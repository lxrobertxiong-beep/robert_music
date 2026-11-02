"""Optional Silero VAD. The upstream tree and JIT weights are not vendored.

Pin: https://github.com/snakers4/silero-vad commit
``066409f3d9db45a30d21dfcbf9147826ffdd7052``
(``v6.2.3-8-g066409f``: 8 commits after tag ``v6.2.3``, not that tag).
Upstream states MIT.

This is not a waveform ``DenoiseBackend``. It writes a speech-probability
CSV and a timestamps JSON. Audio is resampled to 16 kHz with ``call_nr.io``
(soxr). The JIT is loaded from a local checkout only — ``torch.hub`` is not
called, so a missing pin cannot silently download.

Checkout resolution:

1. ``SILERO_VAD_ROOT``
2. ``algo/call-nr/third_party/silero-vad`` (gitignored)
3. ``~/.cache/call-nr/silero-vad``

The checkout must contain ``hubconf.py`` and
``src/silero_vad/data/silero_vad.jit``. A git checkout must be exactly the
pinned commit. Missing code, JIT, or torch raises ``BackendUnavailable``.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from call_nr.io import as_mono_f32, read_wav, resample_soxr
from call_nr.local_pin import assert_pinned_commit, assert_real_weight
from call_nr.pipeline import BackendUnavailable

SILERO_COMMIT = "066409f3d9db45a30d21dfcbf9147826ffdd7052"
SILERO_COMMIT_SHORT = "066409f"
SILERO_DESCRIBE = "v6.2.3-8-g066409f"
SILERO_URL = "https://github.com/snakers4/silero-vad"
SILERO_SAMPLE_RATE = 16_000
SILERO_WINDOW = 512
JIT_RELATIVE = Path("src") / "silero_vad" / "data" / "silero_vad.jit"
TIMESTAMPS_NAME = "speech_timestamps.json"

_CACHED: tuple[object, object, Path] | None = None


def _plugin_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _home() -> Path:
    return Path.home()


def _root_candidates() -> list[Path]:
    return [
        _plugin_root() / "third_party" / "silero-vad",
        _home() / ".cache" / "call-nr" / "silero-vad",
    ]


def _missing_root(problems: list[str]) -> BackendUnavailable:
    searched = "\n".join(f"  - {path}" for path in _root_candidates())
    extra = ""
    if problems:
        extra = " Rejected checkouts:\n" + "\n".join(f"  - {item}" for item in problems)
    return BackendUnavailable(
        "Silero VAD is not available. This package does not vendor the upstream "
        f"tree or download weights. Pin {SILERO_COMMIT_SHORT} ({SILERO_COMMIT}, "
        f"{SILERO_DESCRIBE}) from {SILERO_URL}. Set SILERO_VAD_ROOT to a checkout "
        "that contains hubconf.py and src/silero_vad/data/silero_vad.jit "
        "(a Git LFS pointer is not enough), or place that tree at "
        "~/.cache/call-nr/silero-vad. torch.hub is not used. "
        f"Searched:\n{searched}{extra}"
    )


def _require_root(root: Path, *, explicit: str) -> Path:
    hubconf = root / "hubconf.py"
    jit = root / JIT_RELATIVE
    if not root.is_dir() or not hubconf.is_file():
        raise BackendUnavailable(
            f"Silero VAD checkout {explicit} has no hubconf.py: {root}. "
            f"Clone {SILERO_URL} at {SILERO_COMMIT}. This package does not vendor it."
        )
    try:
        assert_real_weight(jit, label=f"Silero VAD JIT ({JIT_RELATIVE.as_posix()})")
    except BackendUnavailable as exc:
        raise BackendUnavailable(
            f"{exc} Expected it inside {root}. "
            "If the file is a Git LFS pointer, fetch the real JIT from the pinned "
            "commit. This package does not download weights."
        ) from exc
    assert_pinned_commit(root, SILERO_COMMIT, label="Silero VAD")
    return root


def resolve_silero_root() -> Path:
    """Return the local Silero checkout or raise ``BackendUnavailable``."""
    raw = os.environ.get("SILERO_VAD_ROOT")
    if raw:
        return _require_root(Path(raw), explicit="SILERO_VAD_ROOT")
    problems: list[str] = []
    for candidate in _root_candidates():
        if not candidate.exists():
            continue
        try:
            return _require_root(candidate, explicit=str(candidate))
        except BackendUnavailable as exc:
            problems.append(str(exc))
    raise _missing_root(problems)


def _require_torch() -> None:
    if importlib.util.find_spec("torch") is None:
        raise BackendUnavailable(
            "Silero VAD needs torch in the local environment "
            "(for example `pip install torch`). CI does not install torch and does "
            f"not download weights. Pin {SILERO_COMMIT_SHORT} ({SILERO_COMMIT})."
        )


def _load(root: Path):
    """Load the JIT model from the local hubconf. No torch.hub network call."""
    global _CACHED
    if _CACHED is not None and _CACHED[2] == root:
        return _CACHED[0], _CACHED[1]
    _require_torch()
    spec = importlib.util.spec_from_file_location(
        "call_nr_silero_hubconf",
        root / "hubconf.py",
    )
    if spec is None or spec.loader is None:
        raise BackendUnavailable(f"could not load Silero hubconf from {root / 'hubconf.py'}")
    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        model, utils = module.silero_vad(onnx=False)
    except Exception as exc:
        raise BackendUnavailable(
            f"Silero VAD failed to load from {root} ({exc}). "
            f"Expected pin {SILERO_COMMIT} with src/silero_vad/data/silero_vad.jit. "
            "torch.hub is not used and this package does not download weights."
        ) from exc
    get_timestamps = utils[0]
    _CACHED = (model, get_timestamps, root)
    return model, get_timestamps


def _reset(model: object) -> None:
    reset = getattr(model, "reset_states", None)
    if callable(reset):
        reset()


def _to_16k(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    mono = as_mono_f32(samples)
    if int(sample_rate) == SILERO_SAMPLE_RATE:
        return mono
    return resample_soxr(mono, int(sample_rate), SILERO_SAMPLE_RATE)


def _probability(model: object, chunk) -> float:
    """Read one window probability without calling the model twice.

    A second call would advance the JIT state. ``reshape`` covers both a
    scalar tensor and a one-element batch.
    """
    value = model(chunk, SILERO_SAMPLE_RATE)
    flat = value.reshape(-1)
    return float(flat[0].item())


def _jsonable(value):
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes, np.ndarray)):
        try:
            return value.item()
        except (ValueError, AttributeError):
            return value
    return value


@dataclass(frozen=True)
class SileroVadResult:
    """Window probabilities and speech timestamps at 16 kHz."""

    probs: list[tuple[float, float]]
    timestamps: list[dict]
    sample_rate_hz: int = SILERO_SAMPLE_RATE
    window_samples: int = SILERO_WINDOW


def analyze(samples: np.ndarray, sample_rate: int) -> SileroVadResult:
    """Return 16 kHz speech probabilities and timestamps.

    Raises ``BackendUnavailable`` when the local pin or torch is missing.
    """
    root = resolve_silero_root()
    model, get_timestamps = _load(root)
    audio_16k = _to_16k(samples, sample_rate)
    import torch

    audio = torch.from_numpy(np.ascontiguousarray(audio_16k, dtype=np.float32))
    probs: list[tuple[float, float]] = []
    _reset(model)
    with torch.no_grad():
        for start in range(0, max(0, int(audio.numel()) - SILERO_WINDOW + 1), SILERO_WINDOW):
            chunk = audio[start : start + SILERO_WINDOW]
            probs.append((start / float(SILERO_SAMPLE_RATE), _probability(model, chunk)))
    if audio.numel() == 0:
        timestamps: list[dict] = []
    else:
        _reset(model)
        raw = get_timestamps(audio, model, sampling_rate=SILERO_SAMPLE_RATE)
        timestamps = list(_jsonable(raw))
    return SileroVadResult(probs=probs, timestamps=timestamps)


def write_outputs(result: SileroVadResult, csv_path: Path) -> Path:
    """Write ``t_sec,speech_prob`` CSV and a sibling timestamps JSON."""
    dest = Path(csv_path)
    if dest.name == TIMESTAMPS_NAME:
        raise ValueError(
            f"CSV path must not be named {TIMESTAMPS_NAME}; that name is the timestamps file"
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["t_sec", "speech_prob"])
        writer.writerows(result.probs)
    timestamps_path = dest.parent / TIMESTAMPS_NAME
    payload = {
        "backend": "silero_vad",
        "pin": SILERO_COMMIT,
        "describe": SILERO_DESCRIBE,
        "sample_rate_hz": result.sample_rate_hz,
        "window_samples": result.window_samples,
        "timestamps": result.timestamps,
    }
    timestamps_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return timestamps_path


def run_files(source: Path, csv_path: Path) -> tuple[Path, Path, int]:
    """Read ``source``, analyze, and write the CSV plus timestamps JSON."""
    samples, sample_rate = read_wav(source)
    result = analyze(samples, sample_rate)
    timestamps_path = write_outputs(result, csv_path)
    return Path(csv_path), timestamps_path, len(result.probs)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="call-nr-silero-vad",
        description=(
            "Run the pinned Silero VAD on a WAV file. "
            "Writes a speech-probability CSV and speech_timestamps.json. "
            "Does not download weights."
        ),
    )
    parser.add_argument(
        "input_pos",
        nargs="?",
        type=Path,
        help="input WAV (alternative to -i)",
    )
    parser.add_argument("-i", "--input", type=Path, help="input WAV")
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        type=Path,
        help=f"probability CSV path; {TIMESTAMPS_NAME} is written beside it",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    source = args.input or args.input_pos
    if source is None:
        print("input WAV is required (-i or a positional path)", file=sys.stderr)
        return 2
    if not source.is_file():
        print(f"input not found: {source}", file=sys.stderr)
        return 2
    try:
        csv_path, timestamps_path, count = run_files(source, args.output)
    except BackendUnavailable as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(
        f"wrote {csv_path} timestamps={timestamps_path} windows={count} "
        f"backend=silero_vad sr={SILERO_SAMPLE_RATE} pin={SILERO_COMMIT_SHORT}",
        file=sys.stdout,
    )
    return 0
