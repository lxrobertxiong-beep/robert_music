# SPDX-License-Identifier: Apache-2.0
"""48 kHz / 10 ms graph tests. Limiter is exercised only as an engineering stub."""

from __future__ import annotations

import json
import math
from pathlib import Path

from algo.filter_listen import AudioGraph, GraphConfig

MODULE = Path(__file__).resolve().parents[1] / "algo" / "filter-listen"


def test_graph_48k_10ms_silence():
    graph = AudioGraph(config=GraphConfig(sample_rate=48000, frame_samples=480))
    block = [0.0] * 4800  # 100 ms
    output = graph.process_buffer(block, src_sr=48000)
    assert len(output) == len(block)
    assert all(abs(sample) <= 1e-12 for sample in output)
    described = graph.describe()
    assert described["sample_rate"] == 48000
    assert described["frame_samples"] == 480


def test_graph_with_peq_sine_stays_finite_and_limited():
    doc = json.loads((MODULE / "configs" / "example_compensation.json").read_text(encoding="utf-8"))
    graph = AudioGraph(
        config=GraphConfig(sample_rate=48000, frame_samples=480, peq=doc)
    )
    block = [
        0.2 * math.sin(2.0 * math.pi * 1000.0 * (index / 48000.0))
        for index in range(4800)
    ]
    output = graph.process_buffer(block, src_sr=48000)
    assert all(math.isfinite(sample) for sample in output)
    assert max(abs(sample) for sample in output) < 1.0


def test_call_insert_disabled_by_default():
    graph = AudioGraph(config=GraphConfig())
    seen = {"called": False}

    def _insert(frame):
        seen["called"] = True
        return frame

    graph.call_insert = _insert
    output = graph.process_frame([0.1] * 480)
    assert seen["called"] is False
    assert len(output) == 480


def test_partial_tail_frame_keeps_length():
    graph = AudioGraph(config=GraphConfig(frame_samples=480))
    block = [0.05] * 500
    output = graph.process_buffer(block, src_sr=48000)
    assert len(output) == 500
    assert all(math.isfinite(sample) for sample in output)
