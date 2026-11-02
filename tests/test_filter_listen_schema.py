# SPDX-License-Identifier: Apache-2.0
"""peq_schema stability and control-plane path checks for filter-listen."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "algo" / "filter-listen"


def test_peq_schema_field_names_stable():
    schema = json.loads((MODULE / "configs" / "peq_schema.json").read_text(encoding="utf-8"))
    assert schema["required"] == ["sample_rate", "bands"]
    band = schema["properties"]["bands"]["items"]
    assert band["required"] == ["fc", "Q", "gain", "type"]
    assert band["properties"]["type"]["enum"] == [
        "peaking",
        "lowshelf",
        "highshelf",
        "lowpass",
        "highpass",
    ]
    example = json.loads(
        (MODULE / "configs" / "example_compensation.json").read_text(encoding="utf-8")
    )
    assert example["sample_rate"] == 48000
    assert example["bands"]
    for item in example["bands"]:
        assert set(item) == {"fc", "Q", "gain", "type"}


def test_registry_points_at_in_repo_module():
    registry = json.loads(
        (ROOT / "control" / "plugin-registry.example.json").read_text(encoding="utf-8")
    )
    plugin = next(item for item in registry["plugins"] if item["id"] == "filter-listen")
    assert plugin["local_path"] == "algo/filter-listen"
    assert "oss-ai-filter-listen" not in plugin["local_path"]
    assert "not pushed" not in plugin["license"]["notes"].lower()
    assert plugin["task_bindings"] == ["export_peq"]
    names = {item["name"]: item["path"] for item in plugin["entrypoints"]}
    assert names["generate_peq_from_fr"] == "scripts/generate_peq_from_fr.py"
    assert names["apply_peq_wav"] == "scripts/apply_peq_wav.py"
    assert names["export_metrics"] == "scripts/export_metrics.py"
    never = plugin["oss_boundary"]["never_bundle"]
    assert "/home/box/private/jieli/" in never
    assert "**/DynamicEQPro.a" in never
    assert "**/*.key" in never
    assert "**/*.fw" in never
    assert plugin["configs"] == [
        "configs/peq_schema.json",
        "configs/graph_48k_10ms.yaml",
    ]


def test_job_map_and_stub_use_repo_relative_workdir():
    text = (ROOT / "control" / "JOB_ENTRYPOINT_MAP.md").read_text(encoding="utf-8")
    assert "export_peq" in text
    assert "algo/filter-listen" in text
    assert "/workspace/oss-ai-filter-listen" not in text

    spec = importlib.util.spec_from_file_location(
        "stub_server_for_filter_listen",
        ROOT / "control" / "stub_server.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    resolved = module.resolve_entrypoint(
        "export_peq",
        "filter-listen",
        {
            "fr": "testdata/synthetic_fr.csv",
            "target": "harman_like",
            "output": "/tmp/peq.json",
            "no_autoeq": True,
        },
        {"pins": []},
    )
    assert resolved["workdir"] == "algo/filter-listen"
    assert resolved["dry_run"] is True
    assert resolved["command"][:4] == [
        "python3",
        "scripts/generate_peq_from_fr.py",
        "--fr",
        "testdata/synthetic_fr.csv",
    ]
    assert "--no-autoeq" in resolved["command"]
    assert resolved["follow_on"][0]["script"] == "scripts/apply_peq_wav.py"
