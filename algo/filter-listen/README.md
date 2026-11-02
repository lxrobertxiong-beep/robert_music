# filter-listen（AI 滤波 / 试听补偿骨架）

SPDX-License-Identifier: Apache-2.0

可复现的 **开源骨架**：48 kHz、每帧 **480 samples（10 ms）**、可移植 PEQ JSON、离线 FR→PEQ→WAV 烟测。  
本目录代码为 **Apache-2.0**（仓库根 `LICENSE`）。**不**纳入杰理闭源库；openMHA 仅作架构参考（不 vendor AGPL）；AutoEq 为可选 MIT pip 依赖，**不要**把整棵 AutoEq 树 vendor 进来。

`peq_schema` 字段保持稳定，供调控平台把本插件注册为 PEQ 导出 / 应用入口：[`configs/peq_schema.json`](configs/peq_schema.json)。`gain` 对所有 band 仍必填。`lowpass` / `highpass` 忽略该字段：RBJ cookbook 低通 / 高通通带增益是 0 dB（见 `peq.py`）。

导入名：目录带连字符，pytest / 应用代码使用桥接模块 `algo.filter_listen`（`algo/filter_listen.py`）。

## 合规（必读）

| 规则 | 说明 |
|------|------|
| Apache-2.0 | 仓库根 `LICENSE`；第三方见 [`NOTICE`](NOTICE) |
| 禁止 vendor 杰理 | 不得拷贝 `.a` / `.bin` / `.fw` / `.exe` / 密钥 / SDK 源（含 `DynamicEQPro.a`） |
| openMHA | **参考级重写**；本树无 AGPL 源码 |
| AutoEq | 可选 `pip install`；**不要**把整个 AutoEq 仓 vendor 进来 |
| 测量 CSV / WAV | `testdata/` 为合成示例（静音、1 kHz 正弦、合成频响） |

能力映射：[`docs/jieli_capability_map.md`](docs/jieli_capability_map.md)（只做能力对照，不捆绑 SDK）。

## 架构速览

实时：`in → resample(48k) → [call insert 未用] → PEQ → soft limiter → out`  
离线：`FR CSV → generate_peq_from_fr.py → JSON → apply_peq_wav.py`

soft limiter / DRC 为工程占位，**非听感定稿**。详见 [`docs/architecture.md`](docs/architecture.md)。

P0 路径只依赖 Python 标准库（`math` / `wave` / `json`）。NumPy / SciPy / soundfile 不是门禁依赖；见 [`requirements.txt`](requirements.txt)（默认全部注释，避免拖垮 control-only CI）。

最小离线 demo（合成 FR → PEQ → 正弦/静音 WAV → 夹具 `fr_rmse_db`）见 [`docs/demo.md`](docs/demo.md)。该 RMSE 只描述合成夹具，不宣称准入。limiter 仍是 **非听感定稿**。一条命令：

```bash
python3 algo/filter-listen/scripts/run_demo.py
```

## 怎么跑单元烟测

在仓库根目录（与现有 `pytest -q` 相同，不必安装本模块的可选依赖）：

```bash
pytest -q tests/test_filter_listen_peq.py tests/test_filter_listen_graph.py \
  tests/test_filter_listen_schema.py tests/test_filter_listen_scripts.py \
  tests/test_filter_listen_demo.py
```

或直接 `pytest -q`。

## 离线脚本（stdlib；AutoEq 缺失时用 `--no-autoeq`）

工作目录可在仓库根。脚本参数使用你传入的路径。

```bash
python3 algo/filter-listen/scripts/generate_peq_from_fr.py --help
python3 algo/filter-listen/scripts/generate_peq_from_fr.py \
  --fr algo/filter-listen/testdata/synthetic_fr.csv \
  --target harman_like \
  --no-autoeq \
  -o /tmp/filter_listen_peq.json

python3 algo/filter-listen/scripts/apply_peq_wav.py \
  --wav algo/filter-listen/testdata/sine_1k_0p5s.wav \
  --peq /tmp/filter_listen_peq.json \
  -o /tmp/filter_listen_out.wav

python3 algo/filter-listen/scripts/export_metrics.py \
  --wav /tmp/filter_listen_out.wav \
  --peq /tmp/filter_listen_peq.json \
  --fr algo/filter-listen/testdata/synthetic_fr.csv \
  --target harman_like \
  -o /tmp/filter_listen_metrics.json
```

不带 `--fr`、也不带 `--wav-path-rmse` 时 `fr_rmse_db` 保持 `null`。带上合成频响时写出的数是夹具客观 stub，不宣称准入，也不是听感定稿。默认 `--fr-rmse-mode per_bin`（未平滑的逐频点 dB RMSE）。可选 `third_octave`（20 Hz–20 kHz ISO 近似 1/3 倍频程带内 dB 平均后再 RMSE）和 `--wav-path-rmse`（WAV 或合成探针走 PEQ、计分时 limiter 关闭、Welch 估计传递函数；与 `--fr` 同时给出时 CSV 优先）。`fr_rmse_mode` 写在 metrics JSON 里。详见 [`docs/demo.md`](docs/demo.md)。

可选 AutoEq（MIT，不 vendor）：

```bash
pip install autoeq
python3 algo/filter-listen/scripts/generate_peq_from_fr.py \
  --fr algo/filter-listen/testdata/synthetic_fr.csv \
  -o /tmp/filter_listen_peq.json
```

当前脚本在检测到 AutoEq 后仍回退到确定性 stdlib stub（上游 API 不稳定）。`--no-autoeq` 显式走 stub。

## 目录

```
configs/   graph_48k_10ms.yaml, peq_schema.json, example_compensation.json
docs/      architecture, demo, jieli_capability_map, m3_dependencies, eval_metrics_draft
scripts/   run_demo.py, generate_peq_from_fr.py, apply_peq_wav.py, export_metrics.py
peq.py     可移植 biquad cascade
graph.py   48 kHz / 10 ms 图（limiter 为非听感定稿 stub）
testdata/  synthetic_fr.csv, silence_0p5s.wav, sine_1k_0p5s.wav
```

调控面 `export_peq` 的 workdir 为仓内相对路径 `algo/filter-listen`（见 `control/JOB_ENTRYPOINT_MAP.md`）。

## M3 依赖

泄漏 / 三频段动态 EQ / AI bass / 3D 对 `peq_schema`、48 kHz 帧 API 的依赖见 [`docs/m3_dependencies.md`](docs/m3_dependencies.md)。

## 评测入口

[`docs/eval_metrics_draft.md`](docs/eval_metrics_draft.md) — 客观字段草稿 + 主观 ABX 入口。demo 夹具上的 `fr_rmse_db` 是算出来的 dB RMSE（不宣称准入，非听感定稿）；没有频响曲线时该字段仍为 `null`。
