# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 daopeng xiong and contributors
"""Desktop audition helper. Same WAV path as apply_peq_wav. No UI dependencies.

Presets are existing PortablePEQ documents (LP / HP / peaking / the checked-in
example). ``peq_schema.json`` is not modified here. No weights are downloaded
and AutoEq is not vendored. The soft limiter stays the graph stub (非听感定稿).
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import shutil
import tempfile
import uuid
import wave
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = _MODULE_ROOT / "configs"
_APPLY_SCRIPT = _MODULE_ROOT / "scripts" / "apply_peq_wav.py"

# Dropdown order. Stdlib documents only; none of these need AutoEq.
UI_PRESETS = (
    "passthrough",
    "lowpass",
    "highpass",
    "peaking",
    "example_compensation",
)

PRESET_FILES = {
    "passthrough": "audition_passthrough.json",
    "lowpass": "audition_lowpass.json",
    "highpass": "audition_highpass.json",
    "peaking": "audition_peaking.json",
    "example_compensation": "example_compensation.json",
}

_AUTOEQ_GENERATOR = "autoeq"
_APPLY = None


class OptionalPinMissing(Exception):
    """A selected preset needs an optional package that is not installed.

    The desktop status text prefixes this with ``exit 3``, matching the
    call-nr CLI. Shipped LP / HP / PEQ presets do not raise it.
    """


@dataclass(frozen=True)
class AuditionResult:
    """Playable paths plus the same style of text the CLI would print.

    ``ok`` is false when nothing was written. ``message`` starts with
    ``exit 3`` when a selected preset needs a missing optional pin, and
    ``exit 2`` for a bad path, unknown preset, or unreadable WAV.
    """

    input_wav: str | None
    output_wav: str | None
    message: str
    ok: bool


def default_out_dir() -> Path:
    """Directory of WAVs the local UI can play and download."""
    path = Path(tempfile.gettempdir()) / "filter-listen-audition"
    path.mkdir(parents=True, exist_ok=True)
    return path


def coerce_upload(upload: object) -> str | None:
    """Normalize a Gradio audio value to a filesystem path."""
    if upload is None:
        return None
    if isinstance(upload, Path):
        text = str(upload).strip()
        return text or None
    if isinstance(upload, str):
        text = upload.strip()
        return text or None
    if isinstance(upload, dict):
        for key in ("path", "name"):
            value = upload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
    named = getattr(upload, "path", None)
    if isinstance(named, str) and named.strip():
        return named.strip()
    return None


def resolve_input(upload: object, local_path: str | None) -> Path:
    """Prefer a non-empty local path, otherwise the upload."""
    text = (local_path or "").strip()
    if text:
        path = Path(text).expanduser()
        if not path.is_file():
            raise ValueError(f"input not found: {path}")
        return path
    uploaded = coerce_upload(upload)
    if uploaded:
        path = Path(uploaded).expanduser()
        if not path.is_file():
            raise ValueError(f"input not found: {path}")
        return path
    raise ValueError("upload a WAV or pass a local WAV path")


def preset_path(name: str) -> Path:
    """Resolve a dropdown id to a PortablePEQ JSON file."""
    filename = PRESET_FILES.get(name)
    if not filename:
        known = ", ".join(UI_PRESETS)
        raise ValueError(f"unknown filter preset {name!r}; expected {known}")
    return CONFIG_DIR / filename


def _apply_module():
    """Load ``scripts/apply_peq_wav.py`` without making scripts a package."""
    global _APPLY
    if _APPLY is not None:
        return _APPLY
    spec = importlib.util.spec_from_file_location(
        "filter_listen_apply_peq_wav",
        _APPLY_SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {_APPLY_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _APPLY = module
    return module


def _require_optional_pin(doc: dict, name: str) -> None:
    """Exit-3 style failure when a preset declares ``meta.generator=autoeq``.

    The checked-in audition presets use ``audition_preset`` or the example
    hand tune, so this does not run for the dropdown. AutoEq is never vendored.
    """
    meta = doc.get("meta")
    if not isinstance(meta, dict):
        return
    generator = str(meta.get("generator", "")).lower()
    if generator != _AUTOEQ_GENERATOR:
        return
    try:
        importlib.import_module("autoeq.frequency_response")
    except ImportError as exc:
        raise OptionalPinMissing(
            "AutoEq is not importable. Optional pin: pip install autoeq "
            "(MIT; do not vendor the AutoEq tree). "
            f"Preset {name} sets meta.generator=autoeq. "
            "Nothing is downloaded. This is not an evaluation admission "
            f"(不宣称评测准入). Detail: {exc}"
        ) from exc


def load_preset(name: str) -> dict:
    """Read one named preset. Raises ValueError or OptionalPinMissing."""
    path = preset_path(name)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unreadable preset {name}: {exc}") from exc
    if not isinstance(doc, dict):
        raise TypeError(f"preset {name} is not a JSON object")
    _require_optional_pin(doc, name)
    return doc


def _stamp() -> str:
    now = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"{now}-{uuid.uuid4().hex[:8]}"


def _success_message(
    output: Path,
    preset_name: str,
    src_sr: int,
    n_samples: int,
    n_bands: int,
) -> str:
    return (
        f"wrote {output} sr=48000 frame=480 in_sr={src_sr} "
        f"n={n_samples} peq_bands={n_bands} preset={preset_name}\n"
        "soft limiter remains an engineering stub (非听感定稿). "
        "不宣称评测准入。权重不入库，AutoEq 树不入库，peq_schema 未改。"
    )


def audition(
    upload: object,
    local_path: str | None,
    preset_name: str,
    *,
    out_dir: Path | None = None,
) -> AuditionResult:
    """Render one WAV with an existing filter preset.

    Writes a copy of the input (for playback) and a 16-bit mono WAV from
    ``apply_peq_wav`` (48 kHz frame path, soft limiter on). A missing
    optional pin does not raise: the result message is exit-3 text.
    """
    dest_dir = Path(out_dir) if out_dir is not None else default_out_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        src = resolve_input(upload, local_path)
    except ValueError as exc:
        return AuditionResult(None, None, f"exit 2\n{exc}", False)

    stamp = _stamp()
    preview = dest_dir / f"input-{stamp}.wav"
    try:
        apply_mod = _apply_module()
        samples, src_sr = apply_mod.read_wav_mono(src)
        shutil.copyfile(src, preview)
    except (OSError, ValueError, wave.Error, EOFError) as exc:
        return AuditionResult(None, None, f"exit 2\n{exc}", False)

    name = (preset_name or "").strip()
    try:
        doc = load_preset(name)
    except OptionalPinMissing as exc:
        return AuditionResult(str(preview), None, f"exit 3\n{exc}", False)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return AuditionResult(str(preview), None, f"exit 2\n{exc}", False)

    output = dest_dir / f"{name}-{stamp}.wav"
    try:
        rendered, n_bands = apply_mod.apply_peq_document(samples, src_sr, doc)
        apply_mod.write_wav_mono(output, rendered, 48000)
    except (OSError, ValueError, RuntimeError, wave.Error) as exc:
        return AuditionResult(str(preview), None, f"exit 2\n{exc}", False)
    message = _success_message(output, name, src_sr, len(rendered), n_bands)
    return AuditionResult(str(preview), str(output), message, True)
