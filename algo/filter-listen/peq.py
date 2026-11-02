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


# ``per_bin`` is the historical unsmoothed dB RMSE. ``third_octave`` is opt-in.
FR_RMSE_MODE_PER_BIN = "per_bin"
FR_RMSE_MODE_THIRD_OCTAVE = "third_octave"
FR_RMSE_MODES = (FR_RMSE_MODE_PER_BIN, FR_RMSE_MODE_THIRD_OCTAVE)

# ISO-ish 1/3-oct centers: exact base-10 series f = 1000 * 10^(k/10)
# for k = -17..13. Preferred labels of that series run from 20 Hz to 20 kHz
# (exact centers are about 19.95 Hz .. 19.95 kHz). Not a listening weight.
_THIRD_OCTAVE_K_MIN = -17
_THIRD_OCTAVE_K_MAX = 13
_THIRD_OCTAVE_F_MIN = 20.0
_THIRD_OCTAVE_F_MAX = 20000.0


def _validate_fr_rmse_mode(mode: str) -> str:
    if mode not in FR_RMSE_MODES:
        allowed = ", ".join(FR_RMSE_MODES)
        raise ValueError(f"unknown fr_rmse mode {mode!r}; expected {allowed}")
    return mode


def third_octave_centers() -> list[float]:
    """ISO-ish 1/3-oct center frequencies covering nominal 20 Hz–20 kHz."""
    return [
        1000.0 * (10.0 ** (k / 10.0))
        for k in range(_THIRD_OCTAVE_K_MIN, _THIRD_OCTAVE_K_MAX + 1)
    ]


def _third_octave_band_index(freq_hz: float) -> int | None:
    """Nearest base-10 1/3-oct band, or None outside 20 Hz–20 kHz."""
    if freq_hz < _THIRD_OCTAVE_F_MIN or freq_hz > _THIRD_OCTAVE_F_MAX:
        return None
    k_float = math.log10(freq_hz / 1000.0) * 10.0
    k = math.floor(k_float + 0.5)
    if k < _THIRD_OCTAVE_K_MIN or k > _THIRD_OCTAVE_K_MAX:
        return None
    return k - _THIRD_OCTAVE_K_MIN


def third_octave_paired_means(
    freqs: Sequence[float],
    levels_a: Sequence[float],
    levels_b: Sequence[float],
) -> tuple[list[float], list[float], list[float]]:
    """Mean dB of two curves on shared ISO-ish 1/3-oct bands.

    Bands with no in-range point are skipped (nothing is invented). A point
    in 20 Hz–20 kHz belongs to the nearest center ``1000 * 10^(k/10)``.
    Returns ``(centers, mean_a, mean_b)``.
    """
    if len(freqs) != len(levels_a) or len(freqs) != len(levels_b):
        raise ValueError("freqs, levels_a, and levels_b must have the same length")
    n_bands = _THIRD_OCTAVE_K_MAX - _THIRD_OCTAVE_K_MIN + 1
    sums_a = [0.0] * n_bands
    sums_b = [0.0] * n_bands
    counts = [0] * n_bands
    for freq, level_a, level_b in zip(freqs, levels_a, levels_b, strict=True):
        index = _third_octave_band_index(float(freq))
        if index is None:
            continue
        sums_a[index] += float(level_a)
        sums_b[index] += float(level_b)
        counts[index] += 1
    centers = third_octave_centers()
    kept_centers: list[float] = []
    mean_a: list[float] = []
    mean_b: list[float] = []
    for index, count in enumerate(counts):
        if count == 0:
            continue
        kept_centers.append(centers[index])
        mean_a.append(sums_a[index] / count)
        mean_b.append(sums_b[index] / count)
    return kept_centers, mean_a, mean_b


def _rmse(errors: Sequence[float]) -> float:
    if not errors:
        raise ValueError("no points to score")
    mean_square = sum(err * err for err in errors) / len(errors)
    return math.sqrt(mean_square)


