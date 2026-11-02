# SPDX-License-Identifier: Apache-2.0
"""PEQ cascade unit tests (stdlib, no NumPy)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from algo.filter_listen import Biquad, PeqCascade, peq_from_dict

MODULE = Path(__file__).resolve().parents[1] / "algo" / "filter-listen"


def _finite(values) -> bool:
    return all(math.isfinite(float(v)) for v in values)


def test_peaking_unity_ish_at_zero_gain():
    biquad = Biquad.peaking(1000.0, 1.0, 0.0, 48000.0)
    frame = [0.0] * 480
    frame[0] = 1.0
    output = biquad.process(frame)
    assert _finite(output)
    assert abs(output[0] - 1.0) < 0.05


def test_shelf_filters_finite_impulse():
    for factory in (Biquad.lowshelf, Biquad.highshelf):
        biquad = factory(200.0, 0.7, 2.0, 48000.0)
        frame = [0.0] * 64
        frame[0] = 0.5
        output = biquad.process(frame)
        assert _finite(output)


def test_cascade_from_example_json():
    doc = json.loads((MODULE / "configs" / "example_compensation.json").read_text(encoding="utf-8"))
    peq = peq_from_dict(doc)
    assert len(peq.filters) == len(doc["bands"])
    frame = _lfsr(480, scale=0.1)
    output = peq.process_frame(frame)
    assert len(output) == len(frame)
    assert _finite(output)


def test_export_coeffs_keys():
    peq = PeqCascade([Biquad.peaking(500, 1.0, 3.0, 48000)], sample_rate=48000)
    coeffs = peq.export_coeffs()
    assert set(coeffs[0]) == {"b0", "b1", "b2", "a1", "a2"}


def test_lowpass_highpass_match_rbj_and_are_not_peaking():
    """Cookbook |H(fc)| is 20*log10(Q). A peaking fallback at 0 dB would be flat."""
    fs = 48000.0
    fc = 1000.0
    for quality in (0.5, 1.0 / math.sqrt(2.0), 2.0, 4.0):
        expected = 20.0 * math.log10(quality)
        for factory, name in ((Biquad.lowpass, "lowpass"), (Biquad.highpass, "highpass")):
            section = factory(fc, quality, 6.0, fs)
            via_band = Biquad.from_band(
                {"fc": fc, "Q": quality, "gain": 6.0, "type": name},
                fs,
            )
            assert via_band.to_coeffs() == section.to_coeffs()
            assert section.to_coeffs() != Biquad.peaking(fc, quality, 6.0, fs).to_coeffs()
            assert abs(section.magnitude_db(fc, fs) - expected) < 0.02

    low = Biquad.lowpass(fc, 1.0 / math.sqrt(2.0), 0.0, fs)
    high = Biquad.highpass(fc, 1.0 / math.sqrt(2.0), 0.0, fs)
    # A decade below / above the corner, Butterworth sections have separated.
    assert low.magnitude_db(100.0, fs) > -1.0
    assert low.magnitude_db(10000.0, fs) < -30.0
    assert high.magnitude_db(100.0, fs) < -30.0
    assert high.magnitude_db(10000.0, fs) > -1.0


def test_lowpass_passes_dc_highpass_blocks_it():
    fs = 48000.0
    dc = [0.25] * 4800
    low = Biquad.lowpass(1000.0, 0.707, 3.0, fs).process(dc)
    high = Biquad.highpass(1000.0, 0.707, 3.0, fs).process(dc)
    assert _finite(low) and _finite(high)
    assert abs(low[-1] - 0.25) < 1e-3
    assert abs(high[-1]) < 1e-3


def test_lowpass_attenuates_high_sine_highpass_attenuates_low_sine():
    fs = 48000.0
    n = 4800

    def sine(freq: float) -> list[float]:
        return [math.sin(2.0 * math.pi * freq * i / fs) for i in range(n)]

    def tail_rms(samples: list[float]) -> float:
        tail = samples[n // 2 :]
        return math.sqrt(sum(sample * sample for sample in tail) / len(tail))

    low_tone = sine(100.0)
    high_tone = sine(8000.0)

    def low_section(block: list[float]) -> list[float]:
        return Biquad.lowpass(1000.0, 0.707, 0.0, fs).process(block)

    def high_section(block: list[float]) -> list[float]:
        return Biquad.highpass(1000.0, 0.707, 0.0, fs).process(block)

    assert tail_rms(low_section(low_tone)) > 0.5
    assert tail_rms(low_section(high_tone)) < 0.05
    assert tail_rms(high_section(high_tone)) > 0.5
    assert tail_rms(high_section(low_tone)) < 0.05


def test_unknown_band_type_does_not_fall_back_to_peaking():
    with pytest.raises(ValueError, match="unsupported PEQ band type"):
        Biquad.from_band(
            {"fc": 1000.0, "Q": 1.0, "gain": 0.0, "type": "notch"},
            48000.0,
        )


def test_cascade_magnitude_sums_lp_hp():
    fs = 48000.0
    low = Biquad.lowpass(200.0, 0.707, 0.0, fs)
    high = Biquad.highpass(4000.0, 0.707, 0.0, fs)
    cascade = PeqCascade([low, high], sample_rate=fs)
    freq = 1000.0
    expected = low.magnitude_db(freq, fs) + high.magnitude_db(freq, fs)
    assert abs(cascade.magnitude_db(freq) - expected) < 1e-9
    frame = cascade.process_frame([0.2] * 32)
    assert _finite(frame)


# Frozen before M4. Default per_bin on synthetic_fr.csv + identity PEQ vs harman_like.
_SYNTHETIC_IDENTITY_PER_BIN_RMSE = 1.642059223266621


def _load_fr_fit():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "generate_peq_from_fr_for_rmse",
        MODULE / "scripts" / "generate_peq_from_fr.py",
    )
    assert spec and spec.loader
    fr_fit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fr_fit)
    return fr_fit


def _reference_third_octave_rmse(freqs, measured, target) -> float:
    """Independent nearest-band mean dB RMSE for the ISO-ish 20 Hz–20 kHz grid."""
    sums_m: dict[int, float] = {}
    sums_t: dict[int, float] = {}
    counts: dict[int, int] = {}
    for freq, level_m, level_t in zip(freqs, measured, target, strict=True):
        freq_hz = float(freq)
        if freq_hz < 20.0 or freq_hz > 20000.0:
            continue
        k = math.floor(math.log10(freq_hz / 1000.0) * 10.0 + 0.5)
        if k < -17 or k > 13:
            continue
        sums_m[k] = sums_m.get(k, 0.0) + float(level_m)
        sums_t[k] = sums_t.get(k, 0.0) + float(level_t)
        counts[k] = counts.get(k, 0) + 1
    errors = [(sums_m[k] - sums_t[k]) / counts[k] for k in sorted(counts)]
    assert errors
    return math.sqrt(sum(err * err for err in errors) / len(errors))


def test_fixture_fr_rmse_identity_is_zero_and_lowpass_moves_it():
    from algo.filter_listen import peq as peq_mod

    freqs = [100.0, 1000.0, 10000.0]
    measured = [1.0, -2.0, 0.5]
    identity = {
        "sample_rate": 48000,
        "preamp_db": 0.0,
        "bands": [],
    }
    rmse = peq_mod.fr_rmse_db(freqs, measured, measured, identity)
    assert abs(rmse) < 1e-9

    scored = peq_mod.fr_rmse_db(
        freqs,
        measured,
        measured,
        {
            "sample_rate": 48000,
            "preamp_db": 0.0,
            "bands": [{"fc": 1000.0, "Q": 0.707, "gain": 0.0, "type": "lowpass"}],
        },
    )
    assert math.isfinite(scored)
    assert scored > 1.0


def test_per_bin_default_matches_frozen_synthetic_fixture():
    from algo.filter_listen import peq as peq_mod

    fr_fit = _load_fr_fit()
    freqs, measured = fr_fit.load_fr_csv(MODULE / "testdata" / "synthetic_fr.csv")
    target = fr_fit.target_curve(freqs, "harman_like")
    identity = {"sample_rate": 48000, "preamp_db": 0.0, "bands": []}
    per_bin = peq_mod.fr_rmse_db(freqs, measured, target, identity)
    explicit = peq_mod.fr_rmse_db(freqs, measured, target, identity, mode="per_bin")
    assert per_bin == explicit
    assert abs(per_bin - _SYNTHETIC_IDENTITY_PER_BIN_RMSE) < 1e-12


def test_third_octave_reproducible_on_synthetic_csv_and_hand_bands():
    from algo.filter_listen import peq as peq_mod

    identity = {"sample_rate": 48000, "preamp_db": 0.0, "bands": []}
    # Two bins in the 1 kHz band: mean dB error is 1, per-bin RMSE is sqrt(2).
    pair_f = [1000.0, 1001.0]
    pair_m = [0.0, 2.0]
    pair_t = [0.0, 0.0]
    third = peq_mod.fr_rmse_db(pair_f, pair_m, pair_t, identity, mode="third_octave")
    again = peq_mod.fr_rmse_db(pair_f, pair_m, pair_t, identity, mode="third_octave")
    assert third == again
    assert abs(third - 1.0) < 1e-12
    per_bin = peq_mod.fr_rmse_db(pair_f, pair_m, pair_t, identity)
    assert abs(per_bin - math.sqrt(2.0)) < 1e-12

    # Below the 20 Hz aggregation floor: ignored by third_octave, kept by per_bin.
    wide_f = [10.0, 1000.0]
    wide_m = [100.0, 0.0]
    wide_t = [0.0, 0.0]
    assert abs(peq_mod.fr_rmse_db(wide_f, wide_m, wide_t, identity, mode="third_octave")) < 1e-12
    assert peq_mod.fr_rmse_db(wide_f, wide_m, wide_t, identity) > 50.0

    fr_fit = _load_fr_fit()
    freqs, measured = fr_fit.load_fr_csv(MODULE / "testdata" / "synthetic_fr.csv")
    target = fr_fit.target_curve(freqs, "harman_like")
    lowpass = {
        "sample_rate": 48000,
        "preamp_db": 0.0,
        "bands": [{"fc": 1000.0, "Q": 0.707, "gain": 0.0, "type": "lowpass"}],
    }
    first = peq_mod.fr_rmse_db(freqs, measured, target, lowpass, mode="third_octave")
    second = peq_mod.fr_rmse_db(freqs, measured, target, lowpass, mode="third_octave")
    assert first == second
    assert math.isfinite(first)
    cascade = peq_mod.peq_from_dict(lowpass)
    compensated = [
        level + cascade.magnitude_db(freq)
        for freq, level in zip(freqs, measured, strict=True)
    ]
    expected = _reference_third_octave_rmse(freqs, compensated, target)
    assert abs(first - expected) < 1e-12
    centers, mean_m, mean_t = peq_mod.third_octave_paired_means(freqs, compensated, target)
    assert len(centers) == len(peq_mod.third_octave_centers())
    assert len(mean_m) == len(mean_t) == 31
    assert abs(peq_mod.fr_rmse_db(freqs, measured, target, lowpass) - first) > 1e-3

    with pytest.raises(ValueError, match="unknown fr_rmse mode"):
        peq_mod.fr_rmse_db(pair_f, pair_m, pair_t, identity, mode="smoothed")


def test_welch_transfer_reports_constant_gain_and_identity_probe():
    from algo.filter_listen import peq as peq_mod

    probe = peq_mod.synthesize_broadband_probe(48000.0, seconds=0.25)
    again = peq_mod.synthesize_broadband_probe(48000.0, seconds=0.25)
    assert probe == again
    gain_db = 6.0
    scaled = [sample * (10.0 ** (gain_db / 20.0)) for sample in probe]
    freqs, levels = peq_mod.estimate_transfer_db_welch(probe, scaled, 48000.0)
    assert len(freqs) == len(levels)
    assert len(freqs) > 10
    assert max(abs(level - gain_db) for level in levels) < 1e-6
    flat = [0.0 for _ in freqs]
    score = peq_mod.curve_rmse_db(freqs, levels, flat, mode="per_bin", sample_rate=48000.0)
    assert abs(score - gain_db) < 1e-6
    copy_freqs, copy_levels = peq_mod.estimate_transfer_db_welch(probe, probe, 48000.0)
    assert max(abs(level) for level in copy_levels) < 1e-9
    third = peq_mod.curve_rmse_db(
        copy_freqs,
        copy_levels,
        [0.0 for _ in copy_freqs],
        mode="third_octave",
        sample_rate=48000.0,
    )
    assert abs(third) < 1e-9


def _lfsr(n: int, scale: float = 0.1) -> list[float]:
    state = 1
    out: list[float] = []
    for _ in range(n):
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        out.append(((state / 0x7FFFFFFF) * 2.0 - 1.0) * scale)
    return out
