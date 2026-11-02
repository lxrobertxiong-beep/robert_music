#!/usr/bin/env python3
"""P0 smoke: import stub + dry-run create_job mapping without HTTP long-run."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "control"))


def main() -> int:
    registry = json.loads((ROOT / "control" / "plugin-registry.example.json").read_text(encoding="utf-8"))
    assert registry is not None
    map_text = (ROOT / "control" / "JOB_ENTRYPOINT_MAP.md").read_text(encoding="utf-8")
    for key in ("run_eval", "export_peq", "pin_version"):
        if key not in map_text:
            print(f"missing map key: {key}", file=sys.stderr)
            return 1
    spec = importlib.util.spec_from_file_location(
        "stub_server", ROOT / "control" / "stub_server.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print("smoke ok: registry + JOB_ENTRYPOINT_MAP + stub_server import")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
