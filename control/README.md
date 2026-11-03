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
| `stub_server.py` | 本地 stub：`8765`；`POST /v1/jobs` 默认 dry-run；`execute=true` 只跑 `export_peq` 与 `pin_version` |
| `desktop/` | 桌面**启动项**（Linux `.desktop` + 安装脚本；Windows `.bat`）。拉起同一个 stub 并展示 CLI 用法。调控台仍是 API + CLI |

## 任务类型（固定枚举）

- `run_eval`
- `export_peq`
- `pin_version`

## 首插件

| id | 本地树 | 目标仓（纸面） | 能力 |
|----|--------|----------------|------|
| `filter-listen` | `algo/filter-listen/`（仓内相对路径） | `lxrobertxiong-beep/robert_music` | `export_peq`；48 kHz / 10 ms；Apache-2.0+DCO |
| `call-nr` | `algo/call-nr`（评测适配留在受限仓 `audio-algo-eval` 的 `scripts/run_vbd_eval.py`，不拷进本仓） | 算法→`robert_music`；eval→`audio-algo-eval` | `run_eval` / `pin_version`；钉 `RNNoise@v0.2`、`DeepFilterNet3@v0.5.6`、`GTCRN@502ebfab`、`Silero VAD@066409f`（本地权重，不入库）；**不宣称准入** |

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

从仓库根（`control/` 的上一级）启动时，`execute=true` 会跑本地安全入口，不下载权重。`run_eval?execute=true` 仍是 400 `execute_disabled`。

```bash
python3 control/stub_server.py
curl -s -X POST 'http://127.0.0.1:8765/v1/jobs?execute=true' \
  -H 'Content-Type: application/json' \
  -d '{"type":"export_peq","plugin_id":"filter-listen","params":{"fr":"testdata/synthetic_fr.csv","target":"harman_like","output":"/tmp/peq.json"}}' \
  | python3 -m json.tool
```

OpenAPI 可用任意本地查看器打开 `openapi-stub.yaml`（例如 IDE 预览）；**不要**把本目录当成已发布 API。

## 桌面启动项

裁定仍是 **UI=C**（API + CLI）。`desktop/` 只做两件事：在终端里启动 `python3 control/stub_server.py`（监听 `127.0.0.1:8765`），并打印 / 打开上面的 curl 用法与本 README。它不创建 job，也不改 stub 的 dry-run / `execute=true` 规则。

路径都相对本仓库：脚本用自身位置找到 `control/`，再找到仓库根。从仓库根或 `control/` 运行都可以。

```bash
# 任意工作目录
bash control/desktop/launch-stub.sh

# 装到当前用户的应用菜单（写入绝对 Exec / Path，指向这一份检出）
bash control/desktop/install-linux.sh
```

安装后在应用菜单里找 **Control stub (local)**（中文环境显示「调控平台本地 stub」）。安装脚本会跑 `update-desktop-database` 和 `xdg-desktop-menu forceupdate`。若菜单窗口在安装前已经开着，关掉再打开一次。终端保持打开；关掉窗口或 Ctrl+C 即停止 stub。若 8765 上已经是本 stub，则只显示用法，不再起第二个进程。

无图形会话、或不想弹出 README 时：

```bash
CONTROL_LAUNCHER_NO_OPEN=1 bash control/desktop/launch-stub.sh
```

`install-linux.sh` 会把条目写到 `${XDG_DATA_HOME:-$HOME/.local/share}/applications/robert-music-control-stub.desktop`。请用这个脚本安装。把仓库里的 `.desktop` 原样拷进该目录后，`Exec` 仍靠同目录的 `launch_stub.py`，拷走就找不到脚本。

卸载：

```bash
rm -f "${XDG_DATA_HOME:-$HOME/.local/share}/applications/robert-music-control-stub.desktop"
```

在仓库里直接双击 `control/desktop/robert-music-control-stub.desktop` 时，`Exec` 用桌面文件自己的位置（`%k`）找到旁边的 `launch_stub.py`。文件管理器若要求「可信任 / 可执行」，给该文件加可执行位即可。

Windows：双击 `control/desktop/launch-stub.bat`。`.lnk` 不必入库，生成方式见 [`desktop/WINDOWS.md`](./desktop/WINDOWS.md)。

## 安全边界（摘要）

公开树与 export/publish 任务禁止纳入：

- `jieli-sdk-drop`
- `*.key`
- `private/jieli`（含 `/home/box/private/jieli/`）
- `DynamicEQPro.a` 等杰理闭源制品

详见 `ARCHITECTURE.md`。

## 约束

- 禁止 `git push` / `gh repo create` / Origin create / 写入真密钥。
- Stub 默认只解析 `resolved_entrypoint`（dry-run）。`execute=true` 仅本地执行 `export_peq`（`generate_peq_from_fr.py`，默认 `--no-autoeq`）与 `pin_version`（`setup_pins.sh`，只打印 pin，不下载权重）。`run_eval` 的 `execute=true` 返回 400。结果只给退出码、输出摘要与路径，**不填虚构评测分数**。

## CI

纸面见 [`CI_HOOKS.md`](./CI_HOOKS.md)（push 完成后落地 workflow）。
