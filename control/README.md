> **本地同步**：本目录由 `/workspace/control-platform/` 同步而来，现已在公开仓 `lxrobertxiong-beep/robert_music`。

# control-platform（调控平台 · 本地草案）

本地镜像目录：`/workspace/robert_music/control/`（已随公开仓入库）。

> **唯一落点**：`/workspace/control-platform/`  
> **状态**：纸面 + OpenAPI stub + 本地 HTTP stub；已在公开仓；**无真密钥**；无生产服务。`filter-listen` 路径为仓内 `algo/filter-listen`；`call-nr` 路径为仓内 `algo/call-nr`。  
> **日期**：2026-11-02（Asia/Shanghai）  
> **裁定**：UI=**C**（API + CLI 先行）；许可证 **Apache-2.0 + DCO**；  
> 目标公开仓纸面 `lxrobertxiong-beep/robert_music`（同仓含 `control/`）；  
> 目标评测仓纸面 `lxrobertxiong-beep/audio-algo-eval`。详见 `DECISIONS.md`。

本目录是「插件与调控 API」草案的**唯一主交付**。勿再使用误开的平行目录 `/workspace/mlops-drafts/control-plane-api/`（已标迁移）。

## 目录文件

| 文件 | 作用 |
|------|------|
| `README.md` | 本说明 |
| `DECISIONS.md` | 负责人裁定钉死项 |
| `ARCHITECTURE.md` | 调控平台与方案 B 双仓、插件模型、任务流、安全边界、M2 公开仓合并注记 |
| `JOB_ENTRYPOINT_MAP.md` | create_job → CLI/脚本入口映射表 |
| `plugin-registry.example.json` | 首插件注册表示例：`call-nr`、`filter-listen` |
| `openapi-stub.yaml` | OpenAPI 3.0 stub（含 `resolved_entrypoint`） |
| `stub_server.py` | 本地 stub：`8765`；`POST /v1/jobs` 解析入口（默认 dry-run） |

## 任务类型（固定枚举）

- `run_eval`
- `export_peq`
- `pin_version`

## 首插件

| id | 本地树 | 目标仓（纸面） | 能力 |
|----|--------|----------------|------|
| `filter-listen` | `algo/filter-listen/`（仓内相对路径） | `lxrobertxiong-beep/robert_music` | `export_peq`；48 kHz / 10 ms；Apache-2.0+DCO |
| `call-nr` | `algo/call-nr`（评测适配留在受限仓 `audio-algo-eval` 的 `scripts/run_vbd_eval.py`，不拷进本仓） | 算法→`robert_music`；eval→`audio-algo-eval` | `run_eval` / `pin_version`；钉 `RNNoise@v0.2`、`DeepFilterNet3@v0.5.6`；**不宣称准入** |

## 本地如何看 stub

```bash
cd /workspace/control-platform

# 读注册表
python3 -c 'import json; print(json.load(open("plugin-registry.example.json"))["plugins"][0]["id"])'

# HTTP stub（127.0.0.1:8765）
python3 stub_server.py
# 另开终端：
curl -s http://127.0.0.1:8765/v1/plugins | python3 -m json.tool
curl -s http://127.0.0.1:8765/v1/plugins/filter-listen | python3 -m json.tool

# create_job → 入口映射（dry-run）
curl -s -X POST http://127.0.0.1:8765/v1/jobs \
  -H 'Content-Type: application/json' \
  -d '{"type":"export_peq","plugin_id":"filter-listen","params":{"fr":"testdata/synthetic_fr.csv","target":"harman_like","output":"/tmp/peq.json"}}' \
  | python3 -m json.tool

curl -s -X POST http://127.0.0.1:8765/v1/jobs \
  -H 'Content-Type: application/json' \
  -d '{"type":"run_eval","plugin_id":"call-nr","params":{"baseline":"rnnoise"}}' \
  | python3 -m json.tool
```

OpenAPI 可用任意本地查看器打开 `openapi-stub.yaml`（例如 IDE 预览）；**不要**把本目录当成已发布 API。

## 安全边界（摘要）

公开树与 export/publish 任务禁止纳入：

- `jieli-sdk-drop`
- `*.key`
- `private/jieli`（含 `/home/box/private/jieli/`）
- `DynamicEQPro.a` 等杰理闭源制品

详见 `ARCHITECTURE.md`。

## 约束

- 禁止 `git push` / `gh repo create` / Origin create / 写入真密钥。
- Stub 默认只解析 `resolved_entrypoint`，**不执行**子进程；结果只给路径与钉版回显，**不填虚构评测分数**。

## CI

纸面见 [`CI_HOOKS.md`](./CI_HOOKS.md)（push 完成后落地 workflow）。
