"""Registry and job-map point call-nr at the in-repo tree."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "control" / "plugin-registry.example.json"
JOB_MAP = ROOT / "control" / "JOB_ENTRYPOINT_MAP.md"
PLUGIN_JSON = ROOT / "algo" / "call-nr" / "PLUGIN.json"


def _load_call_nr() -> dict:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return next(plugin for plugin in data["plugins"] if plugin["id"] == "call-nr")


def test_registry_call_nr_is_in_repo_relative():
    plugin = _load_call_nr()
    assert plugin["local_path"] == "algo/call-nr"
    assert not Path(plugin["local_path"]).is_absolute()
    root = ROOT / plugin["local_path"]
    assert (root / "PLUGIN.json").is_file()
    names = {item["name"] for item in plugin["entrypoints"]}
    assert {"infer", "setup_pins"} <= names
    for item in plugin["entrypoints"]:
        rel = item["path"]
        assert not rel.startswith("/")
        assert (root / rel).is_file()
    never = plugin["oss_boundary"]["never_bundle"]
    joined = "\n".join(never)
    assert "DynamicEQPro.a" in joined
    assert "**/*.fw" in never
    assert any("jieli" in item for item in never)
    scrubbed = dict(plugin)
    scrubbed["oss_boundary"] = {
        **plugin["oss_boundary"],
        "never_bundle": [],
    }
    blob = json.dumps(scrubbed)
    assert "/workspace/m1-call-nr" not in blob
    assert "/workspace/call-nr-eval" not in blob
    assert "/home/" not in blob
    assert "/workspace/" not in blob


def test_plugin_json_pins_match_registry():
    plugin = _load_call_nr()
    meta = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    assert meta["id"] == "call-nr"
    assert meta["contracts"]["A"]["implemented"] is True
    assert meta["contracts"]["B"]["implemented"] is False
    by_name = {pin["name"]: pin for pin in meta["pins"]}
    assert by_name["RNNoise"]["ref"] == "904a876dce1f9ab8860c0a5000ed151f9f6eef58"
    assert "978576aa8400552a4ce9730838c635aa30db5e61" in by_name["DeepFilterNet3"]["ref"]
    assert by_name["GTCRN"]["ref"] == "502ebfab64da7c4a9af78dcb9c6ceef1ebb01c73"
    assert by_name["Silero VAD"]["ref"] == "066409f3d9db45a30d21dfcbf9147826ffdd7052"
    assert by_name["GTCRN"]["checkpoint"] == "checkpoints/model_trained_on_dns3.tar"
    assert "CALL_NR_GTCRN_WEIGHTS" in by_name["GTCRN"]["weights_env"]
    assert by_name["Silero VAD"]["code_env"] == "SILERO_VAD_ROOT"
    reg_by_name = {pin["name"]: pin for pin in plugin["pins"]}
    assert by_name["RNNoise"]["ref"] in reg_by_name["RNNoise"]["ref"]
    assert by_name["DeepFilterNet3"]["ref"] in reg_by_name["DeepFilterNet3"]["ref"]
    assert by_name["GTCRN"]["ref"] in reg_by_name["GTCRN"]["ref"]
    assert by_name["Silero VAD"]["ref"] in reg_by_name["Silero VAD"]["ref"]


def test_job_map_and_stub_use_in_repo_algorithm_workdir():
    text = JOB_MAP.read_text(encoding="utf-8")
    assert "algo/call-nr" in text
    assert "/workspace/m1-call-nr" not in text
    sys.path.insert(0, str(ROOT / "control"))
    import stub_server

    pin = stub_server.ENTRYPOINT_MAP[("pin_version", "call-nr")]
    assert pin["workdir"] == "algo/call-nr"
    assert pin["script"] == "scripts/setup_pins.sh"
    assert pin["interpreter"] == "bash"
    evaluated = stub_server.ENTRYPOINT_MAP[("run_eval", "call-nr")]
    assert evaluated["algo_weld"] == "algo/call-nr"
    assert not str(evaluated["workdir"]).startswith("/")
    assert "call-nr-eval" not in str(evaluated["workdir"])
    resolved = stub_server.resolve_entrypoint(
        "pin_version",
        "call-nr",
        {},
        {"pins": [{"name": "RNNoise", "version": "v0.2", "ref": "904a876"}]},
    )
    assert resolved["workdir"] == "algo/call-nr"
    assert resolved["dry_run"] is True
    assert resolved["command"][0] == "bash"
    assert resolved["resolved_pins"][0]["report_name"] == "RNNoise@v0.2"
