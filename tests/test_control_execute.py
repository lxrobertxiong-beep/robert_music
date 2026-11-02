# SPDX-License-Identifier: Apache-2.0
"""Local execute=true for export_peq and pin_version; run_eval stays refused."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _stub():
    sys.path.insert(0, str(ROOT / "control"))
    import stub_server

    return stub_server


def test_dry_run_does_not_spawn_or_write(tmp_path: Path):
    stub_server = _stub()
    out = tmp_path / "peq.json"
    code, job = stub_server.create_job(
        {
            "type": "export_peq",
            "plugin_id": "filter-listen",
            "params": {
                "fr": "testdata/synthetic_fr.csv",
                "target": "harman_like",
                "output": str(out),
            },
        },
        execute=False,
    )
    assert code == 201
    assert job["status"] == "queued"
    assert job["result"] is None
    assert job["resolved_entrypoint"]["dry_run"] is True
    assert job["resolved_entrypoint"]["local_execute"] is True
    assert "--no-autoeq" in job["resolved_entrypoint"]["command"]
    assert not out.exists()


def test_execute_export_peq_synthetic_fr(tmp_path: Path):
    stub_server = _stub()
    out = tmp_path / "nested" / "peq.json"
    code, job = stub_server.create_job(
        {
            "type": "export_peq",
            "plugin_id": "filter-listen",
            "params": {
                "fr": "testdata/synthetic_fr.csv",
                "target": "harman_like",
                "output": str(out),
            },
        },
        execute=True,
    )
    assert code == 201
    assert job["status"] == "succeeded"
    assert job["exit_code"] == 0
    assert job["resolved_entrypoint"]["dry_run"] is False
    assert job["resolved_entrypoint"]["workdir"] == "algo/filter-listen"
    assert job["result"]["exit_code"] == 0
    assert job["result"]["timed_out"] is False
    assert "wrote" in job["stdout_summary"]
    assert job["stderr_summary"] == ""
    assert out.is_file()
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["sample_rate"] == 48000
    assert doc["bands"]
    assert doc["meta"]["generator"] == "stdlib_peaking_stub"
    assert "testdata/synthetic_fr.csv" in doc["meta"]["source_fr"]


def test_execute_pin_version_prints_metadata_without_download():
    stub_server = _stub()
    code, job = stub_server.create_job(
        {"type": "pin_version", "plugin_id": "call-nr", "params": {}},
        execute=True,
    )
    assert code == 201
    assert job["status"] == "succeeded"
    assert job["exit_code"] == 0
    assert job["resolved_entrypoint"]["dry_run"] is False
    assert job["resolved_entrypoint"]["command"] == [
        "bash",
        "scripts/setup_pins.sh",
    ]
    text = job["stdout_summary"]
    assert "no weights downloaded" in text
    assert "GTCRN" in text
    assert "Silero VAD" in text
    assert "RNNoise" in text
    names = {pin["name"] for pin in job["resolved_entrypoint"]["resolved_pins"]}
    assert names == {"RNNoise", "DeepFilterNet3", "GTCRN", "Silero VAD"}


def test_execute_run_eval_stays_400():
    stub_server = _stub()
    code, body = stub_server.create_job(
        {
            "type": "run_eval",
            "plugin_id": "call-nr",
            "params": {"baseline": "rnnoise"},
        },
        execute=True,
    )
    assert code == 400
    assert body["error"] == "execute_disabled"
    assert "audio-algo-eval" in body["message"]


def test_run_eval_dry_run_still_resolves():
    stub_server = _stub()
    code, job = stub_server.create_job(
        {
            "type": "run_eval",
            "plugin_id": "call-nr",
            "params": {"baseline": "rnnoise"},
        },
        execute=False,
    )
    assert code == 201
    assert job["resolved_entrypoint"]["dry_run"] is True
    assert job["resolved_entrypoint"]["local_execute"] is False
    assert job["resolved_entrypoint"]["workdir"] == "audio-algo-eval"
    assert job["resolved_entrypoint"]["algo_weld"] == "algo/call-nr"


def test_explicit_no_autoeq_false_omits_flag():
    stub_server = _stub()
    resolved = stub_server.resolve_entrypoint(
        "export_peq",
        "filter-listen",
        {"fr": "testdata/synthetic_fr.csv", "no_autoeq": False},
        {},
    )
    assert "--no-autoeq" not in resolved["command"]
    assert resolved["dry_run"] is True
