# TASK-20260706 · UI Code Review Bugfix Plan

> 来源：`docs/code-review/ui_code_review.pdf` 第 6 节「具体代码缺陷与待修复清单」
> 当前基线：Step D 已提交（`refactor(ui): polish workbench step d experience`）。
> 目标：只修第 6 节确认存在的问题，不混入新的视觉重构。

---

## 0. 范围确认

### 确认需要修复

1. `BaseFlashPanel._poll_task_queue()` 缺少窗口销毁保护。
2. `WorkbenchPanel._refresh_sidebar_tree()` 在搜索输入时整棵侧栏销毁重建，存在闪烁/卡顿风险。
3. `SchemeWorkbenchModel` 多个查询接口重复调用 `query_assets()`，存在性能风险。
4. `PanelHost` Protocol 缺少 `get_global_usb_drive()` 声明。
5. `shared_actions.py` 仍有硬编码 `padx=20`。
6. `workbench_panel.py` 有方法内本地导入，可整理到文件顶部。

### 暂不作为本轮必修

- `WorkbenchPanel._handle_scan_result()` 中 `db_path = None`：
  当前 `asset_index._db_path(None)` 会走默认 `ASSET_INDEX_PATH`，不是当前功能缺陷。
  仅在后续支持多数据库/可配置索引路径时再单独设计。

---

## 1. 修复顺序

优先级按风险和改动面排序：

1. P0：补 `PanelHost.get_global_usb_drive()` 协议声明。
2. P0：给 `_poll_task_queue()` 增加销毁保护，避免窗口关闭后的 Tk 回调继续触达控件。
3. P1：给搜索刷新加 debounce，降低 `_refresh_sidebar_tree()` 高频销毁重建。
4. P1：给 `SchemeWorkbenchModel` 增加资产缓存，减少同一 UI 刷新中的重复 SQLite 查询。
5. P2：清理 `shared_actions.py` 硬编码间距。
6. P2：整理 `workbench_panel.py` 方法内 import。

---

## 2. Todo

### P0-1 · 补齐 PanelHost 协议

- [ ] 测试先行：在 `test_operation_panels.py` 或新增 helper 测试中断言 `PanelHost` 暴露 `get_global_usb_drive`。
- [ ] 在 `src/fwasset/ui/operation_panels/host_types.py` 增加：
  `def get_global_usb_drive(self) -> str: ...`
- [ ] 验证 `AutoUsbPanel._resolve_drive()` 依赖的宿主契约在 Protocol 中可见。

验收：
- [ ] 相关测试通过。
- [ ] 不改 UI 行为。

### P0-2 · `_poll_task_queue()` 窗口销毁保护

- [ ] 测试先行：覆盖 `_poll_task_queue()` 在控件已销毁/不存在时直接返回，不继续调用 `on_done` 或 `after`。
- [ ] 在 `BaseFlashPanel._poll_task_queue()` 开头检查 `winfo_exists()`。
- [ ] 在继续安排 `self.after(120, ...)` 前再次检查窗口仍存在。
- [ ] 需要时对 `on_done(payload)` 做最小防护，避免回调异常让轮询状态卡死。

验收：
- [ ] 关闭窗口后后台任务完成不抛 `TclError`。
- [ ] 正常后台任务完成流程不变。

### P1-1 · 搜索刷新 debounce

- [ ] 测试先行：快速触发多次 `_on_search_changed()` 时，只保留一次延迟刷新任务。
- [ ] 在 `WorkbenchPanel` 增加 `_search_after_id` 或类似字段。
- [ ] `_on_search_changed()` 不直接刷新侧栏/主表，改为取消旧 `after` 并延迟 150-200ms 执行。
- [ ] 延迟回调执行前确认窗口仍存在。

验收：
- [ ] 快速输入搜索时侧栏不再每个按键立即整树销毁重建。
- [ ] 停止输入后筛选结果仍正确刷新。
- [ ] 型号切换、扫描完成等非搜索路径不被 debounce 误延迟，除非代码明确复用同一刷新入口。

