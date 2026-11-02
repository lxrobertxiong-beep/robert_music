# filter-listen 最小离线 demo

SPDX-License-Identifier: Apache-2.0

合成频响 → PEQ JSON → 短 WAV → 指标 stub。只依赖 Python 标准库，不安装 NumPy / AutoEq，不捆绑杰理 SDK。

soft limiter 会在 `apply_peq_wav.py` 里跑过，但它是工程占位，**非听感定稿**。本 demo 不给出听感结论。`fr_rmse_db` 保持 `null`。

`configs/peq_schema.json` 不因本 demo 改字段。

## 一条命令

在仓库根目录：

```bash
python3 algo/filter-listen/scripts/run_demo.py
```

默认把产物写到新的临时目录，并在最后一行打印 `demo ok:`。指定目录：

```bash
python3 algo/filter-listen/scripts/run_demo.py --out /tmp/filter-listen-demo
```

产物：

| 文件 | 内容 |
|------|------|
| `peq.json` | `--no-autoeq` 的 stdlib peaking stub，符合 `peq_schema` |
| `sine_out.wav` | `testdata/sine_1k_0p5s.wav` 经过 PEQ + soft limiter |
| `silence_out.wav` | `testdata/silence_0p5s.wav` 经过同一条路径（应仍为静音） |
| `metrics.json` | 指标 stub；`fr_rmse_db` 为 `null`，`peak` 来自正弦输出 |

## 拆开的三步（与上面同一条路径）

```bash
python3 algo/filter-listen/scripts/generate_peq_from_fr.py \
  --fr algo/filter-listen/testdata/synthetic_fr.csv \
  --target harman_like \
  --no-autoeq \
  -o /tmp/filter-listen-demo/peq.json

python3 algo/filter-listen/scripts/apply_peq_wav.py \
  --wav algo/filter-listen/testdata/sine_1k_0p5s.wav \
  --peq /tmp/filter-listen-demo/peq.json \
  -o /tmp/filter-listen-demo/sine_out.wav

python3 algo/filter-listen/scripts/apply_peq_wav.py \
  --wav algo/filter-listen/testdata/silence_0p5s.wav \
  --peq /tmp/filter-listen-demo/peq.json \
  -o /tmp/filter-listen-demo/silence_out.wav

python3 algo/filter-listen/scripts/export_metrics.py \
  --wav /tmp/filter-listen-demo/sine_out.wav \
  --peq /tmp/filter-listen-demo/peq.json \
  -o /tmp/filter-listen-demo/metrics.json
```

## CI

- `pytest -q tests/test_filter_listen_demo.py`（`pytest -q` 也会收集它）
- smoke workflow 另跑同一条命令：`python algo/filter-listen/scripts/run_demo.py`

两条都不安装可选数值依赖，也不改 control-stub / lint 的依赖列表。
