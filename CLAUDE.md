# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Read AGENTS.md first

`AGENTS.md` is the canonical, detailed contract for this repo (domain TypedDicts, service error codes, panel registry, coding style, doc-naming, and the **mandatory human-verify-before-commit workflow**). This file only adds the project-level context and the parts of the domain model that postdate AGENTS.md. When the two disagree on a concrete table (e.g. `SCHEMA_VERSION`), trust the source files referenced below — AGENTS.md was written at Schema v2 and the code is now at v3.

## Commands

```bash
uv sync --extra dev                                          # Install deps
uv run fwasset                                               # Run the desktop app
uv run python -m pytest -q                                   # Full suite (coverage gate >= 80%)
uv run python -m pytest -m "not ui" -q                       # Skip display-dependent tests
uv run python -m pytest src/fwasset/tests/test_file_scan.py -q --no-cov   # Single file, no coverage
.\scripts\test.ps1                                           # Canonical Windows gate
uv run pyinstaller fwasset.spec                              # Build the exe
```

No lint/type-check tooling is configured. Coverage omits `app.py` and `ui/*` (see `pyproject.toml`). UI tests carry `@pytest.mark.ui`.

## What this app is for

Massage-chair firmware asset manager. The current focus is making firmware **searchable and browsable** across a deeply-nested, inconsistently-named directory tree (the "L36程序" reorganization), so a user can find a program by型号 / 模块 / 具体需求 (language, feature) fast. Flash automation exists but the searching/browsing UX is the active surface. The eventual goal is full CRUD over programs plus launching the matching flash tool.

## Domain model — the 通用/定制 scheme system (postdates AGENTS.md)

This is the central concept and is **not** in AGENTS.md. The firmware root (e.g. `L36程序/`) splits into two first-level dirs:

- **`通用/` (common)** — shared modules. One module (e.g. 蓝牙程序) may hold several *variants* (subdirs like `英文-通用`, `中文-通用_默认`). A subdir whose name contains `_默认` is the **default variant** used to fill gaps in custom schemes.
- **`定制/` (custom)** — per-customer whole-chair schemes. Each scheme dir holds a `方案配置.toml` (`name`, `platform`) and only the modules that differ from common. Missing modules are **filled from `通用/`** (internally called "回源 / fallback") based on `平台配置.toml` defaults.

A massage chair typically contains multiple modules (主板, 手控UI, 蓝牙, etc. — not every model has all, and some may have extra specialized modules). The workbench presents them dynamically: it groups variants by module and sorts them using a **preferred display order** for common modules (`STANDARD_MODULE_ORDER` in `view_models/scheme_workbench_model.py`). Any non-standard modules are simply appended to the list.

### Key files for the scheme system

- `core/scheme_config.py` — `discover_schemes(model_root)` walks `定制/*/方案配置.toml` → `SchemeConfig(name, platform, path)`. `scheme_for_path()` maps an asset path back to its scheme.
- `core/platform_config.py` — `load_platform_config(model_root)` reads `平台配置.toml` (`[[platform]]` + `[platform.defaults]` mapping `module_dir → variant_name`). Drives fallback selection.
- `core/file_scan.py` — `_infer_asset_context()` derives `(category, platform, scheme_name, scheme_path)` from an asset's path relative to root: a `通用` path segment ⇒ `category="common"`, a `定制` segment ⇒ `category="custom"` + scheme lookup.
- `ui/view_models/scheme_workbench_model.py` — `SchemeWorkbenchModel` is the brain of the UI. `build_sidebar_tree()` returns `{common: {label: count}, custom: [scheme...]}`; `get_scheme_module_tree()` produces the grouped rows dynamically with fallback applied.

### UI-facing language rules (hard constraints)

- The user-visible source label is **only** `定制专属` (custom-exclusive) or `通用默认` (common-default). The word **"回源" must never appear in UI text** — it is an internal term only. See `ModuleVariant.source_label` / `ModuleRow.source_label`.
- 型号 list is derived from **directory structure**, NOT from parsing filenames — filenames contain noise like `L50S` that would pollute the model list. Memory notes record prior bugs here ([[workbench-ui-p0-fixes]]). Two layouts (auto-detected in `_detect_single_model_root()`): a scan root containing `通用/定制` directly is a **single-model root** (model = root dir name, `L36程序` → `L36`); otherwise it is a **multi-model parent** (e.g. `按摩器程序/`) whose first-level subdirs are each a model. Platform configs are **scoped per model** (`_platforms_by_model`) — never let one model's platforms/defaults leak into another.

### Platform defaults (设为平台默认)

The default variant used for scheme fallback is defined **only** by `平台配置.toml` `[platform.defaults]` (the `_默认` dir-name suffix is legacy display, never a write target). The workbench lets the 烧录员 set it: right-click a common variant → 设为平台默认 → `core/services/platform_default_service.py::set_default_variant` rewrites the model's `平台配置.toml` (via `save_platform_config`), then the model reloads platforms in place — fallback and the `★默认` badge update **without a rescan** (defaults are read live from toml, not indexed).

## Architecture deltas vs. AGENTS.md / docs/README.md

The UI was rewritten around the workbench; several files those docs mention are **gone or replaced**:

- Entry: `app.main` → `shell.UnifiedFlashPlatform` (CTk root) → mounts a single `ui/workbench_panel.py::WorkbenchPanel` (a `BaseFlashPanel`). The old `firmware_list_panel`, `asset_tree`, `sidebar_panel`, `handcontrol_panel`, and the `asset_filter_model` / `asset_selection_model` / `tree_expansion_model` view-models have been removed — don't reference them.
- New surfaces: `ui/panels/data_grid_panel.py`, `ui/view_models/scheme_workbench_model.py`. Operation panels (`auto_usb`, `tool_launch`, `manual_doc`, `disabled`) and their registry/`PanelHost` protocol are unchanged — AGENTS.md's section on them still applies.
- **Database: `SCHEMA_VERSION = 3`** (`core/asset_index.py`). v2→v3 adds `category`, `platform`, `scheme_name`, `scheme_path` columns + indexes on `category`/`scheme_name`. `query_assets()` gained `category=` and `scheme_name=` filters. Mismatched local index versions raise and require a re-scan.
- `core/types.py::FirmwareAsset` now carries `category: Literal["common","custom",""]`, `platform`, `scheme_name`.

## Where to find planning context

`specs/active/` holds the live task plans (the UI-rewrite and workbench-optimization specs are the current ones). Live code reviews live in `docs/code-review/` (currently `REVIEW-20260709-branch-pyside6.md`); closed reviews are under `docs/code-review/archive/` — check those before re-litigating settled decisions.
