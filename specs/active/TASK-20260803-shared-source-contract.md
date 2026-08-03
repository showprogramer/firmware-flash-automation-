# TASK-20260803-shared-source-contract：共享来源模块一致性与登记对话框优化 `complexity: high`

## 状态

| 项 | 状态 |
| --- | --- |
| 类型 | core 服务契约 + Qt UI 修复 |
| 当前状态 | ✅ 人工验证通过，记录已更新 |
| 前置 | Phase B2/Phase C 共享登记已完成；R5 路径守卫已合入 |
| 分支 | `feature/pyside6-migration` |
| 完成 commit | 本次提交 |

## 复杂度理由

改动同时收紧共享登记服务的输入契约，并改变 Qt 登记入口的候选范围与交互层级；需要防止错误配置写入、保留固定版本和自动更新两种登记模式，并进行服务与界面回归。

## 目标

共享来源只能用于同一规范模块。登记弹窗只展示“当前模块、其它型号”的来源资产，不再允许放开到全部资产；服务层必须独立拒绝模块不一致的请求，确保任何调用方都不能写入错误关联。

## 关键决策

- `set_shared_module()` 以 `canonical_module_dir()` 得到目标模块键与来源模块键；两者不一致时返回 `module_mismatch`，且不写入 `型号配置.toml`。
- 来源资产缺少可识别模块键时返回 `invalid_args`；不再用目标模块键代替来源模块键。
- Qt 候选始终限定为“非目标型号 + 同一规范模块”；移除“只看同模块名 / 看全部”切换。
- 对话框采用单一主操作：标题和说明明确当前模块，候选行展示“型号 · 变体”及第二行完整路径；完整路径可换行并保留 tooltip。
- 无候选时显示明确空状态，确认按钮不可用；有候选但未选择时确认按钮同样不可用。
- 固定版本与自动更新模式保持原有语义；仅自动更新时显示来源平台选择。

## 文件变更

### Task 1：服务层模块一致性契约 `complexity: medium`

**复杂度理由：** 单一 service 的错误码和写入前校验变化，必须证明不匹配来源不会落盘。

**Files:** `src/fwasset/core/services/shared_module_service.py`、`src/fwasset/tests/test_shared_module_service.py`

- 在写入前对比来源资产模块键与目标模块键。
- 新增不匹配来源的回归用例，断言 `module_mismatch` 与配置文件未创建。

### Task 2：Qt 来源选择收敛与视觉优化 `complexity: medium`

**复杂度理由：** 变更候选构建、空状态、选择状态和对话框层级，须保留 Phase C 的模式与平台联动。

**Files:** `src/fwasset/ui_qt/workbench_window.py`、`src/fwasset/ui_qt/design_tokens.py`、`src/fwasset/ui_common/workbench_helpers.py`、`src/fwasset/tests/test_ui_common_helpers.py`、`src/fwasset/tests/test_qt_smoke.py`

- 移除跨模块候选和切换按钮。
- 将来源项改为两行信息，使用现有间距令牌与 QFluentWidgets 主/次按钮。
- 覆盖候选范围、无选择禁用确认、模块说明文案与自动更新平台联动的 Qt 场景。

### Task 3：验证与收口 `complexity: low`

**复杂度理由：** 仅记录自动化结果、人工检查项、Review 结论与变更记录。

**Files:** 本 Task、`docs/code-review/archive/REVIEW-20260803-shared-source-contract.md`、`docs/code-review/README.md`、`docs/CHANGELOG.md`

## 非目标

- 不改变共享引用 TOML schema、解析器或已有引用的读取行为。
- 不新增跨型号批量登记、迁移或 CRUD 功能。
- 不改变固定版本和自动更新的解析语义。
- 不修改工作区路径守卫。

## 验收标准

- 不同模块的来源无法通过 Qt 入口选择，也无法通过 `set_shared_module()` 写入。
- 相同模块的其它型号来源仍可正常登记；冲突确认、固定版本和自动更新可用。
- 弹窗不再有“看全部”切换，来源列表清晰展示型号、变体和完整路径。
- 无可用来源或尚未选择来源时，确认登记不可用并给出明确提示。

## 验证记录

- 自动化验证：
  - `.venv-wsl/bin/python -m pytest src/fwasset/tests/test_shared_module_service.py src/fwasset/tests/test_ui_common_helpers.py -q --no-cov -p no:cacheprovider` → 19 passed。
  - `.venv-wsl/bin/python -m pytest src/fwasset/tests/test_qt_smoke.py::test_shared_source_picker_excludes_other_modules src/fwasset/tests/test_qt_smoke.py::test_shared_source_picker_requires_explicit_selection -q --no-cov -p no:cacheprovider` → 2 passed。
  - `.venv-wsl/bin/python -m pytest -m "not ui" -q --no-cov -p no:cacheprovider` → 374 passed，3 个既有 Windows 路径语义用例失败（`test_file_scan` ×1、`test_settings` ×2），本任务定向用例通过。
  - `.venv-wsl/bin/python -m pytest src/fwasset/tests/test_qt_smoke.py -q --no-cov -p no:cacheprovider` → 26 passed，1 个既有侧栏重选用例失败；本任务新增 Qt 用例通过。该套件同时因受限运行环境无法写入 `.runtime/logs/app.log` 输出日志错误。
- 人工验证（Windows，2026-08-03）：用户确认同模块登记、不同模块不可见、固定版本、自动更新与无候选禁用确认均通过。
- Review：已完成并归档。
- CHANGELOG：已同步。
- 迁移说明：不适用。

## Task DoD

- [x] 服务层模块一致性校验与回归测试完成
- [x] Qt 候选范围和登记对话框优化完成
- [x] 自动化验证已记录
- [x] 人工验证已记录
- [x] Review 已完成
- [x] CHANGELOG 已同步
- [x] 迁移说明不适用已确认
