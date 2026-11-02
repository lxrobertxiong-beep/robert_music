#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 daopeng xiong and contributors
"""Write an objective metrics JSON for the eval harness draft.

Peak is measured from 16-bit PCM when a WAV is given. ``fr_rmse_db`` is the
score for the selected ``--fr-rmse-mode`` (default ``per_bin``, the historical
unsmoothed per-bin dB RMSE). It is filled from an FR CSV when ``--fr`` is set.
``--wav-path-rmse`` is an opt-in alternative: estimate the transfer FR by
sending a WAV (or a synthesized broadband probe) through the PEQ apply path
with the soft limiter off, then Welch-score it against the built-in target.
If both ``--fr`` and ``--wav-path-rmse`` are set, the FR CSV wins.

A computed value is a fixture/objective stub only — not an admission
(不宣称准入) result and not a listening sign-off (非听感定稿).
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


def _ensure_module_path() -> None:
    scripts = Path(__file__).resolve().parent
    module_root = scripts.parent
    for entry in (str(module_root), str(scripts)):
        if entry not in sys.path:
            sys.path.insert(0, entry)


def _score_notes(*, mode: str, source: str, csv_priority: bool) -> str:
    """State which score landed in ``fr_rmse_db``, then the fixture disclaimer."""
    lead = [f"fr_rmse_mode={mode}."]
    if source == "fr_csv":
        if mode == "third_octave":
            lead.append(
                "Aggregated as mean dB on ISO-ish 1/3-octave centers from "
                "20 Hz to 20 kHz, then RMSE versus the same target on those centers."
            )
        else:
            lead.append("Unsmoothed per-bin dB RMSE.")
        lead.append("Score source: FR CSV.")
    else:
        if source == "wav_synth":
            lead.append(
                "Score source: Welch transfer of a synthesized broadband probe "
                "through the PEQ apply path with the soft limiter off, versus "
                "the built-in target."
            )
        else:
            lead.append(
                "Score source: Welch transfer of the supplied WAV through the "
                "PEQ apply path with the soft limiter off, versus the built-in target."
            )
        if mode == "third_octave":
            lead.append(
                "Band scores are mean dB on ISO-ish 1/3-octave centers from "
                "20 Hz to 20 kHz."
            )
    if csv_priority:
        lead.append("FR CSV takes priority over --wav-path-rmse for fr_rmse_db.")
    lead.append(FIXTURE_RMSE_NOTE)
    return " ".join(lead)


def _score_supplied_fr(peq_doc: dict[str, Any], fr: Path, target_name: str, mode: str) -> float:
    _ensure_module_path()
    import generate_peq_from_fr as fr_fit
    from peq import fr_rmse_db as score_fr_rmse_db

    freqs, measured = fr_fit.load_fr_csv(fr)
    target = fr_fit.target_curve(freqs, target_name)
    return float(score_fr_rmse_db(freqs, measured, target, peq_doc, mode=mode))


def _apply_peq_limiter_off(
    samples: list[float],
    src_sr: int,
    peq_doc: dict[str, Any],
    sample_rate: int,
) -> tuple[list[float], list[float]]:
    """PEQ apply path used for scoring. Soft limiter is bypassed.

    Reference is the resampled input (before preamp). Processed audio is
    preamp + biquad cascade with ``limiter_threshold`` set high, matching
    ``apply_peq_wav.py --no-limiter``. The limiter is not part of the score.
    """
    _ensure_module_path()
    from graph import AudioGraph, GraphConfig

    frame = 480
    graph = AudioGraph(
        config=GraphConfig(
            sample_rate=int(sample_rate),
            frame_samples=frame,
            latency_budget_ms=1000.0 * frame / float(sample_rate),
            limiter_threshold=1e9,
            peq=peq_doc,
        )
    )
    reference = graph.resample_boundary(samples, int(src_sr))
    raw_preamp = peq_doc.get("preamp_db", 0.0)
    preamp_db = 0.0 if raw_preamp is None else float(raw_preamp)
    gain = 10.0 ** (preamp_db / 20.0)
    driven = [sample * gain for sample in reference]
    processed = graph.process_buffer(driven, src_sr=int(sample_rate))
    if len(processed) != len(reference):
        raise RuntimeError("PEQ apply path changed the buffer length")
    return reference, processed


def _score_wav_path(
    peq_doc: dict[str, Any],
    samples: list[float],
    src_sr: int,
    sample_rate: int,
    target_name: str,
    mode: str,
) -> float:
    _ensure_module_path()
    import generate_peq_from_fr as fr_fit
    from peq import curve_rmse_db, estimate_transfer_db_welch

    reference, processed = _apply_peq_limiter_off(samples, src_sr, peq_doc, sample_rate)
    freqs, measured = estimate_transfer_db_welch(reference, processed, float(sample_rate))
    target = fr_fit.target_curve(freqs, target_name)
    return float(
        curve_rmse_db(
            freqs,
            measured,
            target,
            mode=mode,
            sample_rate=float(sample_rate),
        )
    )


def _load_wav_or_probe(
    wav: Path | None,
    sample_rate: int,
) -> tuple[list[float], int, str]:
    """Return samples, source rate, and ``wav_file`` or ``wav_synth``."""
    if wav is None:
        _ensure_module_path()
        from peq import synthesize_broadband_probe

        return synthesize_broadband_probe(float(sample_rate)), int(sample_rate), "wav_synth"
    if not wav.exists():
        raise FileNotFoundError(wav)
    _ensure_module_path()
    import apply_peq_wav as wav_io

    samples, src_sr = wav_io.read_wav_mono(wav)
    return samples, int(src_sr), "wav_file"


def metrics_stub(
    wav: Path | None,
    peq: Path | None,
    sample_rate: int,
    frame_ms: float,
    latency_budget_ms: float,
    fr: Path | None = None,
    target_name: str = "harman_like",
    fr_rmse_mode: str = "per_bin",
    wav_path_rmse: bool = False,
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
    fr_mode: str | None = None
    notes = "stub — fill in eval harness"
    csv_priority = fr is not None and wav_path_rmse
    if fr is not None or wav_path_rmse:
        try:
            if peq_doc is None:
                raise ValueError("fr_rmse_db needs a PEQ JSON (--peq)")
            if fr is not None:
                if not fr.exists():
                    raise FileNotFoundError(fr)
                fr_rmse = round(_score_supplied_fr(peq_doc, fr, target_name, fr_rmse_mode), 6)
                source = "fr_csv"
            else:
                samples, src_sr, source = _load_wav_or_probe(wav, sample_rate)
                fr_rmse = round(
                    _score_wav_path(
                        peq_doc,
                        samples,
                        src_sr,
                        sample_rate,
                        target_name,
                        fr_rmse_mode,
                    ),
                    6,
                )
            fr_mode = fr_rmse_mode
            notes = _score_notes(mode=fr_rmse_mode, source=source, csv_priority=csv_priority)
        except Exception as exc:  # noqa: BLE001 — report the failure, do not invent a score
            fr_rmse = None
            fr_mode = None
            err = str(exc)

    return {
        "sample_rate": sample_rate,
        "frame_ms": frame_ms,
        "fr_rmse_db": fr_rmse,
        "fr_rmse_mode": fr_mode,
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
        help=(
            "FR CSV (freq_hz, level_db). Computes fr_rmse_db. "
            "Takes priority over --wav-path-rmse when both are set. "
            "Without --fr and without --wav-path-rmse the field stays null."
        ),
    )
    parser.add_argument(
        "--target",
        default="harman_like",
        choices=["harman_like", "harman", "flat"],
        help="Built-in target used when a score is computed (fixture curve, not an official Harman table)",
    )
    parser.add_argument(
        "--fr-rmse-mode",
        default="per_bin",
        choices=["per_bin", "third_octave"],
        help=(
            "per_bin (default): unsmoothed per-bin dB RMSE. "
            "third_octave: mean dB on ISO-ish 1/3-oct centers from 20 Hz to 20 kHz, "
            "then RMSE versus the same target on those centers."
        ),
    )
    parser.add_argument(
        "--wav-path-rmse",
        action="store_true",
        help=(
            "Estimate FR by sending --wav (or a synthesized broadband probe) "
            "through the PEQ apply path with the soft limiter off, then Welch-score "
            "it against the built-in target. Ignored for fr_rmse_db when --fr is set."
        ),
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
        fr_rmse_mode=args.fr_rmse_mode,
        wav_path_rmse=args.wav_path_rmse,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    rmse = doc["fr_rmse_db"]
    shown = "null" if rmse is None else rmse
    mode = doc["fr_rmse_mode"]
    mode_shown = "null" if mode is None else mode
    print(f"wrote {args.output} fr_rmse_db={shown} fr_rmse_mode={mode_shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
