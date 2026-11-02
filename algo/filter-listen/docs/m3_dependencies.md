# M3 对 filter-listen 输出的依赖

SPDX-License-Identifier: Apache-2.0

M3 规划能力：泄漏感知、三频段动态 EQ、AI 低音、3D/空间听感。  
以下依赖 **本骨架已冻结的接口**，避免后续回写破坏 48 kHz / 10 ms 契约。

## 依赖矩阵

| M3 能力 | 依赖的本模块输出 | 用法 | 备注 |
|---------|------------------|------|------|
| **泄漏补偿 / leakage** | `seal_score` **hook**（预留；本骨架可先 no-op，尚未实现） | 按密封分数选择 / 插值多套 PEQ JSON | 半入耳密封漂移；上行通话一般不做 Harman 补偿 |
| **泄漏补偿** | `peq` graph + `peq_schema.json` | 多曲线切换仍走同一 cascade API | 禁止为泄漏引入厂商 `.a` |
| **三频段动态 EQ** | 48 kHz **frame API**（`frame_samples=480`） | 段内包络在帧边界更新增益，再写入动态 peq sections | schema 见 `jieli_capability_map.md`；替代 DynamicEQPro 的可移植面 |
| **三频段动态 EQ** | `PeqCascade` / 可热更新 bands | 动态增益只改参数，不换图拓扑 | soft limiter 仍在动态 EQ 之后，且 **非听感定稿** |
| **AI bass** | `vbass` 接口字段 + PEQ 低频 shelf 可组合 | AI 模块输出驱动 stub 字段 / 附加 lowshelf | 模型权重另仓；本树仅接口 |
| **AI bass** | 48 kHz 帧 API | 低时延侧链分析 | 与 virtualbass 厂商库解耦 |
| **3D / 空间** | 先完成耳机 EQ（本模块 PEQ）再 HRTF | 补偿作为空间渲染前级 | HRTF 个性化勿与耳机补偿混为一条曲线；勿引入 AGPL 运行时 |

## 必须保持稳定的 API

1. **`AudioGraph.process_frame` / `process_buffer`**：`sample_rate=48000`，`frame_samples=480`。
2. **PEQ JSON**（`configs/peq_schema.json`）：`fc`, `Q`, `gain`, `type`，以及顶层 `sample_rate` 与 `bands`。
3. **Limiter 节点位置**：PEQ 之后、输出之前。曲线本身 **非听感定稿**。
4. **`seal_score` hook（约定）**：签名意向 `Callable[[], float] | None`；本骨架可不实现；后续泄漏模块读取。
5. **Call insert point**：默认关闭；通话链与听感补偿解耦。

## 非依赖（刻意切断）

- 任何杰理效果目标文件或 `DynamicEQPro.a`
- openMHA AGPL 源码树
- 完整 AutoEq git 树（仅可选 pip）

## 建议落地顺序

1. 冻结合成 FR → PEQ → WAV 的烟测（本 PR 的 stdlib 路径）。
2. 增加 `seal_score` no-op hook 与多 JSON 曲线表。
3. 动态 peq schema → 帧级增益调度。
4. AI bass / 3D 另里程碑，消费本图出口。
