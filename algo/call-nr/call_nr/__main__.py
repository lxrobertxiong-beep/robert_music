"""``python -m call_nr`` entry (package root must be on ``PYTHONPATH``)."""

from __future__ import annotations

import sys

from call_nr.cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
