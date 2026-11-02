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
    assert metrics["fr_rmse_mode"] is None
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
    # Frozen per_bin demo fixture (M4 must not move the default score).
    assert abs(rmse - 4.16315) < 1e-9
    assert metrics["fr_rmse_mode"] == "per_bin"
    assert f"fr_rmse_db={rmse}" in proc.stdout
    assert "不宣称准入" in metrics["notes"]
    assert "非听感定稿" in metrics["notes"]
    assert "fixture/objective stub" in metrics["notes"]
    assert "fr_rmse_mode=per_bin" in metrics["notes"]
    assert metrics["error"] is None


def _write_peq(path: Path, bands: list[dict]) -> None:
    path.write_text(
        json.dumps(
            {
                "sample_rate": 48000,
                "preamp_db": 0.0,
                "bands": bands,
            }
        ),
        encoding="utf-8",
    )


def test_export_metrics_third_octave_is_reproducible(tmp_path: Path):
    peq_path = tmp_path / "peq.json"
    _write_peq(
        peq_path,
        [{"fc": 1000.0, "Q": 0.707, "gain": 0.0, "type": "lowpass"}],
    )
    scores = []
    for name in ("a.json", "b.json"):
        out = tmp_path / name
        subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "export_metrics.py"),
                "--peq",
                str(peq_path),
                "--fr",
                str(MODULE / "testdata" / "synthetic_fr.csv"),
                "--target",
                "harman_like",
                "--fr-rmse-mode",
                "third_octave",
                "-o",
                str(out),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        doc = json.loads(out.read_text(encoding="utf-8"))
        scores.append(doc)
    first, second = scores
    assert first == second
    rmse = first["fr_rmse_db"]
    assert isinstance(rmse, float)
    assert math.isfinite(rmse)
    assert rmse >= 0.0
    assert first["fr_rmse_mode"] == "third_octave"
    assert abs(rmse - 4.16315) > 1e-4
    assert "third_octave" in first["notes"]
    assert "不宣称准入" in first["notes"]
    assert "非听感定稿" in first["notes"]
    assert "fixture/objective stub" in first["notes"]
    assert first["error"] is None


def test_wav_path_rmse_smoke_and_csv_priority(tmp_path: Path):
    identity = tmp_path / "identity.json"
    peaked = tmp_path / "peaked.json"
    _write_peq(identity, [])
    _write_peq(peaked, [{"fc": 1000.0, "Q": 1.0, "gain": 6.0, "type": "peaking"}])

    def export(peq: Path, dest: Path, extra: list[str]) -> dict:
        subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "export_metrics.py"),
                "--peq",
                str(peq),
                "-o",
                str(dest),
                *extra,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(dest.read_text(encoding="utf-8"))

    synth = export(
        identity,
        tmp_path / "synth.json",
        ["--wav-path-rmse", "--target", "flat", "--fr-rmse-mode", "per_bin"],
    )
    assert synth["fr_rmse_mode"] == "per_bin"
    assert isinstance(synth["fr_rmse_db"], float)
    assert synth["fr_rmse_db"] < 1e-4
    assert "synthesized" in synth["notes"]
    assert "soft limiter off" in synth["notes"]
    assert "不宣称准入" in synth["notes"]
    assert "非听感定稿" in synth["notes"]
    assert "fixture/objective stub" in synth["notes"]
    assert synth["error"] is None

    moved = export(
        peaked,
        tmp_path / "moved.json",
        ["--wav-path-rmse", "--target", "flat"],
    )
    assert moved["fr_rmse_db"] > 0.2
    assert moved["fr_rmse_mode"] == "per_bin"

    accepted = export(
        identity,
        tmp_path / "accepted.json",
        [
            "--wav",
            str(MODULE / "testdata" / "sine_1k_0p5s.wav"),
            "--wav-path-rmse",
            "--target",
            "flat",
        ],
    )
    assert accepted["fr_rmse_mode"] == "per_bin"
    assert isinstance(accepted["fr_rmse_db"], float)
    assert math.isfinite(accepted["fr_rmse_db"])
    assert accepted["fr_rmse_db"] >= 0.0
    assert "supplied WAV" in accepted["notes"]
    assert accepted["peak"] is not None
    assert accepted["error"] is None

    peq_path = tmp_path / "from_fr.json"
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
    csv_only = export(
        peq_path,
        tmp_path / "csv.json",
        [
            "--fr",
            str(MODULE / "testdata" / "synthetic_fr.csv"),
            "--target",
            "harman_like",
        ],
    )
    both = export(
        peq_path,
        tmp_path / "both.json",
        [
            "--fr",
            str(MODULE / "testdata" / "synthetic_fr.csv"),
            "--target",
            "harman_like",
            "--wav-path-rmse",
            "--wav",
            str(MODULE / "testdata" / "sine_1k_0p5s.wav"),
        ],
    )
    assert csv_only["fr_rmse_db"] == both["fr_rmse_db"]
    assert abs(both["fr_rmse_db"] - 4.16315) < 1e-9
    assert both["fr_rmse_mode"] == "per_bin"
    assert "FR CSV takes priority" in both["notes"]
    assert "Score source: FR CSV." in both["notes"]


def test_generate_help_without_fr():
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "generate_peq_from_fr.py")],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--no-autoeq" in proc.stdout
