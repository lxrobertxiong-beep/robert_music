# create_job → 入口映射（纸面 + stub 契约）

> **性质**：本地纸面；与 `stub_server.py` POST `/v1/jobs` 解析逻辑对齐。  
> **状态**：远程仓尚未创建；默认 **dry-run**（只解析、不执行子进程）。  
> **日期**：2026-11-02（Asia/Shanghai）  
> **UI**：已定 **C**（API + CLI 先行）

目标仓（纸面名，未推远程）：

| 面 | 目标 | 说明 |
|----|------|------|
| 公开算法 + 调控 | `lxrobertxiong-beep/robert_music` | 同仓含 `algo/` + `control/`；许可证 **Apache-2.0 + DCO** |
| 评测（受限） | `lxrobertxiong-beep/audio-algo-eval` | 短名 `audio-algo-eval` |

---

## 映射表

| `type` | `plugin_id` | workdir | 入口 / 命令模板 | 参数要点 |
|--------|-------------|---------|-----------------|----------|
| `export_peq` | `filter-listen` | `/workspace/oss-ai-filter-listen` | `python3 scripts/generate_peq_from_fr.py --fr {fr} [--target {target}] [--no-autoeq] -o {output}` | 后续可选：`scripts/apply_peq_wav.py`、`scripts/export_metrics.py`（见 `follow_on`） |
| `run_eval` | `call-nr` | `/workspace/call-nr-eval` | `python3 scripts/run_vbd_eval.py --baseline {baseline}` | 算法钉扎侧：`/workspace/m1-call-nr`；**不宣称准入** |
| `pin_version` | `call-nr` | `/workspace/m1-call-nr` | `bash scripts/setup_pins.sh` | 或仅回显 registry `pins[]`（stub 默认回显 + 命令模板） |

---

## resolved_entrypoint 形状（stub 返回）

```json
{
  "workdir": "/workspace/...",
  "command": ["python3", "scripts/....py", "..."],
  "command_template": "python3 scripts/....py ...",
  "dry_run": true,
  "follow_on": []
}
```

- `POST /v1/jobs` 默认 `?execute=false`（或不带 query）：只解析，**不** `subprocess`。
- `execute=true`：本 stub **拒绝执行**（返回 400 / 说明仅解析），避免意外跑重评测。

---

## 与 registry 的关系

- `filter-listen` → 目标仓 `lxrobertxiong-beep/robert_music`（home/repo）
- `call-nr` 算法侧 → `lxrobertxiong-beep/robert_music`；`eval_adapter` → `lxrobertxiong-beep/audio-algo-eval`
- 细节见 `plugin-registry.example.json` 与 `ARCHITECTURE.md` §4 / 本文件。
