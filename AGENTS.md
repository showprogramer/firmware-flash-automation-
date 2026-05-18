# Repository Guidelines (项目规范)

## Project Structure & Module Organization (项目结构与模块组织)
This is a Python desktop application for managing firmware assets. Source code lives under `src/fwasset/`:
- Core domain logic → `core/`
- UI panels and view models → `ui/`
- Console entry point → `fwasset.app:main`

Tests live in `tests/` and follow the same feature boundaries as source modules.  
Project notes and task plans are in `specs/`, user-facing documentation in `docs/README.md`, change history in `docs/CHANGELOG.md`, helper scripts in `scripts/`.
Runtime files belong in `.runtime/`. **Do not commit** local databases, logs, caches, or `config.toml`.

## Build, Test, and Development Commands (构建、测试与开发命令)
- `uv sync --extra dev` — Install dependencies into `.venv`
- `uv run fwasset` — Run the desktop application
- `uv run python -m pytest -q` — Run full test suite
- `uv run python -m pytest tests/test_asset_index.py -q --no-cov` — Run single test file
- `.\scripts\test.ps1` — Canonical Windows verification command

## Coding Style & Naming Conventions (编码风格与命名规范)
- Use Python 3.8+ syntax with 4-space indentation.
- Prefer type hints for new helper functions.
- Keep UI orchestration separate from core logic.
- Test files: `test_*.py`
- View models: clear nouns (e.g. `asset_filter_model.py`)
- Service modules: `_service.py` suffix
- Prefer existing helpers in `fwasset.core` and `fwasset.ui` over new abstractions.

## Testing Guidelines (测试指南)
- Framework: pytest
- Minimum coverage: 80% for `src/fwasset` (UI files excluded)
- Use `@pytest.mark.ui` for display-dependent tests
- Filter with `-m "not ui"` when needed

## Task Verification & Git Workflow (任务验证与提交流程)
**重要规则**：当涉及以下情况时，**必须先通知我人工验证**，等待我明确回复「验证通过」或「可以提交」之后，才能执行 git commit 和更新 `docs/CHANGELOG.md`：

- UI 相关改动
- 核心业务逻辑修改
- 固件资产处理、USB 相关流程
- 性能、安全、配置相关变更
- 任何重构或新功能

**流程**：
1. 完成后明确告诉我「已完成，请人工验证」。
2. 回复中列出已运行的自动化验证命令和结果；如果我粘贴同一组结果并说明验证通过，可视为人工验收已完成。
3. 我验证通过并回复后，再生成 Conventional Commit 并提交。
4. 同时补充 `docs/CHANGELOG.md`。
5. 如果任务对应 `specs/` 中的 TODO 或技术计划，完成后同步将对应条目标记为已完成；已拆分出的 `src/fwasset/ui/panels/log_panel.py` 不得继续标记为待拆。

## Migration Notes (迁移记录)
Use `docs/migration note.md` for changes that future agents must understand before editing:
- File or directory moves, especially documentation moving into `docs/` or review docs moving into `docs/code-review/`
- Public entry point changes, config/runtime path changes, database/cache schema migrations
- Compatibility shims, deprecated paths, or follow-up cleanup that should not be guessed from Git history alone

Do not write migration notes for ordinary bug fixes that only change local implementation details. Keep each note short: date, reason, old path/API, new path/API, compatibility impact, verification command, and rollback or follow-up if relevant.

## 代码审查文档自动化规范 (Code Review Automation)
每当完成代码重构、修复、重大修改或审查后，请**自动**在 `docs/code-review/` 目录下创建或更新审查文档，并严格使用以下结构。

### 文件命名建议
- `code-review-YYYYMMDD-序号.md`（例如 `code-review-20260514-01.md`）
- 或按模块：`review-core-asset-index.md`

### 写作模板（必须严格遵守）

```markdown
---
### 问题 [编号]：[简洁的问题标题]

**类型**： [架构 | 规范 | 性能 | 安全 | 用户体验 | Bug修复 | 重构]

**模块**： `[涉及的文件路径或模块名]`

**问题描述**
- [具体描述反模式、Bug 或隐患]
- [列出受影响的逻辑点]

**处理方案**
- [如果是待处理：具体步骤]
- [如果是已修复：写出关键代码改动逻辑]

**状态**： [⬜ 待处理 | ✅ 已修复 | ⏳ 验证中]

**验证记录**
- 验证日期：YYYY-MM-DD
- 验证人：人工 / Agent
- 验证结果：通过 / 需要修改
- 对应版本：vX.Y.Z

**相关 Commit**： [commit hash]
---
