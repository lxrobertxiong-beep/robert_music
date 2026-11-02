# 评测指标草稿（客观 + 主观入口）

SPDX-License-Identifier: Apache-2.0

本文件为 **骨架入口草稿**。`scripts/export_metrics.py` 写出 JSON stub，便于流水线挂接。  
**不发明**未实测的 RMSE / MOS。`fr_rmse_db` 在本骨架中固定为 `null`。

## 客观（可自动化）

| 指标 | 定义草稿 | 数据 | 本骨架状态 |
|------|----------|------|------------|
| FR 误差 RMSE | 补偿后频响 vs 目标曲线，1/3 oct 或 FFT 平滑 dB RMSE | FR CSV + 目标 | stub 字段（null） |
| 最大增益 / 预放大 | `preamp_db` 与 bands 峰值，防削波 | PEQ JSON | 读 JSON |
| 峰值 / 真峰值近似 | 处理后 WAV peak、简易 true-peak stub | WAV | 16-bit PCM 峰值 |
| 延迟 | 帧长 10 ms + 图声明 `latency_budget_ms` | graph yaml | 常量报告 |
| 信噪 / 底噪抬升 | 静音段 RMS 处理前后差 | 静音 WAV | 可选，未实现 |

输出示例键（`export_metrics.py`）：

```json
{
  "sample_rate": 48000,
  "frame_ms": 10,
  "fr_rmse_db": null,
  "peak": null,
  "preamp_db": null,
  "latency_budget_ms": 10.0,
  "notes": "stub — fill in eval harness"
}
```

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
