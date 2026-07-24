# MIGRATION-20260724：Qt-only 界面收敛

## 日期

2026-07-24

## 原因

项目决定不再维护 CTk，统一使用 PySide6 + QFluentWidgets，避免双界面入口、依赖和重复人工验收。

## 变更

- `app.main`：默认从 CTk `ui.shell` 改为 `ui_qt.workbench_window.main`。
- `src/fwasset/ui/`：CTk 壳、面板、操作面板和专属测试删除。
- `src/fwasset/ui/view_models/` 与 `ui/workbench_helpers.py`：迁移到 `src/fwasset/ui_common/`，供 Qt 使用。
- `customtkinter`：从运行依赖移除；PySide6 与 QFluentWidgets 成为主依赖。
- `fwasset.spec`：改用 `src/fwasset/app.py` 入口，移除旧 CTk/Pillow/serial 隐藏导入，保留 Qt 收集。

## 影响

- `uv run fwasset` 直接启动 Qt，不再需要设置 `FWASSET_UI=qt`。
- `FWASSET_UI=ctk` 不再可用；B3 及后续只做 Qt 验收。
- 固件目录、型号配置、平台配置和核心服务契约不变。

## 验证

- .\scripts\test.ps1：350 passed，coverage 93.34%。
- Qt smoke 与入口测试：20 passed，1 warning。
- `uv run pyinstaller fwasset.spec --noconfirm`：构建成功，生成 `dist/fwasset.exe`。
- Qt 人工验证：2026-07-23 完成，B2 三个场景全部通过（首次登记、冲突覆盖、取消共享不删本地文件）。

## 回滚

回滚本次 Qt-only 提交即可恢复旧 UI 目录、依赖和入口；不涉及固件数据文件。
