# 音频算法调控平台 · 架构底稿（本地）

> **性质**：本地纸面草案，落在 `/workspace/control-platform/`。  
> **状态**：本地 stub 可用。公开仓 `lxrobertxiong-beep/robert_music` 已含 `control/`、`algo/filter-listen/` 与 `algo/call-nr/`。  
> **原则**：执行用户音频算法指令；可挂接算法插件与开放平台；**不发明指标、不宣称榜单结果**。  
> **日期**：2026-11-02（Asia/Shanghai）  
> **裁定**：UI=**C**；公开仓 `lxrobertxiong-beep/robert_music`（同仓含 `control/`）；评测仓 `lxrobertxiong-beep/audio-algo-eval`；许可证 **Apache-2.0 + DCO**。详见 `DECISIONS.md`。

---

## 1. 目标与范围

**目标产品线**：「音频算法系统 + 调控平台」——把已有算法树（通话降噪、滤波/听感补偿等）以可注册插件方式接到统一控制面，按任务调度评测、导出参数、钉版本。

**控制面路径（已裁定）**：

| 选项 | 含义 | 裁定 |
|------|------|------|
| **C** | API + CLI 先行 | **已定：先落地**（本目录 stub + OpenAPI） |
| **A** | 自建 Web / 本地 UI | C 稳定后跟进 |
| **B** | 挂接既有 OSS 调控 UI | 备选；需单独选型评审 |

不在本草案推荐随机 TTS MCP 插件；已有可用连接器：**GitHub**、**Cursor Origin**（仅作仓/协作接线，不代替算法执行）。

---

## 2. 分层

```
┌─────────────────────────────────────────────────────────┐
│  Control UI（已定 C：API+CLI；日后可跟 A/B）               │
│  CLI / 未来 Web；只发任务、读状态与结果指针                │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP (OpenAPI stub)
┌──────────────────────────▼──────────────────────────────┐
│  Control API（本仓 stub）                                  │
│  · list plugins · create job · get job status/result     │
│  · 任务类型：run_eval | export_peq | pin_version          │
└───────┬─────────────────────────────┬───────────────────┘
        │                             │
┌───────▼──────────────┐    ┌─────────▼───────────────────┐
│  Plugin Registry     │    │  Job Runner（本地进程）       │
│  plugin-registry*.json│    │  调插件 entry CLI / eval 入口 │
└───────┬──────────────┘    └─────────┬───────────────────┘
        │                             │
   ┌────▼────┐                 ┌──────▼──────┐
   │ Plugins │                 │ Eval adapters│
   │ call-nr │                 │ call-nr-eval │
   │ filter- │                 │ （受限面）    │
   │ listen  │                 └──────┬──────┘
   └────┬────┘                        │
        │                      ┌──────▼──────┐
        │                      │ OSS boundary │
        │                      │ public algo  │
        │                      │ vs private   │
        └──────────────────────┴──────────────┘
```

### 2.1 Plugins（算法插件层）

每个插件是**本地可执行入口 + 元数据**，不把杰理 SDK 编进插件树。

| 插件 id（草案） | 本地路径 | 首批能力 |
|-----------------|----------|----------|
| `call-nr` | `algo/call-nr/` | 通话上行 NS 骨架：契约 A identity；可选 RNNoise@v0.2、DeepFilterNet3@v0.5.6、GTCRN@502ebfab、Silero VAD@066409f（权重不入库，不宣称准入） |
| `filter-listen` | `algo/filter-listen/` | 48 kHz / 10 ms 图；FR→PEQ JSON；PEQ→WAV |

真实入口以仓库内脚本为准（见 §4 与 `plugin-registry.example.json`）。

### 2.2 Eval（评测适配层）

| 路径 | 角色 | 可见面 |
|------|------|--------|
| `audio-algo-eval`（受限仓，不入库） | 通话降噪小闭环（`scripts/run_vbd_eval.py`） | 受限评测侧；**准入数值未确认，禁止宣称准入/榜单** |
| `/workspace/mlops-drafts/audio-eval-restricted-skeleton/` | 双仓 B 评测仓纸面骨架 | 受限 |

**采样率路径（契约，非指标）**：

