#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 daopeng xiong and contributors
"""Stub: write an objective metrics JSON for the eval harness draft.

Does not invent FR RMSE. Peak is measured from 16-bit PCM when a WAV is given.
"""

from __future__ import annotations

import argparse
import array
import json
import sys
import wave
from pathlib import Path
from typing import Any


def _wav_peak(path: Path) -> float | None:
    with wave.open(str(path), "rb") as handle:
        sample_width = handle.getsampwidth()
        nframes = handle.getnframes()
        raw = handle.readframes(nframes)
    if sample_width != 2 or nframes == 0:
        return None
    pcm = array.array("h")
    pcm.frombytes(raw)
    if sys.byteorder != "little":
        pcm.byteswap()
    peak = 0
    for sample in pcm:
        magnitude = abs(int(sample))
        peak = max(peak, magnitude)
    return peak / 32768.0


def metrics_stub(
    wav: Path | None,
    peq: Path | None,
    sample_rate: int,
    frame_ms: float,
    latency_budget_ms: float,
) -> dict[str, Any]:
    peak = None
    preamp_db = None
    err = None
    if wav is not None and wav.exists():
        try:
            peak = _wav_peak(wav)
        except Exception as exc:  # noqa: BLE001 — stub reports the failure, does not invent a peak
            peak = None
            err = str(exc)
    if peq is not None and peq.exists():
        doc = json.loads(peq.read_text(encoding="utf-8"))
        preamp_db = doc.get("preamp_db")

    return {
        "sample_rate": sample_rate,
        "frame_ms": frame_ms,
        "fr_rmse_db": None,
        "peak": peak,
        "preamp_db": preamp_db,
        "latency_budget_ms": latency_budget_ms,
        "notes": "stub — fill in eval harness",
        "error": err,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Export metrics JSON stub.")
    parser.add_argument("--wav", type=Path, default=None)
    parser.add_argument("--peq", type=Path, default=None)
    parser.add_argument("--sample-rate", type=int, default=48000)
    parser.add_argument("--frame-ms", type=float, default=10.0)
    parser.add_argument("--latency-budget-ms", type=float, default=10.0)
    parser.add_argument("-o", "--output", type=Path, default=Path("metrics.json"))
    args = parser.parse_args(argv)

    doc = metrics_stub(
        args.wav,
        args.peq,
        args.sample_rate,
        args.frame_ms,
        args.latency_budget_ms,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
