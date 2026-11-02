# create_job → 入口映射（纸面 + stub 契约）

> **性质**：与 `stub_server.py` POST `/v1/jobs` 解析逻辑对齐。  
> **状态**：默认 **dry-run**（只解析、不执行子进程）。`?execute=true` 只对下面标了「本地可执行」的两条真正 `subprocess`；`run_eval` 继续拒绝。  
> **日期**：2026-11-02（Asia/Shanghai）  
> **UI**：已定 **C**（API + CLI 先行）。不做桌面启动器。

目标仓：

| 面 | 目标 | 说明 |
|----|------|------|
| 公开算法 + 调控 | `lxrobertxiong-beep/robert_music` | 同仓含 `algo/` + `control/`；许可证 **Apache-2.0 + DCO** |
| 评测（受限） | `lxrobertxiong-beep/audio-algo-eval` | 短名 `audio-algo-eval`；**不**拷进本仓 |

仓库根是 `control/` 的上一级。下表 `workdir` 都相对该根解析（评测仓短名除外）。

---

## 映射表

| `type` | `plugin_id` | workdir | 入口 / 命令模板 | `execute=true` | 参数要点 |
|--------|-------------|---------|-----------------|----------------|----------|
| `export_peq` | `filter-listen` | `algo/filter-listen`（相对仓库根） | `python3 scripts/generate_peq_from_fr.py --fr {fr} --target {target} [--no-autoeq] -o {output}` | **本地可执行** | 省略 `no_autoeq` 时控制面默认加上 `--no-autoeq`（无 AutoEq 也能跑）。默认 `fr=testdata/synthetic_fr.csv`。后续 `apply_peq_wav` / `export_metrics` 只出现在 `follow_on`，**本请求不跑** |
| `run_eval` | `call-nr` | `audio-algo-eval`（受限评测仓，**不**拷进本仓） | `python3 scripts/run_vbd_eval.py --baseline {baseline}` | **拒绝**（400 `execute_disabled`） | 算法侧：`algo/call-nr`；**不宣称准入**。dry-run 仍解析 |
| `pin_version` | `call-nr` | `algo/call-nr` | `bash scripts/setup_pins.sh` | **本地可执行** | 只打印 pin 元数据（含可选 GTCRN / Silero VAD）。**不下载权重、不安装 torch**。`params.pins` 只回显，不进 shell |

---

## `execute=true` 行为与限制

- `POST /v1/jobs` 默认 `?execute=false`（或不带 query）：只解析，**不** `subprocess`。响应 `status=queued`，`resolved_entrypoint.dry_run=true`，`result=null`。
- `execute=true` 且任务在上表「本地可执行」：在仓库根解析 `workdir` 后，以 argv（不用 shell）跑主入口。子进程超时 **20s**；stdout / stderr 各自截断到 **2048** 字符。成功或非零退出都返回 **201**，job 记录包含：
  - `status`：`succeeded` 或 `failed`（超时也是 `failed`）
  - `exit_code`（超时为 `null`）
  - `stdout_summary` / `stderr_summary`（同样写在 `result` 里）
  - `resolved_entrypoint.dry_run=false`
- `execute=true` + `run_eval`：**继续拒绝执行**，HTTP **400** / `execute_disabled`。本仓没有评测树。dry-run 仍可解析命令模板。
- 不下载模型权重，不安装 torch，不跑 `audio-algo-eval`，不打包 jieli SDK / 密钥 / 私有二进制。
- `lowpass` / `highpass` 的 `gain` 仍由 `algo/filter-listen/peq.py` 忽略（RBJ 通带 0 dB）。控制面不改这条契约，也不填评测分数。

### 已执行 job 的形状

```json
{
  "status": "succeeded",
  "exit_code": 0,
  "stdout_summary": "wrote /tmp/peq.json (5 bands, generator=stdlib_peaking_stub)\n",
  "stderr_summary": "",
  "resolved_entrypoint": {
    "workdir": "algo/filter-listen",
    "command": ["python3", "scripts/generate_peq_from_fr.py", "--fr", "testdata/synthetic_fr.csv", "--target", "harman_like", "--no-autoeq", "-o", "/tmp/peq.json"],
    "dry_run": false,
    "local_execute": true
  },
  "result": {
    "exit_code": 0,
    "stdout_summary": "wrote /tmp/peq.json (5 bands, generator=stdlib_peaking_stub)\n",
    "stderr_summary": "",
    "timed_out": false
  }
}
```

`pin_version` 的 `workdir` 为 `algo/call-nr`，命令为 `bash scripts/setup_pins.sh`，stdout 以 pin 元数据开头，并写明没有下载权重。

---

## resolved_entrypoint 形状（dry-run）

省略 `no_autoeq` 时，dry-run 与 execute 使用同一条带 `--no-autoeq` 的命令：

```json
{
  "workdir": "algo/filter-listen",
  "command": ["python3", "scripts/generate_peq_from_fr.py", "--fr", "testdata/synthetic_fr.csv", "--target", "harman_like", "--no-autoeq", "-o", "/tmp/peq.json"],
  "command_template": "python3 scripts/generate_peq_from_fr.py --fr testdata/synthetic_fr.csv --target harman_like --no-autoeq -o /tmp/peq.json",
  "dry_run": true,
  "local_execute": true,
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
  "local_execute": true,
  "follow_on": []
}
```

`run_eval` 的 `workdir` 是受限评测仓短名 `audio-algo-eval`，`local_execute` 为 false，`algo_weld` 为 `algo/call-nr`。不要把评测树拷进本仓。

---

## 与 registry 的关系

- `filter-listen` → 目标仓 `lxrobertxiong-beep/robert_music`（home/repo）；入口含 `generate_peq_from_fr`、`apply_peq_wav`、`export_metrics`、`run_demo`
- `call-nr` 算法侧 → 本仓 `algo/call-nr`；pins 与 `PLUGIN.json` 对齐（RNNoise、DeepFilterNet3、GTCRN、Silero VAD，均可选、不入库）；`eval_adapter` → `lxrobertxiong-beep/audio-algo-eval`（受限，不入库）
- 细节见 `plugin-registry.example.json` 与 `ARCHITECTURE.md` §4 / 本文件。
