# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 daopeng xiong and contributors
"""Portable biquad PEQ: peaking, shelves, lowpass, highpass; cascade; frame process.

Stdlib port of the reviewed draft (RBJ Audio EQ Cookbook coefficients). The
draft looped with NumPy; P0 CI keeps this path on the Python standard library.
Maps conceptually to music_eq / post_eq coefficient cascades without including
any vendor binary or SDK source.

``lowpass`` and ``highpass`` ignore the peq_schema ``gain`` field. Those
RBJ sections have 0 dB passband gain. ``gain`` stays required in the JSON
schema so the platform plugin contract does not change.
"""

from __future__ import annotations

import cmath
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
    def lowpass(cls, fc: float, q: float, gain_db: float, fs: float) -> Biquad:
        """RBJ cookbook lowpass. Passband gain is 0 dB.

        ``gain_db`` is the peq_schema ``gain`` field. The field stays
        required in JSON and is ignored on this path: the cookbook LPF has
        no dB-gain term. Do not fold a non-zero gain into these coefficients
        or fall back to a peaking section.
        """
        del gain_db  # peq_schema gain ignored; RBJ LPF passband is 0 dB
        w0 = 2.0 * math.pi * fc / fs
        cos_w0 = math.cos(w0)
        alpha = math.sin(w0) / (2.0 * max(q, 1e-6))
        one_minus = 1.0 - cos_w0
        b0 = one_minus / 2.0
        b1 = one_minus
        b2 = one_minus / 2.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
        return cls(b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)

    @classmethod
    def highpass(cls, fc: float, q: float, gain_db: float, fs: float) -> Biquad:
        """RBJ cookbook highpass. Passband gain is 0 dB.

        ``gain_db`` is the peq_schema ``gain`` field. The field stays
        required in JSON and is ignored on this path: the cookbook HPF has
        no dB-gain term. Do not fold a non-zero gain into these coefficients
        or fall back to a peaking section.
        """
        del gain_db  # peq_schema gain ignored; RBJ HPF passband is 0 dB
        w0 = 2.0 * math.pi * fc / fs
        cos_w0 = math.cos(w0)
        alpha = math.sin(w0) / (2.0 * max(q, 1e-6))
        one_plus = 1.0 + cos_w0
        b0 = one_plus / 2.0
        b1 = -one_plus
        b2 = one_plus / 2.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
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
        # lowpass / highpass: peq_schema ``gain`` is still required, but the
        # RBJ coefficient path ignores it (passband gain is 0 dB).
        if ftype in ("lowpass", "low_pass", "lp"):
            return cls.lowpass(fc, quality, gain, fs)
        if ftype in ("highpass", "high_pass", "hp"):
            return cls.highpass(fc, quality, gain, fs)
        raise ValueError(
            f"unsupported PEQ band type {ftype!r}; "
            "expected peaking, lowshelf, highshelf, lowpass, or highpass"
        )

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

    def magnitude_db(self, freq_hz: float, fs: float) -> float:
        """Magnitude in dB of this section at ``freq_hz`` (0 dB is unity)."""
        if fs <= 0.0:
            raise ValueError(f"sample rate must be positive, got {fs}")
        if freq_hz < 0.0:
            raise ValueError(f"frequency must be >= 0, got {freq_hz}")
        omega = 2.0 * math.pi * min(freq_hz, fs / 2.0) / fs
        z1 = cmath.exp(-1j * omega)
        z2 = z1 * z1
        numerator = self.b0 + self.b1 * z1 + self.b2 * z2
        denominator = 1.0 + self.a1 * z1 + self.a2 * z2
        if denominator == 0:
            return -240.0
        magnitude = abs(numerator / denominator)
        if magnitude < 1e-12:
            return -240.0
        return 20.0 * math.log10(magnitude)


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

    def magnitude_db(self, freq_hz: float) -> float:
        """Cascade magnitude in dB. Preamp is not included."""
        total = 0.0
        for filt in self.filters:
            total += filt.magnitude_db(freq_hz, self.sample_rate)
        return total


def peq_from_dict(
    data: Mapping[str, Any],
    sample_rate: float | None = None,
) -> PeqCascade:
    """Load a document matching configs/peq_schema.json."""
    return PeqCascade.from_schema(data, sample_rate=sample_rate)


def fr_rmse_db(
    freqs: Sequence[float],
    measured_db: Sequence[float],
    target_db: Sequence[float],
    peq_doc: Mapping[str, Any],
    sample_rate: float | None = None,
) -> float:
    """dB RMSE of measured FR + preamp + cascade versus a target curve.

    In-band bins only (strictly inside Nyquist). This is an objective score
    on the curves you pass in — a fixture stub when those curves are the
    synthetic demo CSV. It is not a listening sign-off and not an admission
    (准入) result.
    """
    if not (len(freqs) == len(measured_db) == len(target_db)):
        raise ValueError("freqs, measured_db, and target_db must have the same length")
    cascade = peq_from_dict(peq_doc, sample_rate=sample_rate)
    raw_preamp = peq_doc.get("preamp_db", 0.0)
    preamp_db = 0.0 if raw_preamp is None else float(raw_preamp)
    nyquist = cascade.sample_rate / 2.0
    errors: list[float] = []
    for freq, measured, target in zip(freqs, measured_db, target_db, strict=True):
        freq_hz = float(freq)
        if freq_hz <= 0.0 or freq_hz >= nyquist:
            continue
        compensated = float(measured) + preamp_db + cascade.magnitude_db(freq_hz)
        errors.append(compensated - float(target))
    if not errors:
        raise ValueError("no in-band frequency-response points to score")
    mean_square = sum(err * err for err in errors) / len(errors)
    return math.sqrt(mean_square)
