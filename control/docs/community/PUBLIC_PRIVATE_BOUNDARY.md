# 公开仓 / 私有制品 目录边界清单

版本：2026-11-02 · 按音频算法负责人最终裁定更新

## 仓库裁定

| 仓 | 可见性 | 用途 |
| --- | --- | --- |
| `lxrobertxiong-beep/robert_music` | 公开 | 自研算法系统 + 调控平台（**同仓**）：建议目录 `algo/` + `control/` |
| `lxrobertxiong-beep/audio-algo-eval` | 私有（**暂缓另建**） | 评测受限数据与脚本；未建前留本地 `/workspace/call-nr-eval` 等 |
| 杰理 SDK / 调音包 / 密钥 | 本机私有 | `/home/box/private/jieli/`（及 `/workspace/jieli-sdk-drop/` 备份）；**暂不另建 SDK 私有 Git 仓** |

许可证：**Apache-2.0 + DCO**  
调控台：先 **API+CLI**（对齐 `/workspace/control-platform/`），UI 后置  
P1 插件：仅 `call-nr`、`filter-listen`；额外 MCP 暂缓（GitHub 已通；Origin 有则用）

## 原则

1. **永不进入公开 Git 树**：杰理官方 SDK、调音工具/调音包、许可证密钥、未授权厂商闭源库与二进制。
2. **可以进入公开仓**：自研算法、与芯片解耦的接口、可公开评测协议/脱敏样例说明、社区文档、调控台 API/CLI 自研代码。
3. **私有环境**：DSP 使用 `/home/box/private/jieli/sdk/`；密钥仅本地权限收紧，**不写进任何文档正文**。

## 公开仓目录骨架

```
robert_music/
├── README.md
├── LICENSE                 # Apache-2.0
├── CONTRIBUTING.md         # 含 DCO
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── .github/
├── algo/                   # call-nr、filter-listen 等自研
├── control/                # 调控平台 API+CLI
├── docs/                   # 含本边界清单、挂仓检查单
└── evaluation/             # 仅可公开的协议/入口；受限评测进 audio-algo-eval
```

## .gitignore（公开仓最低要求）

```
**/jieli/sdk/
**/private/jieli/
**/*license*.key
**/*.key
**/*AC897N*earphone_release*
**/LX-OWS01_73D8*
**/*调音包*
**/jieli-sdk-drop/
**/*.fw
**/AC697X_config_tool/
```

## 调音包对照映射

允许：私有阅读后写能力对照表到公开 `docs/`。  
禁止：复制厂商 Lua/配置工具/闭源音效库到公开树。

## 变更记录

| 日期 | 变更 |
| --- | --- |
| 2026-11-02 | 首稿 |
| 2026-11-02 | 负责人最终裁定：双仓名、同仓结构、Apache-2.0+DCO、本机 SDK、UI=C |