- 上行通话端侧试点：**16 kHz / 256 samples**（契约 B，仅文档；见 `algo/call-nr/README.md`。本仓不绑定厂商 SDK）。
- 桌面评测/对照与滤波播放/补偿图：**48 kHz / 10 ms（480 samples）**（契约 A / filter-listen）。
- 评测侧常见桥接：语料 16 kHz → 升 48 kHz 推理 → 降回 16 kHz 再计分（soxr）；**不得**把契约 A/B 标签混用。

### 2.3 Control API

本地 OpenAPI stub：`openapi-stub.yaml`。职责仅限：

1. 列出已注册插件；
2. 创建任务（job）；
3. 查询任务状态与结果指针（路径/日志引用，**不内嵌虚构分数**）。

实现前可用 CLI 直接调插件脚本；API 为统一面占位。

### 2.4 OSS 边界（公开算法 vs 私有/受限）

对齐方案 **B（双仓）** 与社区边界文档：

| 面 | 内容 | 参考 |
|----|------|------|
| **Public algo** | 自研算法、轻量 fixture、模型卡、社区模板；许可证 **Apache-2.0 + DCO**；公开仓 `lxrobertxiong-beep/robert_music`（同仓含 `control/`、`algo/filter-listen/` 与 `algo/call-nr/`） | `mlops-drafts/audio-algo-public-skeleton/`、`community-templates/` |
| **Restricted eval** | 重评测、数据集清单/外链、门禁脚本；目标仓纸面 `lxrobertxiong-beep/audio-algo-eval`（短名 `audio-algo-eval`；private/受限；远程尚未创建） | `mlops-drafts/audio-eval-restricted-skeleton/`、`call-nr-eval/` |
| **Private never-public** | 杰理 SDK、调音包、密钥、厂商闭源库 | `/home/box/private/jieli/`；工作区投放 `/workspace/jieli-sdk-drop/` **不得**进公开 Git |

**硬禁令（公开树）**：

- 不得收录 `/home/box/private/jieli/` 或等价 SDK 树；
- **`DynamicEQPro.a` 禁止进入任何公开树**；
- 不得提交 `*.key`、厂商 `.fw`、调音包原文等（见 `community-templates/docs/PUBLIC_PRIVATE_BOUNDARY.md`）。

调控平台本身可本地读私有路径做联调，但 **导出/发布任务必须过滤私有制品**。

---

## 3. Plugin registry schema

逻辑 schema（JSON）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | 例 `"0.1.0"` |
| `plugins[]` | array | 插件列表 |
| `plugins[].id` | string | 稳定 id（`call-nr` / `filter-listen`） |
| `plugins[].display_name` | string | 展示名 |
| `plugins[].local_path` | string | 仓内相对路径（`algo/call-nr`、`algo/filter-listen`） |
| `plugins[].visibility` | `"public_candidate"` \| `"restricted"` \| `"private"` | 默认可发布面意图 |
| `plugins[].license` | object | `spdx`（可 `TODO`）、`notes` |
| `plugins[].pins` | array | 钉版：`name` / `version` / `ref`（commit 或 PyPI） |
| `plugins[].entrypoints` | array | `name` / `kind`（`cli_script`） / `path` / `args_hint` |
| `plugins[].task_bindings` | array | 该插件支持的 `task_type` |
| `plugins[].eval_adapter` | object\|null | 可选：`path`、`entrypoint` |
| `plugins[].oss_boundary` | object | `may_publish`、`never_bundle` 路径/模式列表 |

示例文件：`plugin-registry.example.json`。

---

## 4. 任务类型（task types）

| `task_type` | 意图 | 典型绑定 |
|-------------|------|----------|
| `run_eval` | 跑评测适配器；写出 summary/报告**路径**；不宣称准入 | `call-nr` → `audio-algo-eval` 的 `scripts/run_vbd_eval.py`（不入库） |
| `export_peq` | FR→可移植 PEQ JSON（及可选 apply/metrics stub） | `filter-listen` → `scripts/generate_peq_from_fr.py` |
| `pin_version` | 校验/记录第三方钉版（clone checkout / 包版本）；不改远程仓 | `call-nr` → `scripts/setup_pins.sh` 及 pins 元数据 |

