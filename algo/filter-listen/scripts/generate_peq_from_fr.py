#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 daopeng xiong and contributors
"""Offline: measurement FR CSV + target -> portable PEQ JSON.

AutoEq (MIT) is optional and never vendored. Without it, or with
``--no-autoeq``, a deterministic stdlib peaking-EQ stub still emits a
document that matches ``configs/peq_schema.json``.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import math
from collections.abc import Sequence
from pathlib import Path


def load_fr_csv(path: Path) -> tuple[list[float], list[float]]:
    """Load frequency_hz, level_db from CSV (header optional)."""
    freqs: list[float] = []
    levels: list[float] = []
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        raise ValueError(f"empty FR CSV: {path}")
    start = 0
    if rows[0] and not _is_float(rows[0][0]):
        start = 1
    for row in rows[start:]:
        if len(row) < 2 or not row[0].strip():
            continue
        freqs.append(float(row[0]))
        levels.append(float(row[1]))
    return freqs, levels


def _is_float(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def target_curve(freqs: Sequence[float], name: str) -> list[float]:
    """Simple built-in targets (examples, not official Harman tables)."""
    name = name.lower()
    if name in ("flat", "none"):
        return [0.0 for _ in freqs]
    if name in ("harman_like", "harman"):
        # Synthetic gentle bass shelf + slight presence — example only.
        curve: list[float] = []
        log_presence = math.log10(3000.0)
        for freq in freqs:
            bass = 4.0 / (1.0 + (freq / 120.0) ** 2)
            log_freq = math.log10(freq + 1e-9)
            presence = 1.5 * math.exp(-0.5 * ((log_freq - log_presence) / 0.35) ** 2)
            tilt = -0.5 * math.log10(max(freq, 20.0) / 1000.0)
            curve.append(bass + presence + tilt)
        return curve
    raise ValueError(f"unknown target: {name}")


def try_autoeq(
    freqs: Sequence[float],
    measured: Sequence[float],
    target: Sequence[float],
    n_filters: int,
) -> list[dict] | None:
    """Return band dicts only if AutoEq can be parsed confidently.

    The public AutoEq API moves between releases. This skeleton detects the
    import and then falls through to the deterministic stub so CI stays stable.
    """
    del freqs, measured, target, n_filters
    try:
        importlib.import_module("autoeq.frequency_response")
    except ImportError:
        return None
    return None


def fit_peaking_stub(
    freqs: Sequence[float],
    error_db: Sequence[float],
    n_filters: int,
    fs: float,
) -> list[dict]:
    """Greedy peaking EQ stub: place bands at the largest |error| frequencies."""
    hi = min(16000.0, 0.45 * fs)
    selected_f: list[float] = []
    selected_e: list[float] = []
    for freq, error in zip(freqs, error_db):
        if 40.0 <= freq <= hi:
            selected_f.append(float(freq))
            selected_e.append(float(error))
    if not selected_f:
        return []

    errors = selected_e[:]
    bands: list[dict] = []
    for _ in range(max(1, n_filters)):
        index = max(range(len(errors)), key=lambda i: abs(errors[i]))
        fc = float(selected_f[index])
        gain = max(-12.0, min(12.0, errors[index]))
        quality = 1.2
        bands.append(
            {
                "fc": round(fc, 2),
                "Q": quality,
                "gain": round(-gain, 3),
                "type": "peaking",
            }
        )
        width = max(0.15, 1.0 / quality)
        log_fc = math.log10(fc)
        updated: list[float] = []
        for freq, error in zip(selected_f, errors):
            weight = (math.log10(freq) - log_fc) / width
            updated.append(error - gain * math.exp(-0.5 * weight * weight))
        errors = updated
    return bands


def build_peq(
    fr_path: Path,
    target_name: str,
    n_filters: int,
    sample_rate: float,
    prefer_autoeq: bool,
) -> dict:
    freqs, measured = load_fr_csv(fr_path)
    target = target_curve(freqs, target_name)
    error = [meas - tgt for meas, tgt in zip(measured, target)]

    bands = None
    generator = "stdlib_peaking_stub"
    if prefer_autoeq:
        bands = try_autoeq(freqs, measured, target, n_filters)
        if bands is not None:
            generator = "autoeq"

    if bands is None:
        bands = fit_peaking_stub(freqs, error, n_filters, sample_rate)

    max_boost = max((band["gain"] for band in bands if band["gain"] > 0), default=0.0)
    preamp = -max_boost if max_boost > 0 else 0.0

    return {
        "name": f"compensation_{target_name}",
        "sample_rate": int(sample_rate),
        "preamp_db": round(preamp, 3),
        "bands": bands,
        "meta": {
            "target": target_name,
            "source_fr": str(fr_path),
            "generator": generator,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate portable PEQ JSON from FR CSV + target curve."
    )
    parser.add_argument("--fr", type=Path, required=False, help="Input FR CSV (freq_hz, level_db)")
    parser.add_argument(
        "--target",
        default="harman_like",
        choices=["harman_like", "harman", "flat"],
        help="Built-in example target",
    )
    parser.add_argument("--n-filters", type=int, default=5)
    parser.add_argument("--sample-rate", type=float, default=48000.0)
    parser.add_argument("-o", "--output", type=Path, default=Path("compensation.json"))
    parser.add_argument(
        "--no-autoeq",
        action="store_true",
        help="Skip AutoEq even if installed; use the stdlib peaking stub",
    )
    args = parser.parse_args(argv)

    if args.fr is None:
        parser.print_help()
        return 0

    doc = build_peq(
        args.fr,
        args.target,
        args.n_filters,
        args.sample_rate,
        prefer_autoeq=not args.no_autoeq,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {args.output} ({len(doc['bands'])} bands, generator={doc['meta']['generator']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
