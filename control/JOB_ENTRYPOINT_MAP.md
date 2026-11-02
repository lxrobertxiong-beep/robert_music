# create_job → 入口映射（纸面 + stub 契约）

> **性质**：与 `stub_server.py` POST `/v1/jobs` 解析逻辑对齐。  
> **状态**：默认 **dry-run**（只解析、不执行子进程）。`export_peq` 的 workdir 为仓内相对路径 `algo/filter-listen`；`pin_version` 的 workdir 为仓内相对路径 `algo/call-nr`。  
> **日期**：2026-11-02（Asia/Shanghai）  
> **UI**：已定 **C**（API + CLI 先行）

目标仓：

| 面 | 目标 | 说明 |
|----|------|------|
| 公开算法 + 调控 | `lxrobertxiong-beep/robert_music` | 同仓含 `algo/` + `control/`；许可证 **Apache-2.0 + DCO** |
| 评测（受限） | `lxrobertxiong-beep/audio-algo-eval` | 短名 `audio-algo-eval` |

---

## 映射表

| `type` | `plugin_id` | workdir | 入口 / 命令模板 | 参数要点 |
|--------|-------------|---------|-----------------|----------|
| `export_peq` | `filter-listen` | `algo/filter-listen`（相对仓库根） | `python3 scripts/generate_peq_from_fr.py --fr {fr} [--target {target}] [--no-autoeq] -o {output}` | 后续可选：`scripts/apply_peq_wav.py`、`scripts/export_metrics.py`（见 `follow_on`） |
| `run_eval` | `call-nr` | `audio-algo-eval`（受限评测仓，**不**拷进本仓） | `python3 scripts/run_vbd_eval.py --baseline {baseline}` | 算法侧：`algo/call-nr`；**不宣称准入** |
| `pin_version` | `call-nr` | `algo/call-nr` | `bash scripts/setup_pins.sh` | 回显 registry `pins[]`（含可选 GTCRN / Silero VAD）；stub 只回显 + 命令模板；CI 不下载权重、不安装 torch |

---

## resolved_entrypoint 形状（stub 返回）

`export_peq` / `filter-listen` 与 `pin_version` / `call-nr` 的解析结果都使用仓内相对 workdir（stub 仍只解析、不执行）：

```json
{
  "workdir": "algo/filter-listen",
  "command": ["python3", "scripts/generate_peq_from_fr.py", "..."],
  "command_template": "python3 scripts/generate_peq_from_fr.py ...",
  "dry_run": true,
  "follow_on": []
}
```

`pin_version` / `call-nr`：

```json
{
  "workdir": "algo/call-nr",
  "command": ["bash", "scripts/setup_pins.sh"],
  "command_template": "bash scripts/setup_pins.sh",
  "dry_run": true,
  "follow_on": []
}
```

`run_eval` 的 `workdir` 是受限评测仓短名 `audio-algo-eval`，`algo_weld` 为 `algo/call-nr`。不要把评测树拷进本仓。

- `POST /v1/jobs` 默认 `?execute=false`（或不带 query）：只解析，**不** `subprocess`。
- `execute=true`：本 stub **拒绝执行**（返回 400 / 说明仅解析），避免意外跑重评测。

---

## 与 registry 的关系

- `filter-listen` → 目标仓 `lxrobertxiong-beep/robert_music`（home/repo）
- `call-nr` 算法侧 → 本仓 `algo/call-nr`（`lxrobertxiong-beep/robert_music`）；`eval_adapter` → `lxrobertxiong-beep/audio-algo-eval`（受限，不入库）
- 细节见 `plugin-registry.example.json` 与 `ARCHITECTURE.md` §4 / 本文件。
