# filter-listen 最小离线 demo

SPDX-License-Identifier: Apache-2.0

合成频响 → PEQ JSON → 短 WAV → 指标 stub。只依赖 Python 标准库，不安装 NumPy / AutoEq，不捆绑杰理 SDK。

soft limiter 会在 `apply_peq_wav.py` 里跑过，但它是工程占位，**非听感定稿**。本 demo 不给出听感结论，也**不宣称准入**。

`fr_rmse_db` 在这条合成夹具路径上是算出来的客观数：测量曲线加上 PEQ（`preamp_db` + biquad 级联幅度）相对内置 `harman_like` 目标，在夹具频点上的未平滑 dB RMSE（`fr_rmse_mode=per_bin`，默认）。它只描述 `testdata/synthetic_fr.csv` 这份夹具，**不是听感定稿，也不是准入结果**。不传 `--fr`、也不传 `--wav-path-rmse` 时 `export_metrics.py` 仍把该字段留为 `null`，避免在没有曲线时编造分数。

可选开关，不改变上述默认：

- `--fr-rmse-mode per_bin|third_octave`。`third_octave` 在 20 Hz–20 kHz 的 ISO 近似 1/3 倍频程中心（`1000 * 10^(k/10)`，k = -17…13）上对带内 dB 取平均，再对同一目标在这些中心上做 RMSE。`fr_rmse_db` 是所选模式的分数，JSON 同时写出 `fr_rmse_mode`。
- `--wav-path-rmse`：用给定 WAV；没给 WAV 时合成一段确定性宽带探针。信号走 PEQ 应用路径，**计分时关闭 soft limiter**（与 `apply_peq_wav.py --no-limiter` 相同），再用标准库 Welch/FFT 估计传递函数，相对内置目标打分。若同时传入 `--fr`，**FR CSV 优先**，`fr_rmse_db` 仍来自 CSV。

两种都仍是夹具客观 stub，**不宣称准入**，**非听感定稿**。`run_demo.py` 默认仍写 `per_bin`，并额外打印一行 `third_octave_fr_rmse_db=`（不写入默认 `metrics.json` 的分数）。

`configs/peq_schema.json` 不因本 demo 改字段名或必填项。`lowpass` / `highpass` 使用 RBJ cookbook 系数（通带增益 0 dB），schema 里仍必填的 `gain` 被忽略，不再回退成 peaking。

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
| `metrics.json` | 夹具客观 `fr_rmse_db`（默认 `fr_rmse_mode=per_bin`，有限数值，备注写明不宣称准入、非听感定稿）；`peak` 来自正弦输出 |

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
