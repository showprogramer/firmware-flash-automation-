# TASK-20260803：文档与 Agent 资料目录整理

## 状态

| 项 | 状态 |
| --- | --- |
| 类型 | 文档与目录整理（不涉及产品代码） |
| 当前状态 | ✅ 已完成 |
| 前置 | 无 |
| 父任务 | 无 |
| 分支 | `feature/pyside6-migration` |
| 完成 commit | `0616fe3`（文档整理，本任务收尾） |

---

## 目标

按内容语义重新组织项目文档、UI 素材和个人 AI 沟通草稿，减少 `AGENTS.md` 的上下文负担，并让 Codex、Claude Code、OpenCode 使用一致的共享规范。

## 已确认决策

- 根目录 `README.md` 作为项目概览和入口。
- `AGENTS.md` 作为共享 Agent 工作规范，只保留高频、强约束内容。
- `CLAUDE.md` 保持为 Claude Code 兼容入口，不复制完整规范。
- 软件运行截图属于 `docs/ui-reference/screenshots/`。
- 初始 UI 草图属于 `specs/design/sketches/`。
- AI 沟通草稿属于本地 `.local/ai-prompts/`，不提交、不共享。
- 不创建空的 `specs/decisions/`。
- 保留现有 `docs/code-review/REVIEW-20260728-pre-crud-readiness.md` 的未提交修改。
- 保留 `.codex/` 和 `.qoder/` 的本地内容，只增加忽略规则，不清理目录。

## 目标结构

```text
README.md
AGENTS.md
CLAUDE.md

docs/
├── architecture.md
├── agent-workflow.md
├── ui-reference/
│   └── screenshots/
├── code-review/
├── migrations/
├── CHANGELOG.md
└── COMMIT_TEMPLATE.md

specs/
├── active/
├── archive/
└── design/
    └── sketches/

.local/
└── ai-prompts/
```

## 文件变更

### Task 1：移动项目说明与视觉资料  `complexity: medium`

**复杂度理由：** 涉及多个已存在目录和共享文档入口，需要保持历史路径语义清晰，但不涉及代码、数据库或公共 API。

**Files:** Move `docs/README.md` to `README.md`; move runtime screenshots to `docs/ui-reference/screenshots/`; move initial sketches to `specs/design/sketches/`; move personal prompts to `.local/ai-prompts/`。

### Task 2：拆分共享 Agent 规范与详细文档  `complexity: medium`

**复杂度理由：** 会改变多个 CLI 的上下文入口和文档引用关系，需要保留现有架构、测试、流程约束，避免信息丢失或规则冲突。

**Files:** Rewrite `AGENTS.md` as a concise shared guide; create `docs/architecture.md`; create `docs/agent-workflow.md`; keep `CLAUDE.md` as a thin compatibility entry point。

### Task 3：同步本地目录忽略规则  `complexity: low`

**复杂度理由：** 仅修改忽略配置，但必须同步多个工具文件并覆盖本地 Agent 状态、个人草稿和报告目录。

**Files:** Update `.gitignore`, `.claudeignore`, `.codexignore`, and `.cursorignore` with `.codex/`, `.qoder/`, and `.local/`; keep the three Agent ignore files synchronized except for their top comments。

### Task 4：文档链接与工作区验证  `complexity: low`

**复杂度理由：** 只需检查目标路径、Git 状态、忽略结果和 Markdown 链接，不涉及运行时代码。

**Files:** Verify `README.md`, `AGENTS.md`, `CLAUDE.md`, moved asset paths, ignore behavior, and the preserved existing Review modification。

## 非目标

- 不修改产品代码、测试代码或运行时配置。
- 不创建新的架构决策记录。
- 不删除 `.codex/`、`.qoder/` 或其他本地运行数据。
- 不将个人 AI 沟通草稿写入共享文档。
- 不提交或自动创建 Git commit。

## 验收标准

- 根目录存在项目概览 `README.md`，不再依赖 `docs/README.md` 作为唯一入口。
- `AGENTS.md` 只包含高频共享规则，并能链接到架构和 Agent 工作流详细文档。
- 运行截图、初始草图、个人提示词分别位于目标目录。
- `.codex/`、`.qoder/`、`.local/` 均被 Git 和三个 Agent ignore 文件忽略。
- 现有 Review 修改未被覆盖，`.codex/` 和 `.qoder/` 本地内容未被删除。
- Markdown 路径和目录说明与实际结构一致。

---

## 验证记录

### 自动化验证（已完成）

| 平台 | 环境 | 命令 | 结果 |
| --- | --- | --- | --- |
| 不限（文档操作） | — | `git diff --check`；三个 Agent ignore 文件去除工具头注释后内容一致；`git check-ignore -v .codex/ .qoder/ .local/ai-prompts/review_prompts.md` | 通过（均命中忽略规则；旧路径 `docs/README.md`、`specs/current_project_ui/`、`specs/images/`、`specs/prompts/` 已不存在，新路径均存在） |

- 已知平台差异：无。
- 提交：`0616fe3`

### 人工验证（已完成）

- 平台：用户侧
- 结论：用户确认文档位置与文件处理无误。

## 文档与收口

- `docs/CHANGELOG.md`：已在 `Unreleased` 记录本次整理（已完成）。
- 迁移说明：`docs/migrations/MIGRATION-20260803-document-organization.md`（已完成）。
- Review：不适用（纯文档整理，无代码审查对象）。
- 按 `AGENTS.md` 的人工验证前置流程提交。

## Task DoD

- [x] 文档目录整理与迁移完成
- [x] 三个 Agent ignore 文件同步
- [x] 自动化验证已记录（git diff --check、ignore 规则命中、旧路径清理确认）
- [x] 人工验证已记录
- [x] Review 不适用已确认
- [x] CHANGELOG 已同步
- [x] 迁移说明已记录
