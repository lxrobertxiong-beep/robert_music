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
    "GTCRN": "502ebfab64da7c4a9af78dcb9c6ceef1ebb01c73",
    "Silero VAD": "066409f3d9db45a30d21dfcbf9147826ffdd7052",
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
print(
    "GTCRN@502ebfab: set CALL_NR_GTCRN_WEIGHTS or GTCRN_CHECKPOINT to "
    "checkpoints/model_trained_on_dns3.tar and GTCRN_ROOT to that checkout. "
    "Optional cache: ~/.cache/call-nr/gtcrn/model_trained_on_dns3.tar. Not vendored."
)
print(
    "Silero VAD@066409f (v6.2.3-8-g066409f): set SILERO_VAD_ROOT to a checkout "
    "with hubconf.py and src/silero_vad/data/silero_vad.jit. "
    "Optional cache: ~/.cache/call-nr/silero-vad/. Not vendored. No torch.hub download."
)
print("Do not place a vendor SDK, firmware, keys, or closed-source DSP libraries in this tree.")
PY
