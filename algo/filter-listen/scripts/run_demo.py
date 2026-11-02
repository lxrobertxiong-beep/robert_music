#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 daopeng xiong and contributors
"""Minimal offline demo: synthetic FR CSV → PEQ JSON → WAV → metrics stub.

Stdlib only. Always passes ``--no-autoeq``. The soft limiter inside
``apply_peq_wav.py`` stays an engineering stub (非听感定稿). This script
does not report listening quality and leaves ``fr_rmse_db`` null.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
SCRIPTS = MODULE / "scripts"
BAND_KEYS = {"fc", "Q", "gain", "type"}


def _run(args: list[str]) -> str:
    proc = subprocess.run(
        [sys.executable, *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit(proc.returncode)
    text = proc.stdout.strip()
    if text:
        print(text)
    return text


def _check_peq(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("sample_rate") != 48000:
        raise SystemExit(f"demo: expected sample_rate 48000 in {path}")
    bands = doc.get("bands")
    if not isinstance(bands, list) or not bands:
        raise SystemExit(f"demo: expected non-empty bands in {path}")
    for band in bands:
        if set(band) != BAND_KEYS:
            raise SystemExit(f"demo: band keys drifted from peq_schema: {band}")
    generator = (doc.get("meta") or {}).get("generator")
    if generator != "stdlib_peaking_stub":
        raise SystemExit(f"demo: expected stdlib_peaking_stub, got {generator}")
    return doc


def _check_wav(path: Path, *, expect_silence: bool) -> int:
    with wave.open(str(path), "rb") as handle:
        if handle.getframerate() != 48000:
            raise SystemExit(f"demo: {path} sample rate is {handle.getframerate()}")
        if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
            raise SystemExit(f"demo: {path} is not mono 16-bit PCM")
        nframes = handle.getnframes()
        if nframes <= 0:
            raise SystemExit(f"demo: {path} has no frames")
        if expect_silence:
            raw = handle.readframes(nframes)
            if any(raw):
                raise SystemExit(f"demo: silence fixture was not silent after PEQ: {path}")
    return nframes


def _check_metrics(path: Path, peq: dict) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("fr_rmse_db") is not None:
        raise SystemExit("demo: fr_rmse_db must stay null; do not invent a score")
    if doc.get("sample_rate") != 48000 or doc.get("frame_ms") != 10:
        raise SystemExit(f"demo: unexpected metrics header: {doc}")
    if doc.get("preamp_db") != peq.get("preamp_db"):
        raise SystemExit("demo: metrics preamp_db does not match the PEQ document")
    if doc.get("error") is not None or doc.get("peak") is None:
        raise SystemExit(f"demo: metrics stub failed: {doc}")
    return doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the filter-listen offline demo on synthetic fixtures "
            "(--no-autoeq, stdlib, limiter is 非听感定稿)."
        )
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory (default: a new temp directory)",
    )
    parser.add_argument(
        "--fr",
        type=Path,
        default=MODULE / "testdata" / "synthetic_fr.csv",
        help="Frequency-response CSV",
    )
    parser.add_argument(
        "--sine",
        type=Path,
        default=MODULE / "testdata" / "sine_1k_0p5s.wav",
        help="Short sine WAV",
    )
    parser.add_argument(
        "--silence",
        type=Path,
        default=MODULE / "testdata" / "silence_0p5s.wav",
        help="Short silence WAV",
    )
    args = parser.parse_args(argv)

    if args.out is None:
        out = Path(tempfile.mkdtemp(prefix="filter-listen-demo-"))
    else:
        out = args.out
        out.mkdir(parents=True, exist_ok=True)

    peq_path = out / "peq.json"
    sine_out = out / "sine_out.wav"
    silence_out = out / "silence_out.wav"
    metrics_path = out / "metrics.json"

    _run(
        [
            str(SCRIPTS / "generate_peq_from_fr.py"),
            "--fr",
            str(args.fr),
            "--target",
            "harman_like",
            "--no-autoeq",
            "-o",
            str(peq_path),
        ]
    )
    peq = _check_peq(peq_path)

    for src, dest, silence in (
        (args.sine, sine_out, False),
        (args.silence, silence_out, True),
    ):
        _run(
            [
                str(SCRIPTS / "apply_peq_wav.py"),
                "--wav",
                str(src),
                "--peq",
                str(peq_path),
                "-o",
                str(dest),
            ]
        )
        _check_wav(dest, expect_silence=silence)

    _run(
        [
            str(SCRIPTS / "export_metrics.py"),
            "--wav",
            str(sine_out),
            "--peq",
            str(peq_path),
            "-o",
            str(metrics_path),
        ]
    )
    metrics = _check_metrics(metrics_path, peq)

    print(
        "demo ok:"
        f" peq={peq_path}"
        f" sine={sine_out}"
        f" silence={silence_out}"
        f" metrics={metrics_path}"
        f" bands={len(peq['bands'])}"
        f" peak={metrics['peak']}"
        " fr_rmse_db=null"
        " no-autoeq"
        " limiter=engineering-stub (非听感定稿)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
