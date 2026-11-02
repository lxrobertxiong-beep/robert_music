#!/usr/bin/env python3
"""In-repo CLI: ``python algo/call-nr/scripts/infer.py --backend identity -i in.wav -o out.wav``."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from call_nr.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
