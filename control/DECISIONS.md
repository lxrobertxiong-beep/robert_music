# 负责人裁定（2026-11-02 Asia/Shanghai）

用户原话授权：过程中不用询问；算法负责人全权决策。

| # | 项 | 裁定 |
|---|----|------|
| 1 | 公开仓 | `lxrobertxiong-beep/robert_music`（算法系统 + 调控平台 **同仓**） |
| 1b | 评测仓 | `lxrobertxiong-beep/audio-algo-eval`（GitHub **private** / 受限） |
| 2 | 许可证 | **Apache-2.0 + DCO** |
| 3 | 仓形态 | 同仓含 `algo/` + `control/`；评测分仓（方案 B） |
| 4 | 调控台 UI | **C** 先 API+CLI（本目录 stub）；UI 后置 |
| 5 | P1 插件 | 仅 `call-nr`、`filter-listen`；额外 MCP **暂缓** |
| 6 | SDK/密钥 | 仅本机 `/home/box/private/jieli/`；**不**另建 SDK 私有仓 |

备注：Cursor 不能代建 GitHub 空仓；本会话 Origin `create_repository` 被拒。社区先挂本地模板，仓可用后再推。


## 变更 2026-11-02（用户仓库链接）

公开仓为用户已建：`lxrobertxiong-beep/robert_music`。评测仓仍计划 `audio-algo-eval`（private，待建）。

## 变更 2026-11-02（仓名钉死）

公开仓最终钉：`lxrobertxiong-beep/robert_music`。本地工作树路径为 `/workspace/robert_music/`。CI 钩子纸面按 `robert_music` 起草，**push 完成后落地**。
