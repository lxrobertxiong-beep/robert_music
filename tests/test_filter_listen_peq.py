# SPDX-License-Identifier: Apache-2.0
"""PEQ cascade unit tests (stdlib, no NumPy)."""

from __future__ import annotations

import json
import math
from pathlib import Path

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


def test_lowpass_type_falls_back_without_raising():
    peq = peq_from_dict(
        {
            "sample_rate": 48000,
            "bands": [{"fc": 1000.0, "Q": 0.7, "gain": 0.0, "type": "lowpass"}],
        }
    )
    output = peq.process_frame([0.2] * 32)
    assert _finite(output)


def _lfsr(n: int, scale: float = 0.1) -> list[float]:
    state = 1
    out: list[float] = []
    for _ in range(n):
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        out.append(((state / 0x7FFFFFFF) * 2.0 - 1.0) * scale)
    return out
