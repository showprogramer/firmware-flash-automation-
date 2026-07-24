# REVIEW-20260724：Qt 唯一支持界面清理

| 项 | 内容 |
| --- | --- |
| 类型 | UI 入口、依赖与目录重构 |
| 模块 | `src/fwasset/app.py`、`ui_qt/`、`ui_common/`、PyInstaller、项目文档 |
| 状态 | ✅ 已闭环；Qt 人工验证通过（2026-07-23） |
| 相关 TASK | `specs/active/TASK-20260724-qt-only-ui-cleanup.md` |
| 分支 | `feature/pyside6-migration` |

## 审查议题

### Issue 1：默认入口与依赖收敛 `complexity: high`

**复杂度理由：** 入口、主依赖、锁文件和 PyInstaller 入口同时调整，影响运行时启动与冻结交付。

- `app.py` 默认直接进入 `ui_qt.workbench_window.main`。
- `customtkinter` 从运行依赖和 `uv.lock` 移除，PySide6/QFluentWidgets 进入主依赖。
- `fwasset.spec` 使用 `src/fwasset/app.py` 作为分析入口，并收紧隐藏导入。

状态：✅ 自动化验证通过；冻结 exe 已成功构建。

### Issue 2：共用逻辑迁移与 CTk 物理退役 `complexity: high`

**复杂度理由：** 跨目录移动 ViewModel/助手并删除旧壳、专属测试，需同时保证 Qt 导入和覆盖率门禁。

- 共用模块迁移至 `src/fwasset/ui_common/`。
- 删除旧 `src/fwasset/ui/` CTk 壳、面板和专属测试。
- Qt 测试改为使用 `ui_qt` 与 `ui_common`，不保留 CTk 回退分支。

状态：✅ `20 passed` Qt 相关测试；非 UI/canonical 套件 `350 passed`，coverage `93.34%`。

### Issue 3：B2/B3 验收口径统一为 Qt `complexity: medium`

**复杂度理由：** 不改共享四字段语义，只调整人工验收壳与文档口径，需避免把未执行的现场验证误记为完成。

- B2 三个场景保留：首次登记、冲突覆盖、取消共享且本地文件不变。
- B3 及后续只安排 Qt，不再安排 CTk 第二套场景。
- `docs/CHANGELOG.md`、迁移说明和配置接管 TASK 已同步 Qt-only 结论。

状态：✅ 用户已于 2026-07-23 在测试副本完成 Qt 三场景验证并确认通过。

## 验证记录

```text
uv run python -m pytest -m "not ui" -q
→ 350 passed；coverage 93.34%

uv run python -m pytest src/fwasset/tests/test_qt_smoke.py src/fwasset/tests/test_app_entry_qt_only.py src/fwasset/tests/test_ui_common_imports.py src/fwasset/tests/test_ui_common_helpers.py -q --no-cov
→ 20 passed, 1 warning；canonical `scripts/test.ps1` 同样通过

uv run pyinstaller fwasset.spec --noconfirm
→ 构建成功，生成 dist/fwasset.exe
```

人工验证记录：2026-07-23，用户使用 Qt 测试副本完成 B2 三场景：首次登记、冲突选择“否/是”、取消共享且本地文件大小与修改时间不变；结果通过。

## 相关文件

- `docs/migrations/MIGRATION-20260724-qt-only-ui.md`
- `docs/CHANGELOG.md`
- `specs/active/TASK-20260724-qt-only-ui-cleanup.md`