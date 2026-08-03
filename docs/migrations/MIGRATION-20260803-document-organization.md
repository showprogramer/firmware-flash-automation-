# 文档与 Agent 资料目录整理

- 日期：2026-08-03
- 原因：区分项目概览、架构参考、任务规格、运行截图和个人 AI 草稿，降低共享 Agent 入口的重复内容。

## 路径变更

| 原路径 | 新路径 | 说明 |
|---|---|---|
| `docs/README.md` | `README.md` | 项目概览入口 |
| `specs/current_project_ui/` | `docs/ui-reference/screenshots/` | 软件实际运行截图 |
| `specs/images/` | `specs/design/sketches/` | 初始 UI 草图 |
| `specs/prompts/` | `.local/ai-prompts/` | 个人 AI 沟通草稿，不共享 |
| 详细内容混在 `AGENTS.md` | `docs/architecture.md`、`docs/agent-workflow.md` | 共享入口只保留高频规则 |

## 影响

- Codex、OpenCode 和 Claude Code 使用根目录 `AGENTS.md` 作为共享规范入口。
- `CLAUDE.md` 只导入 `AGENTS.md`，不再维护第二套完整规则。
- `.codex/`、`.qoder/` 和 `.local/` 不进入 Git 或 Agent 默认上下文。
- 现有 Review、产品代码和运行目录内容不受影响。

## Runtime 清理

- `.runtime/` 只保留 `fwasset.db` 和 `logs/app.log`。
- 归档 Review 仍引用的 `qt_phase1b.png` 已移动到 `docs/ui-reference/screenshots/archive/`。
- 其他未被代码或文档引用的历史 UI 试验图片和 `_spike_dark.py` 已移除。

## 验证

- `git diff --check`
- 检查三个 Agent ignore 文件去除工具头注释后内容一致。
- `git check-ignore -v .codex/ .qoder/ .local/ai-prompts/review_prompts.md`
- 检查旧路径不存在且新路径存在。

## 回滚

按上表反向移动文件，恢复旧版 `AGENTS.md`、`CLAUDE.md` 和 ignore 条目；本次变更未删除 `.codex/`、`.qoder/` 或 `.local/` 内的本地内容。
