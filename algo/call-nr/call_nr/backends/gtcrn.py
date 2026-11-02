"""Optional GTCRN adapter. The upstream tree and weights are not vendored.

Pin: https://github.com/Xiaobin-Rong/gtcrn commit
``502ebfab64da7c4a9af78dcb9c6ceef1ebb01c73`` (short ``502ebfab``).
There is no upstream release tag on that commit. Upstream states MIT.

Weights (``checkpoints/model_trained_on_dns3.tar``) are resolved from the
first of:

1. ``CALL_NR_GTCRN_WEIGHTS``
2. ``GTCRN_CHECKPOINT`` (alias)
3. ``$GTCRN_ROOT/checkpoints/model_trained_on_dns3.tar``
4. ``algo/call-nr/third_party/gtcrn/checkpoints/`` (gitignored)
5. ``~/.cache/call-nr/gtcrn/model_trained_on_dns3.tar``

Code is loaded from ``GTCRN_ROOT`` or the same third-party / cache repo
layout (``gtcrn.py`` at the checkout root). A git checkout must be exactly
the pinned commit.

Desktop path only: contract A audio is resampled to 16 kHz with soxr, run
through the upstream STFT (n_fft=512, hop=256, sqrt-Hann), and resampled
back. ``lookahead_frames`` is ``None`` because this is a whole-buffer STFT,
not a 10 ms zero-lookahead baseline. Missing weights, code, or packages
raise ``BackendUnavailable``. Nothing is downloaded.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import numpy as np

from call_nr.contract import CONTRACT_A_ID, SAMPLE_RATE_A, require_contract_a_rate
from call_nr.io import as_mono_f32, downsample_48_to_16, upsample_16_to_48
from call_nr.local_pin import assert_pinned_commit, assert_real_weight
from call_nr.pipeline import BackendUnavailable

GTCRN_COMMIT = "502ebfab64da7c4a9af78dcb9c6ceef1ebb01c73"
GTCRN_COMMIT_SHORT = "502ebfab"
GTCRN_URL = "https://github.com/Xiaobin-Rong/gtcrn"
CHECKPOINT_NAME = "model_trained_on_dns3.tar"
N_FFT = 512
HOP = 256
WIN = 512

_MODEL = None
_MODEL_WEIGHTS: Path | None = None


def _plugin_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _home() -> Path:
    return Path.home()


def _weight_candidates() -> list[Path]:
    found: list[Path] = []
    root = os.environ.get("GTCRN_ROOT")
    if root:
        found.append(Path(root) / "checkpoints" / CHECKPOINT_NAME)
    found.append(_plugin_root() / "third_party" / "gtcrn" / "checkpoints" / CHECKPOINT_NAME)
    found.append(_home() / ".cache" / "call-nr" / "gtcrn" / CHECKPOINT_NAME)
    return found


def _source_candidates() -> list[Path]:
    return [
        _plugin_root() / "third_party" / "gtcrn",
        _home() / ".cache" / "call-nr" / "gtcrn" / "repo",
    ]


def _weights_missing(problems: list[str]) -> BackendUnavailable:
    searched = "\n".join(f"  - {path}" for path in _weight_candidates())
    extra = ""
    if problems:
        extra = " Rejected candidates:\n" + "\n".join(f"  - {item}" for item in problems)
    return BackendUnavailable(
        "GTCRN weights are not available. This package does not vendor or download "
        f"checkpoints. Pin {GTCRN_COMMIT_SHORT} ({GTCRN_COMMIT}) from {GTCRN_URL}. "
        f"Expected file name: {CHECKPOINT_NAME} "
        "(upstream checkpoints/; a Git LFS pointer is not enough). "
        "Set CALL_NR_GTCRN_WEIGHTS or GTCRN_CHECKPOINT to that file, "
        "or place it at ~/.cache/call-nr/gtcrn/"
        f"{CHECKPOINT_NAME}. Code is separate: set GTCRN_ROOT to a checkout of "
        f"{GTCRN_COMMIT} (gtcrn.py at the repo root). "
        f"Searched:\n{searched}{extra}"
    )


def resolve_gtcrn_weights() -> Path:
    """Return the checkpoint path or raise ``BackendUnavailable``."""
    for key in ("CALL_NR_GTCRN_WEIGHTS", "GTCRN_CHECKPOINT"):
        raw = os.environ.get(key)
        if raw:
            return assert_real_weight(Path(raw), label=f"{key} ({CHECKPOINT_NAME})")
    problems: list[str] = []
    for candidate in _weight_candidates():
        if not candidate.is_file():
            continue
        try:
            return assert_real_weight(candidate, label=CHECKPOINT_NAME)
        except BackendUnavailable as exc:
            problems.append(str(exc))
    raise _weights_missing(problems)


def resolve_gtcrn_root() -> Path:
    """Return a checkout that contains ``gtcrn.py`` or raise."""
    raw = os.environ.get("GTCRN_ROOT")
    if raw:
        return _require_source(Path(raw), explicit="GTCRN_ROOT")
    for candidate in _source_candidates():
        if (candidate / "gtcrn.py").is_file():
            return _require_source(candidate, explicit=str(candidate))
    searched = "\n".join(f"  - {path}" for path in _source_candidates())
    raise BackendUnavailable(
        "GTCRN code is not on the local path. This package does not vendor the "
        f"upstream tree. Clone {GTCRN_URL} and check out {GTCRN_COMMIT}, then set "
        "GTCRN_ROOT (or copy that checkout to algo/call-nr/third_party/gtcrn, "
        "which is gitignored, or to ~/.cache/call-nr/gtcrn/repo). "
        f"Expected gtcrn.py at the checkout root. Searched:\n{searched}"
    )


def _require_source(root: Path, *, explicit: str) -> Path:
    if not root.is_dir() or not (root / "gtcrn.py").is_file():
        raise BackendUnavailable(
            f"GTCRN checkout {explicit} does not contain gtcrn.py: {root}. "
            f"Clone {GTCRN_URL} at {GTCRN_COMMIT}. This package does not vendor it."
        )
    assert_pinned_commit(root, GTCRN_COMMIT, label="GTCRN")
    return root


def _require_python_packages() -> None:
    missing = [name for name in ("torch", "einops") if importlib.util.find_spec(name) is None]
    if missing:
        raise BackendUnavailable(
            "GTCRN Python packages are missing: "
            + ", ".join(missing)
            + ". Install them in a local environment (for example `pip install torch einops`). "
            "CI does not install torch and does not download weights. "
            f"Pin {GTCRN_COMMIT_SHORT} ({GTCRN_COMMIT})."
        )


def _load_model():
    """Load GTCRN once per checkpoint path."""
    global _MODEL, _MODEL_WEIGHTS
    weights = resolve_gtcrn_weights()
    root = resolve_gtcrn_root()
    if _MODEL is not None and _MODEL_WEIGHTS == weights:
        return _MODEL
    _require_python_packages()
    import torch

    spec = importlib.util.spec_from_file_location(
        "call_nr_gtcrn_upstream",
        root / "gtcrn.py",
    )
    if spec is None or spec.loader is None:
        raise BackendUnavailable(f"could not load GTCRN module from {root / 'gtcrn.py'}")
    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    except Exception as exc:
        raise BackendUnavailable(
            f"GTCRN module at {root / 'gtcrn.py'} failed to import ({exc}). "
            f"The checkout must be {GTCRN_COMMIT}. torch and einops are required. "
            "This package does not vendor the upstream tree."
        ) from exc
    factory = getattr(module, "GTCRN", None)
    if factory is None:
        raise BackendUnavailable(
            f"{root / 'gtcrn.py'} has no GTCRN class. Expected pin {GTCRN_COMMIT}."
        )
    model = factory().eval()
    try:
        try:
            checkpoint = torch.load(str(weights), map_location="cpu", weights_only=False)
        except TypeError:
            checkpoint = torch.load(str(weights), map_location="cpu")
        state = checkpoint["model"] if isinstance(checkpoint, dict) and "model" in checkpoint else checkpoint
        model.load_state_dict(state)
    except Exception as exc:
        raise BackendUnavailable(
            f"GTCRN checkpoint failed to load from {weights} ({exc}). "
            f"Expected the upstream torch checkpoint {CHECKPOINT_NAME} from {GTCRN_COMMIT}, "
            "not a Git LFS pointer."
        ) from exc
    _MODEL = model
    _MODEL_WEIGHTS = weights
    return model


def _match_length(audio: np.ndarray, length: int) -> np.ndarray:
    if audio.size < length:
        return np.pad(audio, (0, length - audio.size))
    return audio[:length]


def _enhance_16k(model: object, audio_16k: np.ndarray) -> np.ndarray:
    """Run the upstream STFT -> mask -> iSTFT path at 16 kHz."""
    import torch

    wav = torch.from_numpy(np.ascontiguousarray(audio_16k, dtype=np.float32))
    window = torch.hann_window(WIN).pow(0.5)
    spec = torch.stft(
        wav,
        n_fft=N_FFT,
        hop_length=HOP,
        win_length=WIN,
        window=window,
        return_complex=False,
    )
    with torch.no_grad():
        enhanced = model(spec.unsqueeze(0))[0]
    # Upstream infer.py was written for an older istft that accepted a
    # real/imag stack. Current torch istft wants a complex spectrogram.
    if not torch.is_complex(enhanced):
        enhanced = torch.complex(enhanced[..., 0], enhanced[..., 1])
    rendered = torch.istft(
        enhanced,
        n_fft=N_FFT,
        hop_length=HOP,
        win_length=WIN,
        window=window,
    )
    return np.ascontiguousarray(rendered.detach().cpu().numpy(), dtype=np.float32)


class GTCRNBackend:
    """Desktop GTCRN at contract A. Unavailable until local weights and code exist."""

    name = "gtcrn"
    contract_id = CONTRACT_A_ID
    lookahead_frames = None

    def reset(self) -> None:
        return None

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        return self.process(frame, SAMPLE_RATE_A)

    def process(self, samples: np.ndarray, sample_rate: int) -> np.ndarray:
        require_contract_a_rate(sample_rate)
        model = _load_model()
        mono = as_mono_f32(samples)
        if mono.size == 0:
            return mono
        low_rate = downsample_48_to_16(mono)
        enhanced = _enhance_16k(model, low_rate)
        restored = upsample_16_to_48(enhanced)
        return np.ascontiguousarray(_match_length(restored, mono.size), dtype=np.float32)