def curve_rmse_db(
    freqs: Sequence[float],
    measured_db: Sequence[float],
    target_db: Sequence[float],
    *,
    mode: str = FR_RMSE_MODE_PER_BIN,
    sample_rate: float = 48000.0,
) -> float:
    """dB RMSE of two curves. ``mode`` selects per-bin or 1/3-oct means.

    Per-bin uses every strictly in-band point (``0 < f < Nyquist``), which is
    the historical score. Third-octave then averages those points as mean dB
    inside each 20 Hz–20 kHz ISO-ish band and scores the band means. This is
    an objective fixture stub, not a listening sign-off and not an admission
    (准入) result.
    """
    mode = _validate_fr_rmse_mode(mode)
    if not (len(freqs) == len(measured_db) == len(target_db)):
        raise ValueError("freqs, measured_db, and target_db must have the same length")
    if sample_rate <= 0.0:
        raise ValueError(f"sample rate must be positive, got {sample_rate}")
    nyquist = float(sample_rate) / 2.0
    kept_f: list[float] = []
    kept_m: list[float] = []
    kept_t: list[float] = []
    for freq, measured, target in zip(freqs, measured_db, target_db, strict=True):
        freq_hz = float(freq)
        if freq_hz <= 0.0 or freq_hz >= nyquist:
            continue
        kept_f.append(freq_hz)
        kept_m.append(float(measured))
        kept_t.append(float(target))
    if mode == FR_RMSE_MODE_PER_BIN:
        if not kept_m:
            raise ValueError("no in-band frequency-response points to score")
        return _rmse([measured - target for measured, target in zip(kept_m, kept_t, strict=True)])
    _centers, mean_measured, mean_target = third_octave_paired_means(kept_f, kept_m, kept_t)
    if not mean_measured:
        raise ValueError("no in-band 1/3-octave points to score")
    return _rmse(
        [
            measured - target
            for measured, target in zip(mean_measured, mean_target, strict=True)
        ]
    )


def fr_rmse_db(
    freqs: Sequence[float],
    measured_db: Sequence[float],
    target_db: Sequence[float],
    peq_doc: Mapping[str, Any],
    sample_rate: float | None = None,
    *,
    mode: str = FR_RMSE_MODE_PER_BIN,
) -> float:
    """dB RMSE of measured FR + preamp + cascade versus a target curve.

    In-band bins only (strictly inside Nyquist). ``mode="per_bin"`` (default)
    is the unsmoothed per-bin score. ``mode="third_octave"`` averages that
    compensated curve as mean dB on ISO-ish 1/3-oct centers from 20 Hz to
    20 kHz, then takes RMSE against the same mean of the target.

    This is an objective score on the curves you pass in — a fixture stub
    when those curves are the synthetic demo CSV. It is not a listening
    sign-off and not an admission (准入) result.
    """
    mode = _validate_fr_rmse_mode(mode)
    if not (len(freqs) == len(measured_db) == len(target_db)):
        raise ValueError("freqs, measured_db, and target_db must have the same length")
    cascade = peq_from_dict(peq_doc, sample_rate=sample_rate)
    raw_preamp = peq_doc.get("preamp_db", 0.0)
    preamp_db = 0.0 if raw_preamp is None else float(raw_preamp)
    nyquist = cascade.sample_rate / 2.0
    kept_f: list[float] = []
    kept_m: list[float] = []
    kept_t: list[float] = []
    for freq, measured, target in zip(freqs, measured_db, target_db, strict=True):
        freq_hz = float(freq)
        if freq_hz <= 0.0 or freq_hz >= nyquist:
            continue
        compensated = float(measured) + preamp_db + cascade.magnitude_db(freq_hz)
        kept_f.append(freq_hz)
        kept_m.append(compensated)
        kept_t.append(float(target))
    if not kept_m:
        raise ValueError("no in-band frequency-response points to score")
    return curve_rmse_db(
        kept_f,
        kept_m,
        kept_t,
        mode=mode,
        sample_rate=cascade.sample_rate,
    )


