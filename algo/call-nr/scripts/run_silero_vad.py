#!/usr/bin/env python3
"""Silero VAD CLI. See ``call_nr.backends.silero_vad`` for the pin and weight path."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from call_nr.backends.silero_vad import main

if __name__ == "__main__":
    raise SystemExit(main())
