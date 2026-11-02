"""WAV read/write and the desktop 16 kHz ↔ 48 kHz soxr helpers.

Desktop evaluation resamples only through these helpers so a later
scorer does not drift across resamplers. Contract B sample-rate
conversion is intentionally not implied here.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from call_nr.contract import SAMPLE_RATE_A, SAMPLE_RATE_B


def as_mono_f32(samples: np.ndarray) -> np.ndarray:
    """Downmix to contiguous mono float32. Stereo uses the channel mean."""
    x = np.asarray(samples)
    if x.ndim == 2:
        if x.shape[1] == 1:
            x = x[:, 0]
        elif x.shape[0] == 1:
            x = x[0]
        else:
            x = x.mean(axis=1)
    if x.ndim != 1:
        raise ValueError(f"expected mono audio, got shape {getattr(samples, 'shape', None)}")
    out = np.ascontiguousarray(x, dtype=np.float32)
    if out.size and not np.isfinite(out).all():
        raise ValueError("samples must be finite")
    return out


def read_wav(path: Path | str) -> tuple[np.ndarray, int]:
    """Read a WAV as mono float32 in roughly ``[-1, 1]`` plus its sample rate."""
    data, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
    return as_mono_f32(data), int(sample_rate)


def write_wav(path: Path | str, samples: np.ndarray, sample_rate: int) -> None:
    """Write mono float32 WAV (IEEE float, little-endian)."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    mono = as_mono_f32(samples)
    sf.write(str(dest), mono, int(sample_rate), subtype="FLOAT", format="WAV")


def resample_soxr(samples: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    """Resample mono float32 with soxr (quality HQ). Same rate returns a copy."""
    mono = as_mono_f32(samples)
    src, dst = int(src_sr), int(dst_sr)
    if src <= 0 or dst <= 0:
        raise ValueError(f"sample rates must be positive, got {src} -> {dst}")
    if src == dst:
        return mono.copy()
    try:
        import soxr
    except ImportError as exc:  # pragma: no cover - exercised when extra missing
        raise RuntimeError(
            "soxr is required to resample. Install the call-nr requirements "
            "(pip install soxr). Desktop 16 kHz ↔ 48 kHz must use this helper."
        ) from exc
    converted = soxr.resample(mono, src, dst, quality="HQ")
    return np.ascontiguousarray(converted, dtype=np.float32)


def upsample_16_to_48(samples: np.ndarray) -> np.ndarray:
    return resample_soxr(samples, SAMPLE_RATE_B, SAMPLE_RATE_A)


def downsample_48_to_16(samples: np.ndarray) -> np.ndarray:
    return resample_soxr(samples, SAMPLE_RATE_A, SAMPLE_RATE_B)


def to_contract_a(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    """Return contract-A audio (48 kHz mono float32). 48 kHz input is not resampled."""
    mono = as_mono_f32(samples)
    if int(sample_rate) == SAMPLE_RATE_A:
        return mono
    return resample_soxr(mono, int(sample_rate), SAMPLE_RATE_A)
