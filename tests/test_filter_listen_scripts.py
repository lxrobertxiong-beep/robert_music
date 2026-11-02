# SPDX-License-Identifier: Apache-2.0
"""CLI smoke for the stdlib filter-listen scripts (no AutoEq, no NumPy)."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "algo" / "filter-listen"
SCRIPTS = MODULE / "scripts"


def test_generate_peq_no_autoeq_matches_schema(tmp_path: Path):
    output = tmp_path / "peq.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "generate_peq_from_fr.py"),
            "--fr",
            str(MODULE / "testdata" / "synthetic_fr.csv"),
            "--target",
            "harman_like",
            "--no-autoeq",
            "-o",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "stdlib_peaking_stub" in proc.stdout
    doc = json.loads(output.read_text(encoding="utf-8"))
    assert doc["sample_rate"] == 48000
    assert doc["meta"]["generator"] == "stdlib_peaking_stub"
    assert 1 <= len(doc["bands"]) <= 8
    for band in doc["bands"]:
        assert set(band) == {"fc", "Q", "gain", "type"}
        assert band["type"] == "peaking"


def test_apply_and_export_metrics_round_trip(tmp_path: Path):
    peq_path = tmp_path / "peq.json"
    wav_out = tmp_path / "out.wav"
    metrics_path = tmp_path / "metrics.json"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "generate_peq_from_fr.py"),
            "--fr",
            str(MODULE / "testdata" / "synthetic_fr.csv"),
            "--no-autoeq",
            "-o",
            str(peq_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "apply_peq_wav.py"),
            "--wav",
            str(MODULE / "testdata" / "sine_1k_0p5s.wav"),
            "--peq",
            str(peq_path),
            "-o",
            str(wav_out),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    with wave.open(str(wav_out), "rb") as handle:
        assert handle.getframerate() == 48000
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
        assert handle.getnframes() > 0

    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "export_metrics.py"),
            "--wav",
            str(wav_out),
            "--peq",
            str(peq_path),
            "-o",
            str(metrics_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["sample_rate"] == 48000
    assert metrics["frame_ms"] == 10
    # No FR was passed, so the score must stay null instead of a made-up number.
    assert metrics["fr_rmse_db"] is None
    assert metrics["peak"] is not None
    assert metrics["error"] is None
    assert "preamp_db" in metrics


def test_export_metrics_synthetic_fr_rmse_is_numeric(tmp_path: Path):
    peq_path = tmp_path / "peq.json"
    metrics_path = tmp_path / "metrics.json"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "generate_peq_from_fr.py"),
            "--fr",
            str(MODULE / "testdata" / "synthetic_fr.csv"),
            "--target",
            "harman_like",
            "--no-autoeq",
            "-o",
            str(peq_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "export_metrics.py"),
            "--wav",
            str(MODULE / "testdata" / "sine_1k_0p5s.wav"),
            "--peq",
            str(peq_path),
            "--fr",
            str(MODULE / "testdata" / "synthetic_fr.csv"),
            "--target",
            "harman_like",
            "-o",
            str(metrics_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    rmse = metrics["fr_rmse_db"]
    assert isinstance(rmse, float)
    assert math.isfinite(rmse)
    assert rmse >= 0.0
    assert f"fr_rmse_db={rmse}" in proc.stdout
    assert "不宣称准入" in metrics["notes"]
    assert "非听感定稿" in metrics["notes"]
    assert "fixture/objective stub" in metrics["notes"]
    assert metrics["error"] is None


def test_generate_help_without_fr():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "generate_peq_from_fr.py")],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--no-autoeq" in proc.stdout
