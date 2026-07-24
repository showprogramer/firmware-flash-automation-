# Repository Guidelines (项目规范)

## 上下文加载纪律（强制 · 跨 Agent 适用）

本节约束 **所有 agent**（Claude Code / Codex CLI / Cursor / Aider 等）在浏览代码时的默认行为。配套忽略文件：`.claudeignore` / `.codexignore` / `.cursorignore`（内容同源，保持同步）。

### 禁止默认读取

下列文件 / 目录命中后**直接跳过**，不要展开报告内容、不要 `cat` 全文、不要纳入 diff 讨论：

- **本地敏感配置**：`config.toml`、`.env` / `.env.*`、`*.pem` / `*.key` / `*.cert`、`.claude/settings.local.json`、`.mcp_config*.json`
- **运行时与缓存**：`.runtime/`、`.venv/` / `.venv-wsl/`、`__pycache__/`、`*.pyc` / `*.pyo`、`.coverage`、`htmlcov/`、`.pytest_cache/`、`.hypothesis/`、`.mypy_cache/`、`.ruff_cache/`
- **构建产物**：`dist/`、`build/`、`fwasset.db*`、`*.spec`（保留 `fwasset.spec`）、`*.egg-info/`
- **公司内部文档**：`massagechairproject.md`、`specs/project-overview.md`、`specs/archive/`、`specs/prompts/`、`specs/ui-reactor/`
- **临时办公文件**：`*.xlsx` / `*.xls`、`手控UI问题汇总.xlsx`、`现有摩众手控UI明细表.xlsx`、`*.tmp` / `*.bak`、`Thumbs.db` / `.DS_Store` / `nul`
- **Agent / IDE 本地配置**：`.vscode/`、`.idea/`、`.claude/`、`.opencode/`、`.codex/`、`.agents/`、`.cursor/`、`.aider*`、`.continue/`、`logs/`、`*.swp` / `*.swo`

需要查询本地配置时，**只能读 `config.example.toml`**；真值在用户本地 `config.toml` 里，由人按需粘贴相关片段。

### 当前任务优先读取范围

默认优先读取：

- `src/fwasset/core/` 中与当前功能直接相关的模块；
- `src/fwasset/ui_qt/` 与 `src/fwasset/ui_common/`；
- `src/fwasset/tests/` 中与当前任务相关的测试；
- `specs/active/` 当前任务文件；
- `docs/CHANGELOG.md` 的 `Unreleased` 区域。

除非任务明确要求，不要全文读取：

- `docs/code-review/archive/`；
- 已完成的历史 TASK；
- 与当前功能无关的 service、USB、音乐烧录模块；
- `docs/CHANGELOG.md` 的历史大段内容。

### 命令习惯

- `find` / `ls -R` 默认加 prune：`-path ./.venv -prune -o -path ./.runtime -prune -o ...`
- `grep` / `rg` 默认走 gitignore：`rg` 自动尊重 `.gitignore`；`grep --exclude-dir=.venv --exclude-dir=.runtime`
- 不要用 `cat <sensitive-file>`，要先征求人工确认
- 涉及 USB 设备 / 路径 / 序列号时，用占位符描述（如 `<USB_DRIVE>`），不引用真实值

### 修改 ignore 文件的流程

改动 `.claudeignore` / `.codexignore` / `.cursorignore` 时必须**三处同步**，并在 commit message 注明。三份文件内容应完全一致，只允许顶部注释不同。

## Project Structure & Module Organization

Python desktop application for managing firmware assets. Source code under `src/fwasset/`:

- Core domain logic → `core/` (scanner, index, types, settings, services)
- Service modules → `core/services/` (scan_service, flash_service, usb_repair_service, music_flash_service)
- Qt UI workbench and panels → `ui_qt/`
- Framework-neutral ViewModels and helpers → `ui_common/`
- Console entry point → `fwasset.app:main`
- Tests → `src/fwasset/tests/` (use `test_*.py` naming)
- Specs & plans → `specs/` (active, decisions, archive, prompts)
- User docs → `docs/README.md`, change history → `docs/CHANGELOG.md`
- Runtime data → `.runtime/` (logs, indexes); **never commit** `config.toml`, `fwasset.db`, or `.runtime/`

Build system: `hatchling` (not setuptools). Package: `packages = ["src/fwasset"]`.

## Build, Test & Lint Commands

