"""Put the in-repo call-nr package on sys.path for unit tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "algo" / "call-nr"
plugin_path = str(PLUGIN_ROOT)
if plugin_path not in sys.path:
    sys.path.insert(0, plugin_path)
