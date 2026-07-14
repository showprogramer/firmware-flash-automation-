# 代码审查：UI 方案工作台模式重构

- 日期：2026-06-09
- 类型：重构 / UI 变更 / API 变更
- 模块：`ui/workbench_panel.py`, `ui/panels/module_card.py`, `ui/view_models/scheme_workbench_model.py`, `ui/shell.py`

## 问题描述
原有的 `FirmwareListPanel` 是基于「固件类型」的单列表界面，烧录员在拿到特定方案（例如“以色列-Royal-Z9”）时，无法在一个界面中看到该方案的所有模块全貌（包括定制的模块和通用回源的模块）。并且原先的交互流程冗长，无法快速定位同类型下的多个变体。由于旧的组件高度耦合，维护和进一步扩展都非常困难。

## 处理方案
1. **废弃旧组件**：删除了 `firmware_list_panel.py`、`asset_tree.py` 以及一系列废弃的视图模型。
2. **新增工作台面板**：引入全新的 `WorkbenchPanel` 取代原有入口。
3. **双驱导航树**：将左侧列表分为「通用模块区」与「定制方案区」，支持在下拉框进行型号智能切换。
4. **多维搜索联动**：顶部的搜索框不仅过滤右侧内容，也会实时更新左侧树中的数量角标。
5. **卡片流视图**：右侧详情区重写为模块卡片流 (`ModuleCard`)，并在卡片上增加了一键打开源文件夹的入口，且能够清晰标记模块来源（通用/定制/回源）。
6. **兼容历史 API**：原有的底层操作面板组件（`tool_launch` 和 `auto_usb`）成功迁移并无缝接入新的卡片结构中。扫描结果解析与目录配置也重新对齐到最新版本的 `scan_service.py` 接口。

## 验证记录
- 运行 `uv run python -m pytest -q --no-cov -m "not ui"`：底层测试全部通过。
- 运行 `uv run python -m pytest tests\test_app_service_smoke.py tests\test_operation_panels.py -q --no-cov`：修正后的 UI Smoke 和面板集成测试全部通过。
- 本地 GUI 测试验证：工作台面板能正常扫描目录，左侧树节点可折叠，点击定制方案时，右侧成功展示所有模块及其变体。

## 状态
- [x] 已完成重构
- [x] 等待用户人工验证通过后提交

## 关联 Commit
- （待确认后提交）`refactor(ui): rewrite UI into scheme workbench mode`
