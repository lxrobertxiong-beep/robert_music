#!/usr/bin/env python3
"""Minimal local stub: serve plugin-registry + resolve create_job→entrypoint on :8765.

Default: dry-run (resolve the mapping, do not spawn a subprocess).
``execute=true`` runs only the local-safe entrypoints:

- ``export_peq`` + ``filter-listen`` → ``scripts/generate_peq_from_fr.py``
- ``pin_version`` + ``call-nr`` → ``scripts/setup_pins.sh`` (metadata only)

``run_eval`` stays resolve-only: the eval tree is the restricted
``audio-algo-eval`` repo and is not vendored here. No auth, no secrets,
no weight downloads. Do not invent metrics.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
REGISTRY_PATH = ROOT / "plugin-registry.example.json"
HOST, PORT = "127.0.0.1", 8765
TZ = timezone(timedelta(hours=8))
EXECUTE_TIMEOUT_S = 20
OUTPUT_LIMIT = 2048
ALLOWED_INTERPRETERS = frozenset({"python3", "bash"})

_JOBS: dict[str, dict] = {}

# Hard mapping (must stay aligned with JOB_ENTRYPOINT_MAP.md).
# local_execute is the only set the stub may subprocess.
ENTRYPOINT_MAP = {
    ("export_peq", "filter-listen"): {
        "workdir": "algo/filter-listen",
        "script": "scripts/generate_peq_from_fr.py",
        "interpreter": "python3",
        "local_execute": True,
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
        # Restricted eval repo name, not an in-repo path. Never executed.
        "workdir": "audio-algo-eval",
        "script": "scripts/run_vbd_eval.py",
        "interpreter": "python3",
        "local_execute": False,
        "algo_weld": "algo/call-nr",
        "follow_on": [],
    },
    ("pin_version", "call-nr"): {
        "workdir": "algo/call-nr",
        "script": "scripts/setup_pins.sh",
        "interpreter": "bash",
        "local_execute": True,
        "follow_on": [],
    },
}


def _now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _no_autoeq(params: dict) -> bool:
    """Control-plane default is --no-autoeq so execute does not need AutoEq.

    Pass ``no_autoeq: false`` to omit the flag. The generator still falls
    back to the stdlib stub when AutoEq is missing.
    """
    if "no_autoeq" not in params:
        return True
    value = params["no_autoeq"]
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes")
    return bool(value)


def resolve_entrypoint(
    jtype: str, plugin_id: str, params: dict, plugin: dict
) -> dict:
    """Build resolved_entrypoint from the hard map + request params.

    This function never executes. ``dry_run`` stays true; ``create_job``
    flips it only after a local subprocess is actually launched.
    """
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
        no_autoeq = _no_autoeq(params)
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
        # Pins are echoed in JSON. They are not shell arguments.
        command = [interp, script]
        template = f"{interp} {script}"
    else:
        raise KeyError(jtype)

    resolved: dict = {
        "workdir": workdir,
        "command": command,
        "command_template": template,
        "dry_run": True,
        "local_execute": bool(spec.get("local_execute")),
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
        if params.get("pins"):
            resolved["requested_pins"] = params["pins"]

    return resolved


def _truncate(text: str, limit: int = OUTPUT_LIMIT) -> str:
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return text[:limit] + f"\n…[truncated {omitted} chars]"


def _repo_workdir(rel: str) -> Path:
    """Resolve a workdir that must stay inside the repository root."""
    if not isinstance(rel, str) or not rel or rel.startswith(("/", "\\")):
        raise ValueError(f"workdir must be repo-relative: {rel!r}")
    parts = Path(rel).parts
    if not parts or ".." in parts or Path(rel).is_absolute():
        raise ValueError(f"workdir must be repo-relative: {rel!r}")
    path = (REPO_ROOT / rel).resolve()
    path.relative_to(REPO_ROOT.resolve())
    if not path.is_dir():
        raise ValueError(f"workdir missing in this repo: {rel}")
    return path


def execute_locally(resolved: dict) -> dict:
    """Run the mapped argv with cwd = repo-root / workdir. No shell.

    Follow-on scripts are not launched. Timeout and truncated stdout/stderr
    keep the HTTP handler from hanging on a noisy or stuck child.
    """
    if not resolved.get("local_execute"):
        raise ValueError("entrypoint is not locally executable")
    workdir = _repo_workdir(str(resolved.get("workdir", "")))
    command = list(resolved.get("command") or [])
    if (
        len(command) < 2
        or command[0] not in ALLOWED_INTERPRETERS
        or not all(isinstance(part, str) for part in command)
        or any("\x00" in part for part in command)
    ):
        raise ValueError("refusing command outside the entrypoint map")
    script_rel = command[1]
    script_path = Path(script_rel)
    if script_path.is_absolute() or ".." in script_path.parts:
        raise ValueError("refusing script path outside workdir")
    script = (workdir / script_path).resolve()
    script.relative_to(workdir)
    if not script.is_file():
        raise ValueError(f"entrypoint script missing: {script_rel}")

    try:
        proc = subprocess.run(
            command,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=EXECUTE_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return {
            "status": "failed",
            "exit_code": None,
            "stdout_summary": _truncate(stdout),
            "stderr_summary": _truncate(
                f"{stderr}\n[timeout after {EXECUTE_TIMEOUT_S}s]"
            ),
            "timed_out": True,
        }
    except OSError as exc:
        return {
            "status": "failed",
            "exit_code": None,
            "stdout_summary": "",
            "stderr_summary": _truncate(f"{type(exc).__name__}: {exc}"),
            "timed_out": False,
        }

    code = int(proc.returncode)
    return {
        "status": "succeeded" if code == 0 else "failed",
        "exit_code": code,
        "stdout_summary": _truncate(proc.stdout or ""),
        "stderr_summary": _truncate(proc.stderr or ""),
        "timed_out": False,
    }


def create_job(body: dict, execute: bool) -> tuple[int, dict]:
    """Create a job record. Executes only when ``execute`` and the map allows it."""
    allowed = {"run_eval", "export_peq", "pin_version"}
    jtype = body.get("type")
    plugin_id = body.get("plugin_id")
    if jtype not in allowed:
        return 400, {"error": "invalid_type", "allowed": sorted(allowed)}

    reg = load_registry()
    plugins = {p["id"]: p for p in reg.get("plugins", [])}
    if plugin_id not in plugins:
        return 400, {"error": "unknown_plugin", "id": plugin_id}

    bindings = set(plugins[plugin_id].get("task_bindings", []))
    if jtype not in bindings:
        return 400, {
            "error": "plugin_task_mismatch",
            "plugin_id": plugin_id,
            "type": jtype,
            "task_bindings": sorted(bindings),
        }

    key = (jtype, plugin_id)
    spec = ENTRYPOINT_MAP.get(key)
    if execute and (spec is None or not spec.get("local_execute")):
        return 400, {
            "error": "execute_disabled",
            "message": (
                "run_eval execution is refused in this repo. The eval tree "
                "lives in restricted lxrobertxiong-beep/audio-algo-eval and "
                "is not vendored here. Omit execute or use execute=false to "
                "dry-run the mapping."
            ),
            "hint": "See JOB_ENTRYPOINT_MAP.md",
        }

    params = body.get("params") or {}
    try:
        resolved = resolve_entrypoint(jtype, plugin_id, params, plugins[plugin_id])
    except KeyError as exc:
        return 400, {"error": "entrypoint_unmapped", "detail": str(exc)}

    jid = "job_" + uuid.uuid4().hex[:12]
    created_at = _now()
    if not execute:
        job = {
            "id": jid,
            "type": jtype,
            "plugin_id": plugin_id,
            "status": "queued",
            "created_at": created_at,
            "params": params,
            "resolved_entrypoint": resolved,
            "result": None,
            "note": "stub dry-run — resolved entrypoint only; does not execute plugins",
        }
        _JOBS[jid] = job
        return 201, job

    resolved = dict(resolved)
    resolved["dry_run"] = False
    try:
        outcome = execute_locally(resolved)
    except ValueError as exc:
        return 400, {"error": "execute_rejected", "detail": str(exc)}

    result = {
        "exit_code": outcome["exit_code"],
        "stdout_summary": outcome["stdout_summary"],
        "stderr_summary": outcome["stderr_summary"],
        "timed_out": outcome["timed_out"],
    }
    if jtype == "export_peq":
        result["artifact_paths"] = [str(params.get("output", "/tmp/peq.json"))]

    job = {
        "id": jid,
        "type": jtype,
        "plugin_id": plugin_id,
        "status": outcome["status"],
        "created_at": created_at,
        "finished_at": _now(),
        "params": params,
        "resolved_entrypoint": resolved,
        "result": result,
        "exit_code": outcome["exit_code"],
        "stdout_summary": outcome["stdout_summary"],
        "stderr_summary": outcome["stderr_summary"],
        "note": (
            "local execute — subprocess finished; no weights downloaded; "
            "not an admission claim. follow_on scripts are not run."
        ),
    }
    _JOBS[jid] = job
    return 201, job


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
        if not isinstance(body, dict):
            self._send(400, {"error": "invalid_json"})
            return

        code, payload = create_job(body, execute)
        self._send(code, payload)


def main() -> None:
    if not REGISTRY_PATH.is_file():
        raise SystemExit(f"missing {REGISTRY_PATH}")
    httpd = HTTPServer((HOST, PORT), Handler)
    print(f"control-platform stub on http://{HOST}:{PORT}  (registry={REGISTRY_PATH})")
    print(
        "POST /v1/jobs dry-run by default; execute=true runs export_peq and "
        "pin_version only (no weight download). run_eval execute=true is refused."
    )
    httpd.serve_forever()


if __name__ == "__main__":
    main()
