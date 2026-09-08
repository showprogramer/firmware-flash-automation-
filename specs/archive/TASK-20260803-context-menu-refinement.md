# TASK-20260803-context-menu-refinement：右键菜单与默认模块键一致性 `complexity: medium`

## 状态

| 项 | 状态 |
| --- | --- |
| 类型 | Qt UI 优化 + 默认模块键一致性修复 |
| 当前状态 | ✅ 人工验证通过，记录已更新 |
| 前置 | 共享来源登记与模块一致性约束已完成 |
| 分支 | `feature/pyside6-migration` |
| 完成 commit | `31f9efd` |

## 目标

将工作台资产行的右键菜单收敛为清晰的操作层级：默认版本操作、共享来源操作、目录操作分组呈现；已是默认仅在表格中表达，不再以低对比度禁用菜单项占据菜单首行。

## 文件变更

### Task 1：菜单状态与动作层级 `complexity: medium`

**Files:** `src/fwasset/ui_qt/workbench_window.py`、`src/fwasset/ui_common/workbench_helpers.py`

- 默认版本已生效时隐藏菜单项；未生效时保留设置操作。
- 已有共享来源时将登记操作改为“更换共享来源…”，并与取消操作归入共享来源组。
- 动作采用一致的 QFluent 图标，并将目录操作置于末尾。

### Task 2：Qt 回归与验证 `complexity: low`

**Files:** `src/fwasset/tests/test_qt_smoke.py`、本 Task

- 覆盖默认状态不显示禁用项、共享状态的更换/取消文案与动作分组。
- 记录 WSL 自动化结果与 Windows 人工验证。

### Task 3：默认模块键归一 `complexity: medium`

**Files:** `src/fwasset/core/platform_config.py`、`src/fwasset/core/services/platform_default_service.py`、`src/fwasset/core/shared_module_resolver.py`、`src/fwasset/ui_common/view_models/scheme_workbench_model.py` 及对应测试

- 将“快捷键”等历史目录短键归一为 catalog 规范键“快捷键程序”。
- 读取重复 defaults 时优先规范键；写入默认时合并并移除旧键。
- 覆盖默认徽章、方案补齐、自动更新共享来源与写入合并。

## 验收标准

- 已是默认的资产不显示灰色禁用菜单项；未设默认的通用资产仍可设为默认。
- 同一逻辑模块的目录短键与规范键不得同时产生默认状态；下次设置默认后 TOML 仅保留规范键。
- 已登记共享来源时显示“更换共享来源…”和“取消共享来源”，未登记时只显示“登记共享来源…”。
- 所有菜单动作有一致图标，默认、共享与目录操作具有明确分组。
- 原有设默认、共享登记/取消、打开目录、复制路径行为不变。

## 验证记录

### 自动化验证（已完成）

| 平台 | 环境 | 命令 | 结果 |
| --- | --- | --- | --- |
| WSL/Linux | `.venv-wsl` | `.venv-wsl/bin/python -m pytest src/fwasset/tests/test_ui_common_helpers.py src/fwasset/tests/test_qt_smoke.py::test_context_menu_hides_default_status_and_uses_replace_actions src/fwasset/tests/test_qt_smoke.py::test_context_menu_groups_default_register_and_directory_actions -q --no-cov -p no:cacheprovider` | 通过（3 passed） |
| WSL/Linux | `.venv-wsl` | `.venv-wsl/bin/python -m pytest src/fwasset/tests/test_platform_default_service.py src/fwasset/tests/test_scheme_workbench_model.py::test_shortcut_alias_duplicate_prefers_catalog_key_for_badge_and_fallback src/fwasset/tests/test_shared_module_resolver_phase_c.py::test_follow_default_prefers_canonical_shortcut_key -q --no-cov -p no:cacheprovider` | 通过（24 passed） |

- 已知平台差异：无。
- 提交：`31f9efd`

### 人工验证（已完成）

- 平台：Windows 实机
- 结论：用户确认右键菜单优化、默认切换、重复“快捷键 / 快捷键程序”键的单默认显示与 TOML 合并均通过（2026-08-03）。

- Review：已完成并归档。
- CHANGELOG：已同步。
- 迁移说明：不适用。

## Task DoD

- [x] 菜单层级与文案优化完成
- [x] Qt 回归测试完成
- [x] 自动化验证已记录
- [x] 默认模块键归一与回归测试完成
- [x] 人工验证已记录
- [x] Review 已完成
- [x] CHANGELOG 已同步
- [x] 迁移说明不适用已确认
