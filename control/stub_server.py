#!/usr/bin/env python3
"""Minimal local stub: serve plugin-registry + resolve create_job→entrypoint on :8765.

Default: dry-run only (resolve mapping, never spawn subprocesses).
No auth, no secrets. Do not invent metrics.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / "plugin-registry.example.json"
HOST, PORT = "127.0.0.1", 8765
TZ = timezone(timedelta(hours=8))

_JOBS: dict[str, dict] = {}

# Hard mapping (must stay aligned with JOB_ENTRYPOINT_MAP.md)
ENTRYPOINT_MAP = {
    ("export_peq", "filter-listen"): {
        "workdir": "algo/filter-listen",
        "script": "scripts/generate_peq_from_fr.py",
        "interpreter": "python3",
        "follow_on": [
            {
                "name": "apply_peq_wav",
                "script": "scripts/apply_peq_wav.py",
                "args_hint": "--wav {wav} --peq {peq} -o {out_wav}",
            },
            {
                "name": "export_metrics",
                "script": "scripts/export_metrics.py",
                "args_hint": "--wav {wav} --peq {peq} -o {metrics}",
            },
        ],
    },
    ("run_eval", "call-nr"): {
        # Restricted eval repo name, not an in-repo path. The stub never executes it.
        "workdir": "audio-algo-eval",
        "script": "scripts/run_vbd_eval.py",
        "interpreter": "python3",
        "algo_weld": "algo/call-nr",
        "follow_on": [],
    },
    ("pin_version", "call-nr"): {
        "workdir": "algo/call-nr",
        "script": "scripts/setup_pins.sh",
        "interpreter": "bash",
        "follow_on": [],
    },
}


def _now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def resolve_entrypoint(
    jtype: str, plugin_id: str, params: dict, plugin: dict
) -> dict:
    """Build resolved_entrypoint from hard map + request params. Never executes."""
    key = (jtype, plugin_id)
    spec = ENTRYPOINT_MAP.get(key)
    if not spec:
        raise KeyError(f"no entrypoint map for {key}")

    workdir = spec["workdir"]
    script = spec["script"]
    interp = spec["interpreter"]
    command: list[str]
    template: str

    if jtype == "export_peq":
        fr = params.get("fr", "testdata/synthetic_fr.csv")
        target = params.get("target", "harman_like")
        output = params.get("output", "/tmp/peq.json")
        no_autoeq = bool(params.get("no_autoeq", False))
        command = [interp, script, "--fr", str(fr), "--target", str(target)]
        if no_autoeq:
            command.append("--no-autoeq")
        command.extend(["-o", str(output)])
        template = (
            f"{interp} {script} --fr {fr} --target {target}"
            f"{' --no-autoeq' if no_autoeq else ''} -o {output}"
        )
    elif jtype == "run_eval":
        baseline = params.get("baseline", "rnnoise")
        command = [interp, script, "--baseline", str(baseline)]
        if "config" in params:
            command.extend(["--config", str(params["config"])])
        template = " ".join(command)
    elif jtype == "pin_version":
        command = [interp, script]
        template = f"{interp} {script}"
    else:
        raise KeyError(jtype)

    resolved: dict = {
        "workdir": workdir,
        "command": command,
        "command_template": template,
        "dry_run": True,
        "follow_on": list(spec.get("follow_on") or []),
    }
    if "algo_weld" in spec:
        resolved["algo_weld"] = spec["algo_weld"]

    if jtype == "pin_version":
        pins = plugin.get("pins") or []
        resolved["resolved_pins"] = [
            {
                "name": p.get("name"),
                "version": p.get("version"),
                "ref": p.get("ref"),
                "report_name": p.get("report_name")
                or f"{p.get('name')}@{p.get('version')}",
            }
            for p in pins
        ]
        # optional override from params.pins
        if params.get("pins"):
            resolved["requested_pins"] = params["pins"]

    return resolved


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # quieter
        print(f"[stub] {self.command} {self.path} -> {fmt % args}")

    def _send(self, code: int, body: dict | list) -> None:
        raw = json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        reg = load_registry()
        plugins = {p["id"]: p for p in reg.get("plugins", [])}

        if path == "/v1/plugins":
            self._send(
                200,
                {
                    "schema_version": reg.get("schema_version", "0.1.0"),
                    "plugins": [
                        {
                            "id": p["id"],
                            "display_name": p.get("display_name"),
                            "task_bindings": p.get("task_bindings", []),
                        }
                        for p in reg.get("plugins", [])
                    ],
                },
            )
            return

        if path.startswith("/v1/plugins/"):
            pid = path.split("/v1/plugins/", 1)[1]
            if pid in plugins:
                self._send(200, plugins[pid])
            else:
                self._send(404, {"error": "unknown_plugin", "id": pid})
            return

        if path.startswith("/v1/jobs/"):
            jid = path.split("/v1/jobs/", 1)[1]
            job = _JOBS.get(jid)
            if job:
                self._send(200, job)
            else:
                self._send(404, {"error": "unknown_job", "id": jid})
            return

        if path.startswith("/v1/devices/"):
            did = path.split("/v1/devices/", 1)[1]
            if did == "call-nr-baselines" and "call-nr" in plugins:
                pins = [
                    x.get("report_name") or f"{x.get('name')}@{x.get('version')}"
                    for x in plugins["call-nr"].get("pins", [])
                ]
                self._send(
                    200,
                    {
                        "id": did,
                        "kind": "pin_target",
                        "plugin_id": "call-nr",
                        "pins": pins,
                        "note": "本地草案；无真实设备会话",
                    },
                )
            else:
                self._send(404, {"error": "unknown_device", "id": did})
            return

        self._send(
            404,
            {
                "error": "not_found",
                "hint": "GET /v1/plugins | /v1/plugins/{id} | /v1/jobs/{id} | /v1/devices/{id}",
            },
        )

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)
        execute_raw = (qs.get("execute") or ["false"])[0].lower()
        execute = execute_raw in ("1", "true", "yes")

        if path != "/v1/jobs":
            self._send(404, {"error": "not_found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid_json"})
            return

        allowed = {"run_eval", "export_peq", "pin_version"}
        jtype = body.get("type")
        plugin_id = body.get("plugin_id")
        if jtype not in allowed:
            self._send(400, {"error": "invalid_type", "allowed": sorted(allowed)})
            return
        reg = load_registry()
        plugins = {p["id"]: p for p in reg.get("plugins", [])}
        if plugin_id not in plugins:
            self._send(400, {"error": "unknown_plugin", "id": plugin_id})
            return
        bindings = set(plugins[plugin_id].get("task_bindings", []))
        if jtype not in bindings:
            self._send(
                400,
                {
                    "error": "plugin_task_mismatch",
                    "plugin_id": plugin_id,
                    "type": jtype,
                    "task_bindings": sorted(bindings),
                },
            )
            return

        if execute:
            # Prefer resolve-only; refuse real execution in this stub.
            self._send(
                400,
                {
                    "error": "execute_disabled",
                    "message": (
                        "stub only resolves entrypoints; subprocess execution "
                        "is disabled. Omit execute or use execute=false."
                    ),
                    "hint": "See JOB_ENTRYPOINT_MAP.md",
                },
            )
            return

        params = body.get("params") or {}
        try:
            resolved = resolve_entrypoint(jtype, plugin_id, params, plugins[plugin_id])
        except KeyError as exc:
            self._send(
                400,
                {"error": "entrypoint_unmapped", "detail": str(exc)},
            )
            return

        jid = "job_" + uuid.uuid4().hex[:12]
        job = {
            "id": jid,
            "type": jtype,
            "plugin_id": plugin_id,
            "status": "queued",
            "created_at": _now(),
            "params": params,
            "resolved_entrypoint": resolved,
            "result": None,
            "note": "stub dry-run — resolved entrypoint only; does not execute plugins",
        }
        _JOBS[jid] = job
        self._send(201, job)


def main() -> None:
    if not REGISTRY_PATH.is_file():
        raise SystemExit(f"missing {REGISTRY_PATH}")
    httpd = HTTPServer((HOST, PORT), Handler)
    print(f"control-platform stub on http://{HOST}:{PORT}  (registry={REGISTRY_PATH})")
    print("POST /v1/jobs resolves entrypoints (dry-run default; execute=true refused)")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
