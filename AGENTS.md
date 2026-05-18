# Repository Guidelines (项目规范)

## Project Structure & Module Organization

Python desktop application for managing firmware assets. Source code under `src/fwasset/`:

- Core domain logic → `core/` (scanner, index, types, settings, services)
- UI panels & view models → `ui/` (shell, panels, operation_panels, view_models)
- Console entry point → `fwasset.app:main`
- Tests → `src/fwasset/tests/` (use `test_*.py` naming)
- Specs & plans → `specs/` (active, decisions, archive, prompts)
- User docs → `docs/README.md`, change history → `docs/CHANGELOG.md`
- Runtime data → `.runtime/` (logs, indexes); **never commit** `config.toml`, `fwasset.db`, or `.runtime/`

## Build, Test & Lint Commands

```bash
uv sync --extra dev                                         # Install dependencies
uv run fwasset                                               # Run desktop application
uv run python -m pytest -q                                   # Full test suite
uv run python -m pytest src/fwasset/tests/test_asset_index.py -q --no-cov  # Single file
.\scripts\test.ps1                                           # Canonical Windows verification
```

There are **no standalone lint or type-check commands** configured (no ruff, mypy, flake8). Code style is enforced by convention and review. Run `.\scripts\test.ps1` as the canonical gate — it includes coverage >= 80%.

## Coding Style & Conventions

### Imports & Type Hints
- Always use `from __future__ import annotations` at the top of source files (enables `X | Y` union syntax on Python 3.8+).
- Import order: stdlib → third-party → `fwasset.*` local modules.
- Use `Literal` and `TypedDict` for domain contracts (`core/types.py`). Treat `FirmwareAsset`, `ServiceResult`, `FlashMode` etc. as the canonical data shapes — never add fields without updating the corresponding `TypedDict`.
- Prefer type hints on all new helper functions and public methods.

### Naming
- Test files: `test_*.py` in `src/fwasset/tests/`
- Service modules: `_service.py` suffix (e.g. `scan_service.py`, `flash_service.py`)
- View models: clear nouns (e.g. `asset_filter_model.py`, `scan_state_model.py`)
- Private helpers: underscore prefix (`_db_path`, `_build_sidebar`)
- Constants: `UPPER_SNAKE_CASE` at module top (e.g. `SCHEMA_VERSION`, `FONT_FAMILY`)

### Service Return Convention
All service functions return a `dict` matching `ServiceResult` shape: `{"ok": bool, "code": str, "message": str, "payload": dict}`. User-facing messages are in **Chinese**. Errors use specific `code` strings (e.g. `"index_unavailable"`, `"scan_failed"`), never bare exceptions.

### UI Patterns
- **Panel registry**: Operation panels use `@register` decorator + `get_panel(flash_mode)` lookup in `ui/operation_panels/registry.py`. New flash modes only need a new panel file — do not modify `FirmwareListPanel`.
- **Task queue**: `BaseFlashPanel._run_task()` spawns daemon threads; results are dispatched via `queue.Queue` and polled with `self.after(120, ...)`.
- **View models**: Extract state into standalone model classes (e.g. `AssetSelectionModel`, `ScanStateModel`). Panels compose models; they do not inherit from them.
- **Design tokens**: All colors and fonts come from `ui/design_tokens.py`. Never hard-code hex values or font sizes in panel code.
- **Cancellation**: Use `threading.Event` objects. Create a local `cancel_event` before spawning the worker thread; the thread captures this event in a closure to avoid race conditions.

### Logging & DI
- Services accept `log_fn=print` as default — callers can inject `logger.info` or similar.
- File logging goes through `core/logging_utils.py` with output to `.runtime/logs/app.log`.

### Config & External Files
- `config.toml` — local machine config (gitignored). Template maintained as `config.example.toml`.
- `firmware_catalog.toml` — firmware type definitions shipped with the app.
- Runtime directory resolved by `settings.py`: dev → `.runtime/`, frozen → exe sibling `runtime/`, overridable via `FWASSET_RUNTIME_DIR`.

## Testing Conventions

- Framework: pytest. Coverage gate: >= 80% for `src/fwasset` (UI files excluded via `coverage.omit`).
- Use `@pytest.mark.ui` for display-dependent tests; filter with `-m "not ui"`.
- Test helpers: module-level factory functions (e.g. `make_asset()`) over `conftest` fixtures for simple data.
- Mocking: prefer `monkeypatch.setattr` with lambdas over `unittest.mock` objects.
- Assert service results by key: `assert result["ok"] is True`, `assert result["code"] == "ok"`.
- Error-path testing: use `pytest.raises(SomeError, match="中文消息")` to verify Chinese error messages.

## Document Naming Conventions

| Type | Directory | Naming | Example |
|------|-----------|--------|---------|
| Architecture Decision | `specs/decisions/` | `ADR-NNN-short-name.md` | `ADR-001-ui-core-separation.md` |
| Task / Plan | `specs/active/` | `TASK-YYYYMMDD-short-name.md` | `TASK-20260505-newtasks.md` |
| Migration Note | `docs/migrations/` | `MIGRATION-YYYYMMDD-short-name.md` | `MIGRATION-20260518-docs-consolidation.md` |
| Code Review | `docs/code-review/` | `REVIEW-YYYYMMDD-short-name.md` | `REVIEW-20260518-sidebar-panel.md` |

## Task Verification & Git Workflow

**重要规则**：涉及以下改动时，**必须先通知人工验证**，等待「验证通过」后再 commit：

- UI 相关改动
- 核心业务逻辑修改（`core/` 公共 API、`types.py` TypedDict/Literal、服务返回结构）
- 固件资产处理、USB 相关流程
- 性能、安全、配置相关变更
- 任何重构或新功能
- 操作面板注册表或 UI 入口变更
- 数据库 schema 迁移

**流程**：
1. 完成后明确告知「已完成，请人工验证」。
2. 列出已运行的自动化验证命令和结果；人工粘贴同一组结果并确认后，可视为验收通过。
3. 人工确认后，按 `docs/COMMIT_TEMPLATE.md` 格式生成 Conventional Commit 并提交。
4. 同步更新 `docs/CHANGELOG.md`。
5. 如果任务对应 `specs/active/` 中的计划，完成后将对应条目标记为已完成。

## Code Review Automation

完成代码重构、修复、重大修改后，**自动**在 `docs/code-review/` 创建 `REVIEW-YYYYMMDD-short-name.md`，严格使用以下模板：

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
```

**何时触发审查**：完成以下任意场景后，主动告知用户需要 review 并写出 `REVIEW-*` 文档：
- `core/types.py` 的 TypedDict 或 Literal 新增/修改
- 服务层 `ServiceResult` 返回结构字段变化
- 操作面板注册表或 UI 入口变更（`registry.py`、`shell.py`）
- 扫描、索引、USB 操作等业务流程修改
- 数据库 schema 迁移（`asset_index.py` SCHEMA_VERSION 变更）
- 核心模块公共 API 签名变更

## Migration Notes

Use `docs/migrations/` for changes that future agents must understand before editing:
- File or directory moves
- Public entry point changes, config/runtime path changes, database schema migrations
- Compatibility shims, deprecated paths, or follow-up cleanup that cannot be guessed from Git history alone

Do not write migration notes for ordinary bug fixes. Keep each note short: date, reason, old path/API, new path/API, compatibility impact, verification command, and rollback if relevant.