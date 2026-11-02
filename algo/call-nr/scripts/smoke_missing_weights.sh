#!/usr/bin/env bash
# Assert optional gtcrn and silero_vad exit 3 when the local pin is missing.
# Does not clone upstream, download weights, or pip-install torch.
# A clean tree is required: algo/call-nr/third_party/ is not used or deleted.
# Same exit code is also covered by tests/test_call_nr_optional.py.
set -euo pipefail

CALL_NR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFER="${CALL_NR}/scripts/infer.py"
SILERO="${CALL_NR}/scripts/run_silero_vad.py"
GTCRN_PIN="502ebfab64da7c4a9af78dcb9c6ceef1ebb01c73"
SILERO_PIN="066409f3d9db45a30d21dfcbf9147826ffdd7052"

if [[ -n "${PYTHON:-}" ]]; then
  PY="${PYTHON}"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
else
  PY="python"
fi

WORK="$(mktemp -d)"
cleanup() { rm -rf "${WORK}"; }
trap cleanup EXIT

ORIG_HOME="${HOME}"
export HOME="${WORK}/home"
mkdir -p "${HOME}"
unset CALL_NR_GTCRN_WEIGHTS GTCRN_CHECKPOINT GTCRN_ROOT SILERO_VAD_ROOT
if [[ -d "${ORIG_HOME}/.local" && -z "${PYTHONUSERBASE:-}" ]]; then
  export PYTHONUSERBASE="${ORIG_HOME}/.local"
fi

tp="${CALL_NR}/third_party"
if [[ -e "${tp}/gtcrn/gtcrn.py" || -e "${tp}/gtcrn/checkpoints/model_trained_on_dns3.tar" || -e "${tp}/silero-vad/hubconf.py" || -e "${tp}/silero-vad/src/silero_vad/data/silero_vad.jit" ]]; then
  echo "algo/call-nr/third_party already contains a local GTCRN or Silero pin." >&2
  echo "This smoke checks the missing-weight path and will not run those files." >&2
  echo "Move that directory aside and re-run. Nothing was downloaded or deleted." >&2
  exit 2
fi

if ! "${PY}" -c "import numpy, soundfile" >/dev/null 2>&1; then
  echo "numpy and soundfile are required (pip install -r algo/call-nr/requirements.txt)." >&2
  echo "This smoke does not install packages and does not install torch." >&2
  exit 2
fi

"${PY}" -c 'import numpy as np, soundfile as sf, sys; sf.write(sys.argv[1], np.zeros(480, dtype=np.float32), 48000, subtype="FLOAT", format="WAV")' "${WORK}/in.wav"

expect_exit_3() {
  local label="$1"
  shift
  local stdout_file="${WORK}/${label}.stdout"
  local stderr_file="${WORK}/${label}.stderr"
  local code=0
  "$@" >"${stdout_file}" 2>"${stderr_file}" || code=$?
  if [[ "${code}" -ne 3 ]]; then
    echo "FAIL ${label}: expected exit 3, got ${code}" >&2
    cat "${stderr_file}" >&2
    exit 1
  fi
  echo "---- ${label} stderr ----"
  cat "${stderr_file}"
  echo "---- ${label} exit 3 ----"
}

require_stderr() {
  local label="$1"
  shift
  local file="${WORK}/${label}.stderr"
  local needle
  for needle in "$@"; do
    if ! grep -F -q -- "${needle}" "${file}"; then
      echo "FAIL ${label}: stderr missing: ${needle}" >&2
      cat "${file}" >&2
      exit 1
    fi
  done
}

refuse_output() {
  local path="$1"
  if [[ -e "${path}" ]]; then
    echo "FAIL: output was written on the failure path: ${path}" >&2
    exit 1
  fi
}

expect_exit_3 gtcrn-missing-weights \
  "${PY}" "${INFER}" --backend gtcrn -i "${WORK}/in.wav" -o "${WORK}/gtcrn.wav"
