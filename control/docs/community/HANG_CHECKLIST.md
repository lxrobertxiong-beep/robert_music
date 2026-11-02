# 挂仓检查清单

公开主仓已定：`lxrobertxiong-beep/robert_music`。`audio-algo-eval` 暂缓另建。骨架经 CloudAgent PR 入仓后按下列顺序核对社区文档。

1. 复制本目录下文档到目标仓库对应路径（根目录与 `.github/`、`docs/`）。
2. 将 `.github/ISSUE_TEMPLATE/config.yml` 中所有 `example.com` 占位换成真实 **blob/raw** 路径（指向本仓 `CONTRIBUTING.md`、`CODE_OF_CONDUCT.md`、`docs/`、`SECURITY.md`）。
3. 确认 `SECURITY.md` 中私密举报渠道已填写；`CODE_OF_CONDUCT.md` 举报联系同步更新。
4. **Labels**：当前 Issue 模板已**去掉** `labels` 字段，避免新仓无预设 label 时创建失败。若希望自动打标，请先在仓库创建 `bug`、`enhancement`（及需要的其他标签），再把 `labels` 写回模板 front matter。
5. 许可证确定后：放入根目录 `LICENSE`；在 `CONTRIBUTING.md`「DCO/CLA」节启用最终文案（Apache-2.0 倾向 DCO + `Signed-off-by`）。
6. 挂仓后立刻扫描开放 Issue / PR 与社区风险，并向音频算法负责人汇报。
