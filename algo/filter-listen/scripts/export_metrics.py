#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 daopeng xiong and contributors
"""Write an objective metrics JSON for the eval harness draft.

Peak is measured from 16-bit PCM when a WAV is given. ``fr_rmse_db`` is
filled only when an FR CSV is supplied: dB RMSE of that curve after the
portable PEQ versus a built-in target. Without an FR the field stays null
so a score is not invented. A computed value is a fixture/objective stub
only — not an admission (不宣称准入) result and not a listening sign-off
(非听感定稿).
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


# Shown whenever fr_rmse_db is computed. The number is real for the curves
# that were passed in; the sentence keeps it from being read as a sign-off.
FIXTURE_RMSE_NOTE = (
    "fixture/objective stub only: dB RMSE of the supplied FR after this "
    "portable PEQ (preamp + biquad cascade) versus the built-in target. "
    "不宣称准入. Not a listening sign-off (非听感定稿). "
    "The soft limiter is not part of this score."
)


def _score_supplied_fr(peq_doc: dict[str, Any], fr: Path, target_name: str) -> float:
    scripts = Path(__file__).resolve().parent
    module_root = scripts.parent
    for entry in (str(module_root), str(scripts)):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    import generate_peq_from_fr as fr_fit
    from peq import fr_rmse_db as score_fr_rmse_db

    freqs, measured = fr_fit.load_fr_csv(fr)
    target = fr_fit.target_curve(freqs, target_name)
    return float(score_fr_rmse_db(freqs, measured, target, peq_doc))


def metrics_stub(
    wav: Path | None,
    peq: Path | None,
    sample_rate: int,
    frame_ms: float,
    latency_budget_ms: float,
    fr: Path | None = None,
    target_name: str = "harman_like",
) -> dict[str, Any]:
    peak = None
    preamp_db = None
    err = None
    peq_doc: dict[str, Any] | None = None
    if wav is not None and wav.exists():
        try:
            peak = _wav_peak(wav)
        except Exception as exc:  # noqa: BLE001 — stub reports the failure, does not invent a peak
            peak = None
            err = str(exc)
    if peq is not None and peq.exists():
        peq_doc = json.loads(peq.read_text(encoding="utf-8"))
        preamp_db = peq_doc.get("preamp_db")

    fr_rmse = None
    notes = "stub — fill in eval harness"
    if fr is not None:
        try:
            if peq_doc is None:
                raise ValueError("fr_rmse_db needs a PEQ JSON (--peq)")
            if not fr.exists():
                raise FileNotFoundError(fr)
            fr_rmse = round(_score_supplied_fr(peq_doc, fr, target_name), 6)
            notes = FIXTURE_RMSE_NOTE
        except Exception as exc:  # noqa: BLE001 — report the failure, do not invent a score
            fr_rmse = None
            err = str(exc)

    return {
        "sample_rate": sample_rate,
        "frame_ms": frame_ms,
        "fr_rmse_db": fr_rmse,
        "peak": peak,
        "preamp_db": preamp_db,
        "latency_budget_ms": latency_budget_ms,
        "notes": notes,
        "error": err,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Export metrics JSON stub.")
    parser.add_argument("--wav", type=Path, default=None)
    parser.add_argument("--peq", type=Path, default=None)
    parser.add_argument("--sample-rate", type=int, default=48000)
    parser.add_argument("--frame-ms", type=float, default=10.0)
    parser.add_argument("--latency-budget-ms", type=float, default=10.0)
    parser.add_argument(
        "--fr",
        type=Path,
        default=None,
        help="FR CSV (freq_hz, level_db). Required to compute fr_rmse_db; otherwise the field stays null.",
    )
    parser.add_argument(
        "--target",
        default="harman_like",
        choices=["harman_like", "harman", "flat"],
        help="Built-in target used only when --fr is set (fixture curve, not an official Harman table)",
    )
    parser.add_argument("-o", "--output", type=Path, default=Path("metrics.json"))
    args = parser.parse_args(argv)

    doc = metrics_stub(
        args.wav,
        args.peq,
        args.sample_rate,
        args.frame_ms,
        args.latency_budget_ms,
        fr=args.fr,
        target_name=args.target,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    rmse = doc["fr_rmse_db"]
    shown = "null" if rmse is None else rmse
    print(f"wrote {args.output} fr_rmse_db={shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
