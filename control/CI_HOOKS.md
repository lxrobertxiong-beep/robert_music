# CI 钩子纸面（目标仓 `lxrobertxiong-beep/robert_music`）

> **状态**：P0 workflow 已在仓库内：`.github/workflows/lint.yml`、`unit-tests.yml`、`smoke.yml`、`control-stub.yml`。`lint` 跑 `ruff check control tests smoke algo`。公开仓仍不包含 `audio-algo-eval` 评测门禁。`filter-listen` 单测在仓库根 `tests/test_filter_listen_*.py`，只依赖标准库。`call-nr` 单测另需 `algo/call-nr/requirements.txt`（numpy、soundfile、soxr）与系统库 `libsndfile1`。`smoke` 在控制面 dry-run 之后再跑 `algo/filter-listen/scripts/run_demo.py`。
> **日期**：2026-11-02（Asia/Shanghai）  
> **编辑源**：`/workspace/control-platform/` → 同步 `/workspace/robert_music/control/`

## 范围

| 仓 | 可见面 | 本纸面 |
|----|--------|--------|
| `lxrobertxiong-beep/robert_music` | 公开（algo + control 同仓） | **本文件** |
| `lxrobertxiong-beep/audio-algo-eval` | private/受限 | 另纸；不阻塞公开仓最小门禁 |

## P0 门禁（PR → `main`）

| Job | 触发 | 做什么 | 失败即挡合并 |
|-----|------|--------|--------------|
| `lint` | pull_request, push@main | `ruff check`（或等价）于 `algo/`、`control/` 可测 Python | 是 |
| `unit` | 同上 | `pytest` 轻量单测（公开 fixture only） | 是 |
| `smoke` | 同上 | `python smoke/run_smoke.py`，再跑 `python algo/filter-listen/scripts/run_demo.py`（stdlib，`--no-autoeq`） | 是 |
| `control-stub-syntax` | 同上 | `python -m py_compile control/stub_server.py`；校验 `plugin-registry.example.json` JSON | 是 |

**明确不进 P0 PR 门禁**：全集评测、主观听感、大模型下载、需要密钥的厂商 SDK、`execute=true` 真跑 job。

## 建议 workflow 文件名（落地时）

```
.github/workflows/lint.yml
.github/workflows/unit-tests.yml
.github/workflows/smoke.yml
.github/workflows/control-stub.yml
```

上述四个文件已入库。触发为 `pull_request`、`push` 到 `main`、`workflow_dispatch`；权限仅 `contents: read`，不使用 `secrets.*`。可参考本地骨架：`/workspace/mlops-drafts/audio-algo-public-skeleton/.github/workflows/`。

## `control` 与 create_job

- CI **不**启动长期 stub HTTP 服务做门禁；只做语法/JSON/映射表存在性检查。
- `JOB_ENTRYPOINT_MAP.md` 与 `openapi-stub.yaml` 变更时，可加一步：断言映射键含 `run_eval` / `export_peq` / `pin_version`。

## Secrets / 权限

- **不**配置真密钥；无 GitHub Packages 发布 token 于 P0。
- `contents: read` 足够跑门禁；发布 job 另议（semver 按需）。

## 落地顺序（push 完成后）

1. 确认 remote=`https://github.com/lxrobertxiong-beep/robert_music.git` 可写。
2. 提交本目录已同步的 `control/` + 根目录 `.github/workflows/*`。
3. 开测试 PR 验证四门禁绿灯。
4. 再考虑 `audio-algo-eval` 侧钩子与 cross-repo `repository_dispatch`（非 P0）。

## 非目标

- 不在 CI 中访问 `/home/box/private/jieli/` 或 `jieli-sdk-drop/`
- 不宣称评测准入阈值