### P1-2 · `SchemeWorkbenchModel` 资产查询缓存

- [x] 测试先行：monkeypatch `query_assets` 计数，验证一次 `bind()` 后常用视图方法复用缓存。
- [x] 在 `SchemeWorkbenchModel.bind()` 阶段加载一次全部资产到实例缓存。
- [x] `_load_model_root_paths()`、`load_all_models()`、`build_sidebar_tree()`、`get_common_modules()`、`get_scheme_modules()`、`get_all_modules()` 优先从缓存过滤。
- [x] 保留缓存为空或未 bind 时的兼容退化路径。
- [x] 关键字过滤必须保持当前语义，不改变用户搜索结果。
- [x] **BUG-2 复刻**：`_filter_assets` 复刻 `query_assets` 的「空格分词 AND 跨字段 OR」语义（10 字段 OR + token 间 AND）。
- [x] **BUG-1 修复**：给 `ModuleCardData` 加 `source_kind` 字段；3 个 caller 显式写入；`get_scheme_module_tree` 改读 `source_kind`，不再用 `is_fallback` 推断。

验收：
- [x] 同一 UI 刷新中 SQLite 查询次数明显下降。
- [x] `get_scheme_module_tree()` 输出顺序、归属文案、回源逻辑不变。
- [x] 现有 `scheme_workbench_model` 相关测试全部通过。
- [x] 「主板 防夹」类空格分词 AND-OR 搜索返回正确子集。
- [x] 通用模块的归属显示「通用默认」而非「定制专属」。

### P2-1 · 清理 `shared_actions.py` 硬编码间距

- [ ] 测试/静态断言：`shared_actions.py` 不再出现 `padx=20`。
- [ ] 用 `SPACE_LG` 或符合当前 UI 密度的 token 替代硬编码数值。

验收：
- [ ] 操作面板布局无明显变化或更统一。

### P2-2 · 整理 `workbench_panel.py` 方法内 import

- [ ] 将 `_open_current_asset_dir()` 内的 `import os, subprocess` 移到文件顶部。
- [ ] 将 `_start_scan()` 内的 `from tkinter import filedialog` 移到文件顶部。
- [ ] 保持调用逻辑不变。

验收：
- [ ] `py_compile` 通过。
- [ ] 扫描目录选择、双击/打开目录逻辑不变。

---

## 3. 验证命令

每个小步至少运行相关测试；全部完成后运行：

```powershell
python -m py_compile src\fwasset\ui\base_panel.py src\fwasset\ui\workbench_panel.py src\fwasset\ui\operation_panels\host_types.py src\fwasset\ui\operation_panels\shared_actions.py src\fwasset\ui\view_models\scheme_workbench_model.py
.\.venv\Scripts\python.exe -m pytest src\fwasset\tests\test_operation_panels.py src\fwasset\tests\test_workbench_panel_helpers.py -q --no-cov
.\.venv\Scripts\python.exe -m pytest -m "not ui" -q --no-cov
```

若新增/修改 `scheme_workbench_model` 专项测试，同步加入相关测试命令。

---

## 4. 文档与提交流程

- [ ] 更新 `docs/CHANGELOG.md`，记录 UI review bugfix。
- [ ] 新建或更新 `docs/code-review/REVIEW-20260706-ui-review-bugfix.md`。
- [ ] 本任务涉及 UI 稳定性与性能，提交前必须按 AGENTS.md 先提示人工验证。
- [ ] 人工确认后再按 Conventional Commit 提交。

建议提交拆分：

1. `fix(ui): harden workbench task polling and host contract`
   - P0-1、P0-2。
2. `perf(ui): debounce workbench search refresh`
   - P1-1。
3. `perf(ui): cache scheme workbench assets`
   - P1-2。
4. `refactor(ui): clean minor review findings`
   - P2-1、P2-2。
