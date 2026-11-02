# robert_music

开源音频算法系统与调控平台（同仓）。

- 平台锚定：杰理 AC697N / AC897N（OWS + AAC 通话），机型 `LX-OWS01_73D8`
- 许可证：Apache-2.0；贡献需 DCO（`git commit -s`）
- 目录：`algo/` 自研算法插件；`control/` 调控台 API+CLI；`docs/` 社区与边界文档
- P1 插件：`call-nr`（通话降噪）、`filter-listen`（滤波试听补偿，骨架在 `algo/filter-listen/`，`peq_schema` 见 `algo/filter-listen/configs/peq_schema.json`）
- **不包含**杰理官方 SDK / 调音包 / 密钥（见 `docs/PUBLIC_PRIVATE_BOUNDARY.md`）

仓库：`https://github.com/lxrobertxiong-beep/robert_music`（公开主仓）。
