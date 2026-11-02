# filter-listen 最小离线 demo

SPDX-License-Identifier: Apache-2.0

合成频响 → PEQ JSON → 短 WAV → 指标 stub。只依赖 Python 标准库，不安装 NumPy / AutoEq，不捆绑杰理 SDK。

soft limiter 会在 `apply_peq_wav.py` 里跑过，但它是工程占位，**非听感定稿**。本 demo 不给出听感结论，也**不宣称准入**。

`fr_rmse_db` 在这条合成夹具路径上是算出来的客观数：测量曲线加上 PEQ（`preamp_db` + biquad 级联幅度）相对内置 `harman_like` 目标，在夹具频点上的未平滑 dB RMSE。它只描述 `testdata/synthetic_fr.csv` 这份夹具，**不是听感定稿，也不是准入结果**。不传 `--fr` 时 `export_metrics.py` 仍把该字段留为 `null`，避免在没有曲线时编造分数。lowpass / highpass 的 cookbook 通带增益是 0 dB，schema 里的 `gain` 不进入这两类系数。

`configs/peq_schema.json` 不因本 demo 改字段。lowpass / highpass 使用 RBJ cookbook 系数，不再回退成 peaking。

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
| `metrics.json` | 夹具客观 `fr_rmse_db`（有限数值，备注写明不宣称准入、非听感定稿）；`peak` 来自正弦输出 |

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
  --fr algo/filter-listen/testdata/synthetic_fr.csv \
  --target harman_like \
  -o /tmp/filter-listen-demo/metrics.json
```

`--fr` / `--target` 只在要填写 `fr_rmse_db` 时需要。目标曲线是仓内示例，不是官方 Harman 表。

## CI

- `pytest -q tests/test_filter_listen_demo.py`（`pytest -q` 也会收集它）
- smoke workflow 另跑同一条命令：`python algo/filter-listen/scripts/run_demo.py`

两条都不安装可选数值依赖，也不改 control-stub / lint 的依赖列表。
