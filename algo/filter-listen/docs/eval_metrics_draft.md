# 评测指标草稿（客观 + 主观入口）

SPDX-License-Identifier: Apache-2.0

本文件为 **骨架入口草稿**。`scripts/export_metrics.py` 写出 JSON，便于流水线挂接。  
**不发明**未提供曲线时的 RMSE，也不填 MOS。没有 `--fr` 且没有 `--wav-path-rmse` 时 `fr_rmse_db` 仍为 `null`。  
demo 传入合成 `testdata/synthetic_fr.csv` 与内置目标时，按 PEQ 级联的 RBJ 幅度响应计算 dB RMSE（测量 + `preamp_db` + 各频点幅度）。**默认**对夹具频点直接做均方根，**不做** 1/3 oct 平滑（`fr_rmse_mode=per_bin`）。可选 `--fr-rmse-mode third_octave`：20 Hz–20 kHz ISO 近似 1/3 倍频程中心上的带内 dB 平均，再对同一目标做 RMSE。可选 `--wav-path-rmse`：WAV（或合成探针）走 PEQ 且计分时关闭 soft limiter，Welch 估计传递函数后打分；与 `--fr` 同时给出时 CSV 优先。该数只是夹具上的客观 stub，**不宣称准入**，**非听感定稿**。soft limiter 不进入这个分数。

## 客观（可自动化）

| 指标 | 定义草稿 | 数据 | 本骨架状态 |
|------|----------|------|------------|
| FR 误差 RMSE | 补偿后频响（测量 + preamp + biquad 幅度）vs 目标曲线的 dB RMSE。默认逐频点；可选 1/3 oct 带内平均 | FR CSV，或可选 WAV 路径（limiter 关闭） | 提供 `--fr` 或 `--wav-path-rmse` 时计算（CSV 优先）；否则 `null`。demo 默认仍是 per_bin。不是准入、也非听感定稿 |
| 最大增益 / 预放大 | `preamp_db` 与 bands 峰值，防削波 | PEQ JSON | 读 JSON |
| 峰值 / 真峰值近似 | 处理后 WAV peak、简易 true-peak stub | WAV | 16-bit PCM 峰值 |
| 延迟 | 帧长 10 ms + 图声明 `latency_budget_ms` | graph yaml | 常量报告 |
| 信噪 / 底噪抬升 | 静音段 RMS 处理前后差 | 静音 WAV | 可选，未实现 |

输出示例键（`export_metrics.py`）。未提供频响时：

```json
{
  "sample_rate": 48000,
  "frame_ms": 10,
  "fr_rmse_db": null,
  "fr_rmse_mode": null,
  "peak": null,
  "preamp_db": null,
  "latency_budget_ms": 10.0,
  "notes": "stub — fill in eval harness"
}
```

demo 合成夹具路径会把 `fr_rmse_db` 写成有限数值，`fr_rmse_mode` 为 `per_bin`，`notes` 标明 fixture/objective stub、不宣称准入、非听感定稿。不要把该数读成听感结论或板级准入。stdout 里的 `third_octave_fr_rmse_db` 只是附加信息。

## 主观（入口，不强制本仓 UI）

| 入口 | 说明 |
|------|------|
| ABX / 盲听 | 补偿开/关；同曲目同增益匹配 |
| 偏好评分 | 1–5 音色自然度、低频量感、齿音 |
| 场景标签 | 媒体 / 通话下行旁路 / 通透 |
| 密封条件 | 深插 / 浅戴 / 活动 — 供后续 leakage |

主观结果建议另存，本骨架不规定格式强制校验。soft limiter **非听感定稿**，不得把本骨架输出当成听感结论。

## 与通话基线的边界

- **上行**：默认不做 Harman 类听感补偿。
- **下行媒体**：本模块 PEQ 主路径。
- 降噪客观集不在本目录；本骨架指标聚焦 **频响贴合与过载**（字段预留，数值未填）。

## 合规评测注意

评测夹具数据若来自第三方测量库，遵守其许可；本仓 `testdata/` 仅为合成示例。
