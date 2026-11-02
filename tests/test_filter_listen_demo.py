# SPDX-License-Identifier: Apache-2.0
"""Offline demo: synthetic FR → PEQ → sine/silence WAV → metrics stub."""

from __future__ import annotations

import importlib.util
import json
import math
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
    rmse = metrics["fr_rmse_db"]
    assert isinstance(rmse, float)
    assert math.isfinite(rmse)
    assert rmse >= 0.0
    # Default smoke score stays the pre-M4 unsmoothed per-bin fixture value.
    assert abs(rmse - 4.16315) < 1e-9
    assert metrics["fr_rmse_mode"] == "per_bin"
    assert "不宣称准入" in metrics["notes"]
    assert "非听感定稿" in metrics["notes"]
    assert "fixture/objective stub" in metrics["notes"]
    assert metrics["sample_rate"] == 48000
    assert metrics["frame_ms"] == 10
    assert metrics["preamp_db"] == peq["preamp_db"]
    assert metrics["error"] is None
    assert isinstance(metrics["peak"], float)
    assert 0.0 < metrics["peak"] < 1.0
    assert f"fr_rmse_db={rmse}" in proc.stdout
    assert "fr_rmse_mode=per_bin" in proc.stdout
    assert "synthetic-fixture-objective-stub" in proc.stdout
    assert "third_octave_fr_rmse_db=" in proc.stdout

    expected = _expected_fixture_rmse(peq)
    assert abs(rmse - round(expected, 6)) < 1e-9
    bare = _expected_fixture_rmse(
        {"sample_rate": 48000, "preamp_db": 0.0, "bands": []}
    )
    assert abs(rmse - bare) > 1e-3


def _expected_fixture_rmse(peq: dict) -> float:
    from algo.filter_listen import peq as peq_mod

    spec = importlib.util.spec_from_file_location(
        "generate_peq_from_fr_for_demo_rmse",
        MODULE / "scripts" / "generate_peq_from_fr.py",
    )
    assert spec and spec.loader
    fr_fit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fr_fit)
    freqs, measured = fr_fit.load_fr_csv(MODULE / "testdata" / "synthetic_fr.csv")
    target = fr_fit.target_curve(freqs, "harman_like")
    return float(peq_mod.fr_rmse_db(freqs, measured, target, peq))


def test_demo_does_not_require_schema_edits():
    schema = json.loads((MODULE / "configs" / "peq_schema.json").read_text(encoding="utf-8"))
    assert schema["required"] == ["sample_rate", "bands"]
    band = schema["properties"]["bands"]["items"]
    assert band["required"] == ["fc", "Q", "gain", "type"]