require_stderr gtcrn-missing-weights \
  "${GTCRN_PIN}" \
  "CALL_NR_GTCRN_WEIGHTS" \
  "GTCRN_CHECKPOINT" \
  "GTCRN_ROOT" \
  "model_trained_on_dns3.tar"
refuse_output "${WORK}/gtcrn.wav"
echo "gtcrn missing weights: exit 3 pin=${GTCRN_PIN} env=CALL_NR_GTCRN_WEIGHTS"

expect_exit_3 silero-missing-weights \
  "${PY}" "${INFER}" --backend silero_vad -i "${WORK}/in.wav" -o "${WORK}/vad.csv"
require_stderr silero-missing-weights \
  "${SILERO_PIN}" \
  "SILERO_VAD_ROOT" \
  "silero_vad.jit" \
  "torch.hub is not used"
refuse_output "${WORK}/vad.csv"
echo "silero missing weights: exit 3 pin=${SILERO_PIN} env=SILERO_VAD_ROOT"

expect_exit_3 silero-script-missing-weights \
  "${PY}" "${SILERO}" -i "${WORK}/in.wav" -o "${WORK}/vad_script.csv"
require_stderr silero-script-missing-weights \
  "${SILERO_PIN}" \
  "SILERO_VAD_ROOT" \
  "silero_vad.jit"
refuse_output "${WORK}/vad_script.csv"

if ! "${PY}" -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('torch') else 1)"; then
  gtcrn_root="${WORK}/gtcrn-stub"
  mkdir -p "${gtcrn_root}"
  printf '%s\n' 'class GTCRN:' '    pass' > "${gtcrn_root}/gtcrn.py"
  "${PY}" -c 'import sys; open(sys.argv[1], "wb").write(b"x" * 20000)' "${WORK}/model_trained_on_dns3.tar"
  export CALL_NR_GTCRN_WEIGHTS="${WORK}/model_trained_on_dns3.tar"
  export GTCRN_ROOT="${gtcrn_root}"
  expect_exit_3 gtcrn-missing-torch \
    "${PY}" "${INFER}" --backend gtcrn -i "${WORK}/in.wav" -o "${WORK}/gtcrn-torch.wav"
  require_stderr gtcrn-missing-torch "torch" "einops" "${GTCRN_PIN}" "CI does not install torch"
  refuse_output "${WORK}/gtcrn-torch.wav"
  unset CALL_NR_GTCRN_WEIGHTS GTCRN_ROOT
  echo "gtcrn missing torch: exit 3 pin=${GTCRN_PIN}"

  silero_root="${WORK}/silero-stub"
  mkdir -p "${silero_root}/src/silero_vad/data"
  printf '%s\n' 'def silero_vad(**kwargs):' '    return None, (None,)' > "${silero_root}/hubconf.py"
  "${PY}" -c 'import sys; open(sys.argv[1], "wb").write(b"x" * 20000)' \
    "${silero_root}/src/silero_vad/data/silero_vad.jit"
  export SILERO_VAD_ROOT="${silero_root}"
  expect_exit_3 silero-missing-torch \
    "${PY}" "${INFER}" --backend silero_vad -i "${WORK}/in.wav" -o "${WORK}/silero-torch.csv"
  require_stderr silero-missing-torch "torch" "${SILERO_PIN}" "CI does not install torch"
  refuse_output "${WORK}/silero-torch.csv"
  unset SILERO_VAD_ROOT
  echo "silero missing torch: exit 3 pin=${SILERO_PIN}"
else
  echo "skip missing-package: torch is installed. Weight-missing path already returned exit 3."
  echo "Without torch, tests/test_call_nr_optional.py covers test_gtcrn_missing_torch_is_explicit and test_silero_missing_torch_is_explicit."
fi

echo "smoke_missing_weights: confirmed exit 3; no weights downloaded"
