# SPDX-License-Identifier: Apache-2.0
"""Offline demo: synthetic FR → PEQ → sine/silence WAV → metrics stub."""

from __future__ import annotations

import json
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "algo" / "filter-listen"
DEMO = MODULE / "scripts" / "run_demo.py"


def test_run_demo_on_synthetic_fixtures(tmp_path: Path):
    out = tmp_path / "demo"
    proc = subprocess.run(
        [sys.executable, str(DEMO), "--out", str(out)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "stdlib_peaking_stub" in proc.stdout
    assert "demo ok:" in proc.stdout
    assert "非听感定稿" in proc.stdout
    assert "--no-autoeq" in proc.stdout or "no-autoeq" in proc.stdout

    peq = json.loads((out / "peq.json").read_text(encoding="utf-8"))
    assert peq["sample_rate"] == 48000
    assert peq["meta"]["generator"] == "stdlib_peaking_stub"
    assert peq["meta"]["target"] == "harman_like"
    for band in peq["bands"]:
        assert set(band) == {"fc", "Q", "gain", "type"}

    for name, silence in (("sine_out.wav", False), ("silence_out.wav", True)):
        with wave.open(str(out / name), "rb") as handle:
            assert handle.getframerate() == 48000
            assert handle.getnchannels() == 1
            assert handle.getsampwidth() == 2
            assert handle.getnframes() == 24000
            if silence:
                assert not any(handle.readframes(handle.getnframes()))

    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["fr_rmse_db"] is None
    assert metrics["sample_rate"] == 48000
    assert metrics["frame_ms"] == 10
    assert metrics["preamp_db"] == peq["preamp_db"]
    assert metrics["error"] is None
    assert isinstance(metrics["peak"], float)
    assert 0.0 < metrics["peak"] < 1.0


def test_demo_does_not_require_schema_edits():
    schema = json.loads((MODULE / "configs" / "peq_schema.json").read_text(encoding="utf-8"))
    assert schema["required"] == ["sample_rate", "bands"]
    band = schema["properties"]["bands"]["items"]
    assert band["required"] == ["fc", "Q", "gain", "type"]