def synthesize_broadband_probe(
    sample_rate: float,
    seconds: float = 0.5,
    amplitude: float = 0.1,
) -> list[float]:
    """Deterministic broadband noise used only as a WAV-path FR probe.

    Not a listening stimulus. The LCG is fixed so repeated scores match.
    """
    if sample_rate <= 0.0 or seconds <= 0.0:
        raise ValueError("sample_rate and seconds must be positive")
    if amplitude <= 0.0:
        raise ValueError("amplitude must be positive")
    n_samples = round(float(sample_rate) * float(seconds))
    if n_samples < 32:
        raise ValueError("probe is too short for a Welch FR estimate")
    state = 1
    probe: list[float] = []
    scale = float(amplitude)
    for _ in range(n_samples):
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        probe.append(((state / 0x7FFFFFFF) * 2.0 - 1.0) * scale)
    return probe


def _radix2_fft(samples: Sequence[complex]) -> list[complex]:
    """In-order radix-2 DIT FFT. Length must be a power of two."""
    n = len(samples)
    if n == 0 or n & (n - 1):
        raise ValueError(f"FFT length must be a power of two, got {n}")
    out = [complex(sample) for sample in samples]
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            out[i], out[j] = out[j], out[i]
    length = 2
    while length <= n:
        half = length >> 1
        angle = -2.0 * math.pi / length
        wlen = complex(math.cos(angle), math.sin(angle))
        for start in range(0, n, length):
            twiddle = 1.0 + 0.0j
            for k in range(half):
                even = out[start + k]
                odd = out[start + k + half] * twiddle
                out[start + k] = even + odd
                out[start + k + half] = even - odd
                twiddle *= wlen
        length <<= 1
    return out


def _welch_nfft(n_samples: int, nperseg: int) -> int:
    if n_samples < 32:
        raise ValueError("signal too short for Welch FR")
    cap = min(int(nperseg), n_samples)
    nfft = 1
    while nfft * 2 <= cap:
        nfft *= 2
    if nfft < 32:
        raise ValueError("signal too short for Welch FR")
    return nfft


def estimate_transfer_db_welch(
    reference: Sequence[float],
    processed: Sequence[float],
    sample_rate: float,
    nperseg: int = 1024,
) -> tuple[list[float], list[float]]:
    """Welch transfer magnitude in dB, ``10*log10(P_processed / P_reference)``.

    Hann window, 50% overlap, stdlib radix-2 FFT. DC and Nyquist bins are
    omitted. Bins whose reference power is negligible are omitted so a tonal
    WAV does not invent a curve in silent bins. This estimates the linear
    apply path; it is not a listening measurement.
    """
    if len(reference) != len(processed):
        raise ValueError("reference and processed lengths differ")
    if sample_rate <= 0.0:
        raise ValueError(f"sample rate must be positive, got {sample_rate}")
    nfft = _welch_nfft(len(reference), nperseg)
    window = [
        0.5 - 0.5 * math.cos(2.0 * math.pi * i / nfft)
        for i in range(nfft)
    ]
    hop = nfft // 2
    acc_ref = [0.0] * (nfft // 2 + 1)
    acc_out = [0.0] * (nfft // 2 + 1)
    segments = 0
    start = 0
    n_samples = len(reference)
    while start + nfft <= n_samples:
        ref_frame = [complex(float(reference[start + i]) * window[i]) for i in range(nfft)]
        out_frame = [complex(float(processed[start + i]) * window[i]) for i in range(nfft)]
        ref_spec = _radix2_fft(ref_frame)
        out_spec = _radix2_fft(out_frame)
        for k in range(nfft // 2 + 1):
            ref_bin = ref_spec[k]
            out_bin = out_spec[k]
            acc_ref[k] += ref_bin.real * ref_bin.real + ref_bin.imag * ref_bin.imag
            acc_out[k] += out_bin.real * out_bin.real + out_bin.imag * out_bin.imag
        segments += 1
        start += hop
    if segments == 0:
        raise ValueError("signal too short for Welch FR")
    freqs: list[float] = []
    levels: list[float] = []
    power_floor = 1e-20
    for k in range(1, nfft // 2):
        pref = acc_ref[k] / segments
        if pref < power_floor:
            continue
        pout = acc_out[k] / segments
        freqs.append(k * float(sample_rate) / nfft)
        levels.append(10.0 * math.log10(max(pout, power_floor) / pref))
    if not freqs:
        raise ValueError("no Welch bins with reference energy to score")
    return freqs, levels