Job 状态机（草案）：`queued` → `running` → `succeeded` \| `failed` \| `cancelled`。  
`result` 仅含：退出码、日志路径、产物路径列表、钉版回显；**禁止**在 stub 中填入未实测的 MOS/SDR 等数字。

### 4.1 create_job → 入口映射

完整纸面表见 **`JOB_ENTRYPOINT_MAP.md`**。Stub `POST /v1/jobs` 按 `type`+`plugin_id` 解析并返回 `resolved_entrypoint`（默认 dry-run，不执行子进程）：

| `type` | `plugin_id` | workdir | 入口 |
|--------|-------------|---------|------|
| `export_peq` | `filter-listen` | `algo/filter-listen` | `scripts/generate_peq_from_fr.py`（follow-on: apply / export_metrics） |
| `run_eval` | `call-nr` | `audio-algo-eval`（受限，不入库） | `scripts/run_vbd_eval.py --baseline ...`（algo weld: `algo/call-nr`） |
| `pin_version` | `call-nr` | `algo/call-nr` | `scripts/setup_pins.sh` + registry pins 回显 |



---

## 5. Private vs public（调控平台视角）

| 类别 | 可出现在公开算法仓 / 公开 release？ | 调控平台本地？ |
|------|-------------------------------------|----------------|
| `algo/call-nr` 自研脚本与契约文档 | 是（本仓骨架） | 是 |
| `algo/filter-listen` 自研 PEQ/图 | 是（Apache-2.0 骨架，limiter **非听感定稿**） | 是 |
| `call-nr-eval` 脚本与 mini fixture | 评测仓纸面 `audio-algo-eval`（受限） | 是 |
| `/home/box/private/jieli/**` | **否** | 仅私有联调 |
| `DynamicEQPro.a` | **否（硬禁）** | 不得经 export/publish job 拷贝到公开树 |
| 客户语音 / 主观大集 / 完整大权重 | **否（默认）** | 评测仓或对象存储清单 |

连接器（GitHub / Origin）只用于**确认后的**仓协作；本目录草案 **不 `git push`、不 `gh repo create`**。

---

## 5.1 M2 公开仓合并注记（filter-listen）

`filter-listen` 已在本仓 `algo/filter-listen/`（Apache-2.0 + DCO）。公开布局用 `algo/`（草案里的 `src/` 已按此迁入，不再使用 `src/`）。

- 入口脚本与 `configs/peq_schema.json`、`configs/graph_48k_10ms.yaml` 在模块内；`peq_schema` 字段名保持稳定；
- `plugin-registry` 的 `local_path` 与 `export_peq` workdir 为仓内相对路径 `algo/filter-listen`（入口脚本仍相对该目录）；
- **不得**带入 `jieli-sdk-drop`、`*.key`、`private/jieli`、`DynamicEQPro.a`；
- soft limiter / DRC 为工程 stub，**非听感定稿**。

`call-nr` 评测入口留在受限评测侧（目标 `lxrobertxiong-beep/audio-algo-eval`，不拷进本仓）；算法焊接指向本仓 `algo/call-nr/`，不把评测仓当作公开算法包主体。

---

## 6. 与既有底稿的关系

| 路径 | 关系 |
|------|------|
| `/workspace/mlops-drafts/repo-and-ci-proposal.md` | 双仓 B、CI/发布总提案 |
| `/workspace/mlops-drafts/audio-algo-public-skeleton/` | 公开算法仓目录骨架 |
| `/workspace/mlops-drafts/audio-eval-restricted-skeleton/` | 受限评测仓纸面 |
| `/workspace/community-templates/` | CoC / CONTRIBUTING / SECURITY / 公私边界 |
| `algo/call-nr/`、`algo/filter-listen/` | 首批插件均已入库 |
| `lxrobertxiong-beep/audio-algo-eval` | 首个 `run_eval` 适配器（受限，不入库） |

---

## 7. 非目标（本底稿明确不做）

- 不实现生产调度器 / 多租户；
- 不在本阶段落地选项 A/B UI（**已定 C**；A/B 后置）；
- 不推荐或接入随机 TTS MCP；
- 不写入假评测分数、不宣称 board/准入结果；
- 不推送 remote、不创建正式 GitHub/Origin 仓。
