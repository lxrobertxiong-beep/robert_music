#!/usr/bin/env bash
# Print call-nr pin metadata and check PLUGIN.json. Does not clone or download.
# CI must stay green without network access to upstream weights.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 - "${ROOT}/PLUGIN.json" <<'PY'
import json
import sys
from pathlib import Path

plugin = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected = {
    "RNNoise": "904a876dce1f9ab8860c0a5000ed151f9f6eef58",
    "DeepFilterNet3": "978576aa8400552a4ce9730838c635aa30db5e61",
}
print("call-nr pin metadata (no weights downloaded):")
found = set()
for pin in plugin.get("pins") or []:
    name = pin.get("name")
    blob = json.dumps(pin, ensure_ascii=False)
    print(f"  {name}@{pin.get('version')} {blob}")
    found.add(name)
    commit = expected.get(name)
    if commit is not None and commit not in blob:
        raise SystemExit(f"pin ref mismatch for {name}: expected {commit}")
missing = sorted(set(expected) - found)
if missing:
    raise SystemExit(f"PLUGIN.json missing pins: {missing}")
print("RNNoise@v0.2: build upstream yourself; set RNNOISE_DEMO or RNNOISE_ROOT.")
print("DeepFilterNet3: optional venv, pip install deepfilternet==0.5.6 deepfilterlib==0.5.6")
print("Explicit model name: DeepFilterNet3. CI does not fetch pins.")
print("Do not place a vendor SDK, firmware, keys, or closed-source DSP libraries in this tree.")
PY
