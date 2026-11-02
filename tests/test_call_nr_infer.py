"""Identity CLI smoke on a short synthetic waveform."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from call_nr.contract import SAMPLE_RATE_A
from call_nr.io import read_wav, write_wav

ROOT = Path(__file__).resolve().parents[1]
INFER = ROOT / "algo" / "call-nr" / "scripts" / "infer.py"
SETUP = ROOT / "algo" / "call-nr" / "scripts" / "setup_pins.sh"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INFER), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_identity_cli_roundtrip(tmp_path: Path):
    count = 480 * 2 + 50
    time = np.arange(count, dtype=np.float32) / SAMPLE_RATE_A
    original = (0.2 * np.sin(2 * np.pi * 440.0 * time)).astype(np.float32)
    src = tmp_path / "in.wav"
    dest = tmp_path / "nested" / "out.wav"
    write_wav(src, original, SAMPLE_RATE_A)
    proc = _run(["--backend", "identity", "-i", str(src), "-o", str(dest)])
    assert proc.returncode == 0, proc.stderr
    assert "A_48k_480" in proc.stdout
    rendered, sample_rate = read_wav(dest)
    assert sample_rate == SAMPLE_RATE_A
    assert rendered.shape == original.shape
    assert np.allclose(rendered, original, atol=1e-6)


def test_identity_cli_module_entrypoint(tmp_path: Path):
    original = np.linspace(-0.2, 0.2, 480, dtype=np.float32)
    src = tmp_path / "in.wav"
    dest = tmp_path / "out.wav"
    write_wav(src, original, SAMPLE_RATE_A)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "call_nr",
            "--backend",
            "passthrough",
            "-i",
            str(src),
            "-o",
            str(dest),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT / "algo" / "call-nr")},
    )
    assert proc.returncode == 0, proc.stderr
    rendered, sample_rate = read_wav(dest)
    assert sample_rate == SAMPLE_RATE_A
    assert np.allclose(rendered, original, atol=1e-6)


def test_identity_cli_upsamples_16k_input(tmp_path: Path):
    pytest.importorskip("soxr")
    original = np.full(1600, 0.1, dtype=np.float32)
    src = tmp_path / "in16.wav"
    dest = tmp_path / "out48.wav"
    write_wav(src, original, 16_000)
    proc = _run(["--backend", "identity", "-i", str(src), "-o", str(dest)])
    assert proc.returncode == 0, proc.stderr
    rendered, sample_rate = read_wav(dest)
    assert sample_rate == SAMPLE_RATE_A
    assert abs(len(rendered) / len(original) - 3.0) < 0.05


def test_cli_rejects_unknown_backend_and_missing_input(tmp_path: Path):
    dest = tmp_path / "out.wav"
    missing = _run(["--backend", "identity", "-i", str(tmp_path / "nope.wav"), "-o", str(dest)])
    assert missing.returncode == 2
    unknown = _run(["--backend", "nope", "-i", str(tmp_path / "nope.wav"), "-o", str(dest)])
    assert unknown.returncode == 2


def test_setup_pins_prints_commits_without_network():
    proc = subprocess.run(
        ["bash", str(SETUP)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "904a876dce1f9ab8860c0a5000ed151f9f6eef58" in proc.stdout
    assert "978576aa8400552a4ce9730838c635aa30db5e61" in proc.stdout
    assert "no weights downloaded" in proc.stdout
