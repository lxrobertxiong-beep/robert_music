#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 daopeng xiong and contributors
"""Apply PEQ JSON to a WAV using the frame-aware graph path.

Frame path: resample boundary (if needed) → PEQ cascade in frames of 480 → soft limiter.
PCM I/O uses the stdlib ``wave`` module (16-bit). NumPy/soundfile are not required.
The soft limiter remains an engineering stub (非听感定稿).
"""

from __future__ import annotations

import argparse
import array
import json
import sys
import wave
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parents[1]
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))


def read_wav_mono(path: Path) -> tuple[list[float], int]:
    """Read 16-bit PCM WAV and downmix to mono float samples in [-1, 1]."""
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        sample_rate = handle.getframerate()
        nframes = handle.getnframes()
        raw = handle.readframes(nframes)
    if sample_width != 2:
        raise ValueError(
            f"skeleton WAV path supports 16-bit PCM only (got sampwidth={sample_width})"
        )
    pcm = array.array("h")
    pcm.frombytes(raw)
    if sys.byteorder != "little":
        pcm.byteswap()
    if channels == 1:
        return [sample / 32768.0 for sample in pcm], sample_rate
    mono: list[float] = []
    for index in range(0, len(pcm), channels):
        acc = 0.0
        for ch in range(channels):
            acc += pcm[index + ch]
        mono.append(acc / channels / 32768.0)
    return mono, sample_rate


def write_wav_mono(path: Path, samples: list[float], sample_rate: int) -> None:
    pcm = array.array("h")
    for sample in samples:
        clipped = max(-1.0, min(1.0, float(sample)))
        pcm.append(round(clipped * 32767.0))
    if sys.byteorder != "little":
        pcm.byteswap()
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())


def apply_peq_document(
    samples: list[float],
    src_sr: int,
    peq_doc: dict,
    *,
    sample_rate: int = 48000,
    frame: int = 480,
    limiter: bool = True,
) -> tuple[list[float], int]:
    """Apply one PortablePEQ document with the frame-aware graph.

    Same steps as the CLI: preamp, optional resample to ``sample_rate``,
    PEQ cascade in frames of ``frame``, then the soft limiter stub
    (非听感定稿) unless ``limiter`` is false. Returns samples and the
    number of biquad sections actually built.
    """
    from graph import AudioGraph, GraphConfig

    cfg = GraphConfig(
        sample_rate=sample_rate,
        frame_samples=frame,
        latency_budget_ms=1000.0 * frame / sample_rate,
        limiter_threshold=0.98 if limiter else 1e9,
        peq=peq_doc,
    )
    graph = AudioGraph(config=cfg)
    preamp_db = float(peq_doc.get("preamp_db", 0.0))
    gain = 10.0 ** (preamp_db / 20.0)
    scaled = [sample * gain for sample in samples]
    rendered = graph.process_buffer(scaled, src_sr=src_sr)
    n_bands = 0 if graph.peq is None else len(graph.peq.filters)
    return rendered, n_bands


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Apply portable PEQ JSON to WAV (48k frame-aware).")
    parser.add_argument("--wav", type=Path, required=True)
    parser.add_argument("--peq", type=Path, required=True, help="PEQ JSON (peq_schema)")
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--sample-rate", type=int, default=48000)
    parser.add_argument("--frame", type=int, default=480, help="Frame size (samples); 480 = 10ms@48k")
    parser.add_argument("--no-limiter", action="store_true")
    args = parser.parse_args(argv)

    mono, src_sr = read_wav_mono(args.wav)
    peq_doc = json.loads(args.peq.read_text(encoding="utf-8"))
    output, n_bands = apply_peq_document(
        mono,
        src_sr,
        peq_doc,
        sample_rate=args.sample_rate,
        frame=args.frame,
        limiter=not args.no_limiter,
    )
    write_wav_mono(args.output, output, args.sample_rate)
    print(
        f"wrote {args.output} sr={args.sample_rate} frame={args.frame} "
        f"in_sr={src_sr} n={len(output)} peq_bands={n_bands}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
