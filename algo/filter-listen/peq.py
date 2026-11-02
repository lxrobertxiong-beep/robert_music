# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 daopeng xiong and contributors
"""Portable biquad PEQ: peaking / low-shelf / high-shelf, cascade, frame process.

Stdlib port of the reviewed draft (same RBJ cookbook coefficients). The draft
looped with NumPy; P0 CI keeps this path on the Python standard library.
Maps conceptually to music_eq / post_eq coefficient cascades without including
any vendor binary or SDK source.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


def _as_floats(samples: Sequence[float]) -> list[float]:
    return [float(sample) for sample in samples]


@dataclass
class Biquad:
    """Direct-form I biquad with RBJ cookbook coefficients."""

    b0: float
    b1: float
    b2: float
    a1: float
    a2: float
    # State for the mono path (DF-I delays).
    _x1: float = 0.0
    _x2: float = 0.0
    _y1: float = 0.0
    _y2: float = 0.0

    @classmethod
    def peaking(cls, fc: float, q: float, gain_db: float, fs: float) -> Biquad:
        amp = 10.0 ** (gain_db / 40.0)
        w0 = 2.0 * math.pi * fc / fs
        alpha = math.sin(w0) / (2.0 * max(q, 1e-6))
        cos_w0 = math.cos(w0)
        b0 = 1.0 + alpha * amp
        b1 = -2.0 * cos_w0
        b2 = 1.0 - alpha * amp
        a0 = 1.0 + alpha / amp
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha / amp
        return cls(b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)

    @classmethod
    def lowshelf(cls, fc: float, q: float, gain_db: float, fs: float) -> Biquad:
        amp = 10.0 ** (gain_db / 40.0)
        w0 = 2.0 * math.pi * fc / fs
        cos_w0 = math.cos(w0)
        sin_w0 = math.sin(w0)
        alpha = sin_w0 / (2.0 * max(q, 1e-6))
        two_sqrt_a_alpha = 2.0 * math.sqrt(amp) * alpha
        b0 = amp * ((amp + 1) - (amp - 1) * cos_w0 + two_sqrt_a_alpha)
        b1 = 2.0 * amp * ((amp - 1) - (amp + 1) * cos_w0)
        b2 = amp * ((amp + 1) - (amp - 1) * cos_w0 - two_sqrt_a_alpha)
        a0 = (amp + 1) + (amp - 1) * cos_w0 + two_sqrt_a_alpha
        a1 = -2.0 * ((amp - 1) + (amp + 1) * cos_w0)
        a2 = (amp + 1) + (amp - 1) * cos_w0 - two_sqrt_a_alpha
        return cls(b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)

    @classmethod
    def highshelf(cls, fc: float, q: float, gain_db: float, fs: float) -> Biquad:
        amp = 10.0 ** (gain_db / 40.0)
        w0 = 2.0 * math.pi * fc / fs
        cos_w0 = math.cos(w0)
        sin_w0 = math.sin(w0)
        alpha = sin_w0 / (2.0 * max(q, 1e-6))
        two_sqrt_a_alpha = 2.0 * math.sqrt(amp) * alpha
        b0 = amp * ((amp + 1) + (amp - 1) * cos_w0 + two_sqrt_a_alpha)
        b1 = -2.0 * amp * ((amp - 1) + (amp + 1) * cos_w0)
        b2 = amp * ((amp + 1) + (amp - 1) * cos_w0 - two_sqrt_a_alpha)
        a0 = (amp + 1) - (amp - 1) * cos_w0 + two_sqrt_a_alpha
        a1 = 2.0 * ((amp - 1) - (amp + 1) * cos_w0)
        a2 = (amp + 1) - (amp - 1) * cos_w0 - two_sqrt_a_alpha
        return cls(b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)

    @classmethod
    def from_band(cls, band: Mapping[str, Any], fs: float) -> Biquad:
        ftype = str(band.get("type", "peaking")).lower()
        fc = float(band["fc"])
        quality = float(band.get("Q", band.get("q", 1.0)))
        gain = float(band.get("gain", band.get("gain_db", 0.0)))
        if ftype in ("peaking", "peak", "bell"):
            return cls.peaking(fc, quality, gain, fs)
        if ftype in ("lowshelf", "low_shelf", "ls"):
            return cls.lowshelf(fc, quality, gain, fs)
        if ftype in ("highshelf", "high_shelf", "hs"):
            return cls.highshelf(fc, quality, gain, fs)
        # lowpass / highpass are named in peq_schema; skeleton falls back to peaking.
        return cls.peaking(fc, quality, gain, fs)

    def reset(self) -> None:
        self._x1 = self._x2 = self._y1 = self._y2 = 0.0

    def process_sample(self, sample: float) -> float:
        output = (
            self.b0 * sample
            + self.b1 * self._x1
            + self.b2 * self._x2
            - self.a1 * self._y1
            - self.a2 * self._y2
        )
        self._x2, self._x1 = self._x1, sample
        self._y2, self._y1 = self._y1, output
        return output

    def process(self, samples: Sequence[float]) -> list[float]:
        """Process a 1-D mono frame/block. Returns a new list."""
        block = _as_floats(samples)
        return [self.process_sample(sample) for sample in block]

    def to_coeffs(self) -> dict[str, float]:
        return {
            "b0": self.b0,
            "b1": self.b1,
            "b2": self.b2,
            "a1": self.a1,
            "a2": self.a2,
        }


class PeqCascade:
    """Cascade of biquads; frame-aware mono processing."""

    def __init__(
        self,
        filters: Sequence[Biquad] | None = None,
        sample_rate: float = 48000.0,
    ) -> None:
        self.filters: list[Biquad] = list(filters or [])
        self.sample_rate = float(sample_rate)

    @classmethod
    def from_schema(
        cls,
        data: Mapping[str, Any],
        sample_rate: float | None = None,
    ) -> PeqCascade:
        fs = float(sample_rate if sample_rate is not None else data.get("sample_rate", 48000))
        bands = data.get("bands", data.get("filters", []))
        filters = [Biquad.from_band(band, fs) for band in bands]
        return cls(filters, sample_rate=fs)

    def reset(self) -> None:
        for filt in self.filters:
            filt.reset()

    def process_frame(self, frame: Sequence[float]) -> list[float]:
        """Process one mono frame (e.g. 480 samples @ 48 kHz / 10 ms)."""
        output = _as_floats(frame)
        for filt in self.filters:
            output = filt.process(output)
        return output

    def process(
        self,
        samples: Sequence[float],
        frame_size: int | None = None,
    ) -> list[float]:
        """Process a buffer. If frame_size is set, walk frames and keep state."""
        block = _as_floats(samples)
        if not frame_size or frame_size <= 0:
            return self.process_frame(block)
        output = [0.0] * len(block)
        for start in range(0, len(block), frame_size):
            end = min(start + frame_size, len(block))
            output[start:end] = self.process_frame(block[start:end])
        return output

    def export_coeffs(self) -> list[dict[str, float]]:
        return [filt.to_coeffs() for filt in self.filters]


def peq_from_dict(
    data: Mapping[str, Any],
    sample_rate: float | None = None,
) -> PeqCascade:
    """Load a document matching configs/peq_schema.json."""
    return PeqCascade.from_schema(data, sample_rate=sample_rate)