```bash
uv sync --extra dev                                         # Install dependencies
uv run fwasset                                               # Run desktop application
uv run python -m pytest -q                                   # Full test suite (with coverage)
uv run python -m pytest src/fwasset/tests/test_asset_index.py -q --no-cov  # Single file, no coverage
uv run python -m pytest -m "not ui" -q                       # Skip display-dependent tests
.\scripts\test.ps1                                           # Canonical Windows verification
```

There are **no standalone lint or type-check commands** configured (no ruff, mypy, flake8). Coverage gate: >= 80% for `src/fwasset`. Coverage omits `src/fwasset/app.py` and `src/fwasset/ui_qt/*`; `src/fwasset/ui_common/*` remains covered. Run `.\scripts\test.ps1` as canonical gate.

## Domain Types & Contracts (`core/types.py`)

**TypedDicts** — treat as canonical data shapes, never add fields without updating the definition:

| TypedDict | Key Fields |
|-----------|------------|
| `FirmwareAsset` | `series`, `model`, `version`, `firmware_type`, `firmware_label`, `flash_mode`, `usb_flow`, `path`, `directory_name`, `model_directory_name`, `model_directory_path`, `files: list[str]`, `modified_time: float`, `tool_name`, `tool_path`, `tool_dir`, `label`, `category` ("common"/"custom"/""), `platform`, `scheme_name`, `scheme_path` |
| `ServiceResult` | `ok: bool`, `code: str`, `message: str`, `payload: dict[str, Any]` |
| `HandcontrolFolder` | `path`, `rom_file`, `pkg_file`, `model`, `version`, `label` |
| `ToolRegistration` | `name`, `path`, `directory` |
| `SerialPortInfo` | `device`, `description`, `hwid` |
| `FlashJobResult` | `ok: bool`, `code: str`, `message: str`, `payload: FlashJobPayload` |

**Literals:**
- `FlashMode`: `"auto_usb"`, `"tool_launch"`, `"manual_doc"`, `"disabled"`
- `UsbFlow`: `"paired_files"`, `"directory_copy"`, `""`
- `FirmwareType` (20 values): `mainboard`, `handcontrol_ui`, `music_bt`, `music_files`, `voice`, `shortcut_key`, `movement_3d`, `movement_2d`, `knob_switch`, `leg`, `knee`, `sonic`, `health_detection`, `commercial_mainboard`, `seat_occupancy`, `card_reader`, `leyao_yao`, `triple_combo`, `aging`, `segmented_screen`
- `HiddenItemType`: `"model_directory"`, `"firmware_type"`, `"asset"`

## Database Schema (`core/asset_index.py`)

`SCHEMA_VERSION = 3`. Tables: `assets` (PK: `path`), `hidden_items` (PK: `path`), `scan_meta` (PK: `root_dir`), `schema_meta`. Indexes on `firmware_type`, `model`, `model_directory_path`, `category`, `platform`, `scheme_name`. Migration v1→v2 adds `usb_flow` column, v2→v3 adds `category`, `platform`, `scheme_name`, `scheme_path` columns. `files_json` stores the file list as JSON.

**单工作区语义（非多根）**：索引一次只服务一个固件根目录。`save_assets` 全表替换 `assets`，并清空后只写入当前 `root_dir` 一行 `scan_meta`。换根扫描 = 切换工作区，不保留旧根资产。真相源是整理后的目录树 + TOML；SQLite 为搜索缓存。未来应用内 CRUD 后全量扫描退化为导入/修复冷路径，日常改行级写。

## Service Layer Conventions

All services in `core/services/` return `dict` matching `ServiceResult`: `{"ok": bool, "code": str, "message": str, "payload": dict}`. User-facing messages in **Chinese**. Specific error codes (never bare exceptions):

| Service | Error Codes |
|---------|-------------|
| scan_service | `"ok"`, `"cancelled"`, `"scan_failed"`, `"index_empty"`, `"index_unavailable"` |
| flash_service | `"ok"`, `"copy_failed"`, `"service_exception"` |
| usb_repair_service | `"ok"`, `"unhealthy"`, `"repair_failed"`, `"service_exception"` |
| music_flash_service | `"ok"`, `"format_failed"`, `"copy_failed"`, `"service_exception"` |

Services accept `log_fn=print` as default for dependency injection.

## Firmware Catalog (`firmware_catalog.toml`)

Defines 20 firmware type entries. Each entry maps `dir_keywords` (Chinese strings) and `file_extensions` to a `FirmwareType`. The scanner uses first-match semantics — catalog entry order matters. `handcontrol_ui` has a special rule: requires both `.rom` AND `.pkg` files present.

