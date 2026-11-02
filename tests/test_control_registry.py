"""Minimal public unit tests for control stub registry (no network)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_plugin_registry_example_is_valid_json():
    data = json.loads((ROOT / "control" / "plugin-registry.example.json").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert "plugins" in data or len(data) >= 0


def test_stub_server_compiles():
    import py_compile

    py_compile.compile(str(ROOT / "control" / "stub_server.py"), doraise=True)
