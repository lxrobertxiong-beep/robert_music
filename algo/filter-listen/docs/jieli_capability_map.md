# 杰理能力映射 → 本 OSS 可移植接口（M2/M3）

SPDX-License-Identifier: Apache-2.0

> 来源说明：基于公开音效能力档位的 **洁净室能力摘要**。  
> **严禁**将 `DynamicEQPro.a`、其它 `.a/.bin/.fw/.exe`、license key、SDK 源码放入本树。  
> 本文件只做能力对照表，**不捆绑、不链接、不附带**任何厂商 SDK。

## 产品档位（摘要）

| 档位 | 能力组合 | 备注 |
|------|----------|------|
| **EFFECTS_BASE** | `music_eq` + `drc` | 基础音乐 EQ + DRC |
| **EFFECTS_ADVANCE (OWS)** | `music_eq` + `virtualbass` + `mblimiter` + `post_eq` | 低功耗开关需关闭才能开该档 |
| **EFFECTS_ULTRA (OWS)** | `music_eq` + `virtualbass` + `dynamic_eq_pro_det` + `mblimiter` + `post_eq` | 在线调音与 EQ 文件开关互斥；本仓用 JSON 代替厂商 EQ 文件 |

参数更新（厂商侧，仅文档）：EQ 配置读取 + 超档效果更新（歌曲 EQ 模式 / 通话 EQ 模式）。本仓不拷贝该 API。

### DynamicEQPro（厂商闭源能力字段，不收录库）

文档级参数能力：`fc`, `Q`, `gain`, `attack`/`release`, `low_thr`/`high_thr`, peaking IIR, `SampleRate`, `nSection`, `channel`。  
闭源库 **`DynamicEQPro.a` 不得纳入本仓库**。

## 接口对照表

| JieLi capability | Our OSS module/schema | Direction (export coeffs / runtime) | Status (M2/M3) | Must NOT include |
|------------------|----------------------|-------------------------------------|----------------|------------------|
| `music_eq` | `configs/peq_schema.json` + `peq.py` cascade | export coeffs（biquad JSON）→ runtime `PeqCascade` | **M2** | 厂商 EQ 文件二进制、`.a` |
| `post_eq` | 同上（独立 JSON 或第二 cascade） | export coeffs / runtime | **M2** | 厂商 post_eq 私有表 |
| `drc` | `graph.soft_limiter` / limiter node stub | runtime stub；阈值可后续 export | **M2** stub（**非听感定稿**） | DRC `.a` / 私有曲线 blob |
| `mblimiter` | `graph.soft_limiter`（ADV/ULTRA 映射） | runtime stub | **M2** stub（**非听感定稿**） | `mblimiter` 闭源目标文件 |
| `virtualbass` | M3 AI bass / vbass **接口字段 stub**（见下） | schema-only；无算法体 | **M3** | virtualbass `.a` / 系数仓 |
| `dynamic_eq_pro_det` / DynamicEQPro | dynamic PEQ sections schema stub（M3） | schema → 未来 runtime | **M3** | **`DynamicEQPro.a`**、密钥、SDK |
| EQ file | 本仓 JSON schema 为可移植替代 | export JSON（非厂商 bin） | **M2** | 厂商 `eq*.bin` |
| 超档效果热更新 | 主机侧加载 JSON 热更新钩子（文档） | runtime config reload | **M2/M3** | 厂商 update API 实现拷贝 |
| 通话 EQ 模式 | graph `call_insert` + 可选独立 PEQ | runtime bypass / 轻补偿 | **M2** insert unused | 通话闭源链 |

## M3 接口字段 stub（仅 schema，无实现）

**virtualbass / AI bass（未来）**

```json
{
  "vbass": {
    "enabled": false,
    "cutoff_hz": 120,
    "drive_db": 0.0,
    "ai_bass_model_id": null
  }
}
```

**dynamic_eq sections（未来，对齐文档字段名，不链闭源库）**

```json
{
  "dynamic_peq": {
    "sample_rate": 48000,
    "nSection": 0,
    "channel": 1,
    "sections": [
      {
        "fc": 1000.0,
        "Q": 1.0,
        "gain": 0.0,
        "attack": 0.01,
        "release": 0.1,
        "low_thr": -40.0,
        "high_thr": -12.0,
        "type": "peaking"
      }
    ]
  }
}
```

## 配置开关（厂商侧笔记，本 OSS 不编译 SDK）

- ADV/ULTRA：最低功耗宏关闭后才开该档
- 在线调音与板载 EQ 输出互斥
- 使用 EQ 文件时走文件而不是在线表

本 OSS 用 YAML/JSON 表达等价意图，不依赖上述宏，也不编译厂商 SDK。

> **听感状态**：`soft_limiter` / DRC·mblimiter 映射均为 **骨架 stub，非听感定稿**；正式听感以评测与主观协议为准。
