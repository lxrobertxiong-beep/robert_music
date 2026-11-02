"""Desktop audition helper. Same waveform path as the CLI. No UI dependencies."""

from __future__ import annotations

import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from call_nr.cli import run_waveform
from call_nr.io import read_wav, write_wav
from call_nr.pipeline import BackendUnavailable

# Waveform backends the desktop UI can select. silero_vad writes a CSV, not a WAV.
UI_BACKENDS = (
    "identity",
    "passthrough",
    "rnnoise",
    "deepfilternet",
    "gtcrn",
)


@dataclass(frozen=True)
class AuditionResult:
    """Playable paths plus the same text the CLI would print.

    ``ok`` is false when nothing was written. ``message`` starts with
    ``exit 3`` for a missing optional pin and ``exit 2`` for a bad path
    or unreadable file. The rest of an exit-3 message is the backend text
    (env vars, pin commit). No weights are downloaded here.
    """

    input_wav: str | None
    output_wav: str | None
    message: str
    ok: bool


def default_out_dir() -> Path:
    """Directory of WAVs the local UI can play and download."""
    path = Path(tempfile.gettempdir()) / "call-nr-audition"
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


def _stamp() -> str:
    now = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"{now}-{uuid.uuid4().hex[:8]}"


def audition(
    upload: object,
    local_path: str | None,
    backend_name: str,
    *,
    out_dir: Path | None = None,
) -> AuditionResult:
    """Render one WAV with an existing waveform backend.

    Writes a mono float32 copy of the input (original sample rate, for
    playback) and the contract-A processed WAV. A missing pin does not
    raise: the result message is the CLI exit-3 reason.
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
        samples, sample_rate = read_wav(src)
        write_wav(preview, samples, sample_rate)
    except (OSError, ValueError, RuntimeError) as exc:
        return AuditionResult(None, None, f"exit 2\n{exc}", False)

    output = dest_dir / f"{backend_name}-{stamp}.wav"
    try:
        message = run_waveform(backend_name, src, output)
    except BackendUnavailable as exc:
        return AuditionResult(str(preview), None, f"exit 3\n{exc}", False)
    except (OSError, ValueError, RuntimeError) as exc:
        return AuditionResult(str(preview), None, f"exit 2\n{exc}", False)
    return AuditionResult(str(preview), str(output), message, True)