`FirmwareTypeConfig` TypedDict (in `firmware_catalog.py`): `key`, `label`, `dir_keywords`, `file_extensions`, `flash_mode`, `usb_flow`, `tool_name`, `tool_path`, `tool_dir`, `enabled`.

## Coding Style & Conventions

### Imports & Type Hints
- Always use `from __future__ import annotations` at the top of source files (enables `X | Y` union syntax).
- Import order: stdlib → third-party → `fwasset.*` local modules.
- Prefer type hints on all new helper functions and public methods.

### Naming
- Test files: `test_*.py` in `src/fwasset/tests/`
- Service modules: `_service.py` suffix (e.g. `scan_service.py`, `flash_service.py`)
- View models: clear nouns (e.g. `asset_filter_model.py`, `scan_state_model.py`)
- Private helpers: underscore prefix (`_db_path`, `_build_sidebar`, `_match_catalog_type`)
- Constants: `UPPER_SNAKE_CASE` at module top (e.g. `SCHEMA_VERSION`, `FONT_FAMILY`, `SCAN_EXCLUDE_DIR_KEYWORDS`)

### UI Patterns
- **Panel registry**: `@register` decorator + `get_panel(flash_mode)` in `ui_qt/operation_panels/registry.py`. Four Qt panels: `AutoUsbPanel`, `DisabledPanel`, `ManualDocPanel`, `ToolLaunchPanel`. New flash modes only need a new file under `ui_qt/operation_panels/`.
- **PanelHost protocol** (`host_types.py`): defines `usb_drive`, `_build_usb_selector_row()`, `_run_task()`, `_selected_asset()`, and tool-related methods.
- **Task queue**: `BaseFlashPanel._run_task()` spawns daemon threads; results via `queue.Queue`, polled with `self.after(120, ...)`.
- **View models**: standalone classes (e.g. `AssetSelectionModel`, `ScanStateModel`). Panels compose models; they do not inherit from them.
- **Design tokens**: Qt layout/theme values come from `ui_qt/design_tokens.py` and QFluentWidgets theme APIs. Shared ViewModels/helpers live under `ui_common/`. Never add CustomTkinter/tkinter imports or a second UI implementation.
- **Cancellation**: Use `threading.Event`. Create local `cancel_event` before spawning worker thread; capture in closure.
- **整机模块固定层级**: 按烧录习惯固定展示顺序（主板程序 → 手控UI → 蓝牙程序 → 语音程序 → 快捷键程序 → 3D机芯板程序 → 2D机芯板程序 → 腿部程序），大部分机型包含这些模块但非完整，缺失的模块不显示。单变体折叠为一行，多变体展开显示所有变体。

### Sorting
`SortKey` enum (`sort_config.py`): `PATH` (natural), `MODEL` (prefix+number+suffix), `VERSION` (semver-like). Used by `query_assets()` and `apply_sort()`.

### Config & External Files
- `config.toml` — local machine config (gitignored). Template: `config.example.toml`. Sections: `[paths]`, `[usb]`, `[scan]`, `[music]`.
- `firmware_catalog.toml` — firmware type definitions shipped with the app.
- `平台配置.toml` — platform default module variant configuration (located in firmware root directory).
- `定制/方案名/方案配置.toml` — custom scheme metadata (name, platform).
- Runtime dir: dev → `.runtime/`, frozen → `runtime/`, overridable via `FWASSET_RUNTIME_DIR`.
- Config loaded via `load_toml_config()` → returns `(data, status, error)` where status is `"ok"`, `"missing"`, or `"parser_missing"`.

## Testing Conventions

- Framework: pytest. Coverage gate: >= 80% for `src/fwasset`; `app.py` and `ui_qt/*` are omitted, while `ui_common/*` remains covered.
- `@pytest.mark.ui` for display-dependent tests; filter with `-m "not ui"`.
- Module-level factory functions (e.g. `make_asset()`) over `conftest` fixtures.
- Mocking: prefer `monkeypatch.setattr` with lambdas over `unittest.mock`.
- Assert service results by key: `assert result["ok"] is True`, `assert result["code"] == "ok"`.
- Error-path testing: `pytest.raises(SomeError, match="中文消息")`.
- Test `pythonpath = ["src"]` — imports work as `from fwasset.core.types import ...`.

## Document Naming Conventions

