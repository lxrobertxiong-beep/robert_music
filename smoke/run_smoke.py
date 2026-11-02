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
    plugins = {item["id"]: item for item in registry.get("plugins", [])}
    call_nr = plugins.get("call-nr")
    if not call_nr or call_nr.get("local_path") != "algo/call-nr":
        print("call-nr local_path must be in-repo algo/call-nr", file=sys.stderr)
        return 1
    plugin_root = ROOT / "algo" / "call-nr"
    if not (plugin_root / "PLUGIN.json").is_file():
        print("missing algo/call-nr/PLUGIN.json", file=sys.stderr)
        return 1
    for entry in call_nr.get("entrypoints", []):
        rel = entry.get("path", "")
        if rel.startswith("/") or not (plugin_root / rel).is_file():
            print(f"call-nr entrypoint not in repo: {rel}", file=sys.stderr)
            return 1
    if "algo/call-nr" not in map_text or "/workspace/m1-call-nr" in map_text:
        print("JOB_ENTRYPOINT_MAP call-nr workdir is not in-repo", file=sys.stderr)
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
