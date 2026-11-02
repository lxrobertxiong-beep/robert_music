"""Minimal inference CLI for the call-nr skeleton.

Output is always contract A: 48 kHz mono float32 WAV. Non-48 kHz input
is resampled with soxr inside ``to_contract_a``. Channels are averaged
to mono before that step.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from call_nr.backends import get_backend
from call_nr.contract import CONTRACT_A_ID, SAMPLE_RATE_A
from call_nr.io import read_wav, to_contract_a, write_wav
from call_nr.pipeline import BackendUnavailable

_CHOICES = ("identity", "passthrough", "rnnoise", "deepfilternet")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="call-nr-infer",
        description=(
            "Run a call-nr backend on a WAV file. "
            f"identity needs no third-party binary and writes contract {CONTRACT_A_ID}."
        ),
    )
    parser.add_argument(
        "--backend",
        required=True,
        choices=_CHOICES,
        help="identity and passthrough are built in; rnnoise and deepfilternet are optional pins",
    )
    parser.add_argument("-i", "--input", required=True, type=Path, help="input WAV")
    parser.add_argument("-o", "--output", required=True, type=Path, help="output WAV (contract A)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.input.is_file():
        print(f"input not found: {args.input}", file=sys.stderr)
        return 2
    try:
        samples, sample_rate = read_wav(args.input)
        contract_a = to_contract_a(samples, sample_rate)
        backend = get_backend(args.backend)
        backend.reset()
        rendered = backend.process(contract_a, SAMPLE_RATE_A)
        write_wav(args.output, rendered, SAMPLE_RATE_A)
    except BackendUnavailable as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(
        f"wrote {args.output} contract={CONTRACT_A_ID} backend={args.backend} "
        f"samples={len(rendered)} sr={SAMPLE_RATE_A}",
        file=sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