| Type | Directory | Naming | Example |
|------|-----------|--------|---------|
| Architecture Decision | `specs/decisions/` | `ADR-NNN-short-name.md` | `ADR-001-ui-core-separation.md` |
| Task / Plan | `specs/active/` | `TASK-YYYYMMDD-short-name.md` | `TASK-20260505-newtasks.md` |
| Migration Note | `docs/migrations/` | `MIGRATION-YYYYMMDD-short-name.md` | `MIGRATION-20260518-docs-consolidation.md` |
| Code Review | `docs/code-review/`（活文档）/ `docs/code-review/archive/`（已闭环） | `REVIEW-YYYYMMDD-short-name.md` | `REVIEW-20260709-branch-pyside6.md` |

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
6. **立项硬约束**：复杂度判定为 `xhigh` 的 TASK **必须先拆子 TASK 才能立项**；不拆直接立 xhigh 视为流程违规（见下方「复杂度标注」节）。

## 复杂度标注

每个 TASK 实施计划里的 **`### Task N` 子项**与 REVIEW **每条审查议题**（`### Issue N` / `### Rn`）都必须标注复杂度，供排期、风险预判与回归范围决策。一个 TASK 含 N 个 Task 子项就标 N 个复杂度——不是整个 TASK 文件单一标。

### 评级表

| 等级 | 判据 |
| --- | --- |
| `low` | 单文件 / 纯文档 / 测试补齐；无核心 API、无 schema、无 UI 交互变更 |
| `medium` | 多文件但单一关注点；含 UI 或 service 之一；测试用例 < 10 |
| `high` | 跨 core + UI 双层；动 `types.py` TypedDict / `ServiceResult` 结构 / 数据库 schema / 扫描或索引公共路径；需双壳人验 |
| `xhigh` | 跨多 Phase / 父任务主线；含 schema 迁移 + 公共 API 破坏性变更 + 双壳 UI + 现场数据语义变化；**必须拆子 TASK 才能立项**（见「Task Verification & Git Workflow」第 6 条） |

### 标注位置

- **TASK**：`### Task N：<名字>` 标题行**末尾**加 inline 徽章 `` `complexity: <级别>` ``；下一行 `**Files:**` 之前加一行 `**复杂度理由：** <一句话>`。
- **REVIEW**：`### Issue N (...)` 或 `### Rn (...)` 标题行**末尾**加 inline 徽章 `` `complexity: <级别>` ``；下一行（通常是 `**文件：**`）之前加一行 `**复杂度理由：** <一句话>`。理由对应**修复动作**的实施量级，不是审查发现难度。

### 标注时机与维护

- TASK 立项时初判每个 Task 子项；实施中若发现跨级上升须更新该子项复杂度并注明原因（一句话追加到「复杂度理由」末尾，形如 `（实施中升 medium→high：跨入 view model）`）。
- REVIEW 创建时复用其 TASK 的对应 Task 复杂度；若审查引出超出原 TASK 范围的改动，单独标并说明。
- **不追溯**已 commit / 已归档的 TASK 与 REVIEW；只对新立的强制要求。
- **禁止**以代码行数 / commit 体积 / "感觉复杂" 为判据。评级必须给出可复核的理由。

### 示例

```markdown
### Task 1：`set_shared_module` service（纯数据，无 UI）  `complexity: medium`

**复杂度理由：** 单 service 纯函数，无 UI / 无 schema / 无双壳；错误码 5 种、测试用例 ~7，越界与冲突分支为中粒度而非 low。
**Files:** Create `src/fwasset/core/services/shared_module_service.py`；Create `src/fwasset/tests/test_shared_module_service.py`
```

```markdown
### Issue 1（P1·阻断）：单型号根迁移会写入 `通用/型号配置.toml`  `complexity: medium`

**复杂度理由：** 修复加 `_target_model_root` 帮助函数 + 单条回归测试，单 service 单测；不动 schema / UI。
**文件：** `core/services/shared_migration_service.py:102-108`
```

## Code Review Automation

完成代码重构、修复、重大修改后，**自动**在 `docs/code-review/` 创建 `REVIEW-YYYYMMDD-short-name.md`，使用模板（类型、模块、问题描述、处理方案、状态、验证记录、相关Commit）。触发条件：`types.py` 变更、服务返回结构变更、注册表/UI入口变更、扫描/索引/USB流程修改、数据库schema迁移、公共API签名变更。议题全部关闭后将文件移入 `docs/code-review/archive/` 并更新 `archive/INDEX.md`（见 `docs/code-review/README.md`）。

## Migration Notes

Use `docs/migrations/` for changes that future agents must understand before editing: file/directory moves, public entry point changes, config/runtime path changes, database schema migrations, compatibility shims. Keep each note short: date, reason, old→new path/API, impact, verification command, rollback.
