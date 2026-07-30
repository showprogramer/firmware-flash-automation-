# 代码审查：UI Review Bugfix（性能 / 健壮性 / 契约）

- 日期：2026-07-06
- 类型：Bugfix / 性能 / 接口契约
- 模块：
  - `ui/operation_panels/host_types.py`（`PanelHost` 协议）
  - `ui/base_panel.py`（`_poll_task_queue` 销毁保护）
  - `ui/workbench_panel.py`（搜索 debounce、方法内 import 清理）
  - `ui/operation_panels/shared_actions.py`（间距 token 化）
  - `ui/view_models/scheme_workbench_model.py`（资产查询缓存）
- 来源：`docs/code-review/ui_code_review.pdf` 第 6 节「具体代码缺陷与待修复清单」+ `specs/archive/TASK-20260706-ui-review.md`

## 问题描述

`ui_code_review.pdf` 列出 6 项需要修复的 UI 相关缺陷，覆盖三类风险：

1. **契约 / 健壮性（P0）**
   - `PanelHost` 协议未声明 `get_global_usb_drive()`，但 `AutoUsbPanel._resolve_drive` 已依赖该方法——契约与实现脱节。
   - `BaseFlashPanel._poll_task_queue()` 在后台任务完成时，窗口可能已被销毁。`self.after(120, ...)` 调度会触发 `TclError`；用户回调（如 `on_done`）抛错会让轮询链彻底死掉、`_busy` 永久卡死。
2. **性能（P1）**
   - 搜索框每次按键直接销毁侧栏 + 主表重建，高频输入时闪烁 / 卡顿。
   - `SchemeWorkbenchModel` 单次 UI 刷新内多次调用 `query_assets()`，每次都走一次 SQLite；同一型号下 `_load_model_root_paths/build_sidebar_tree/get_common_modules/get_scheme_modules/get_all_modules/load_all_models` 全部重查。
3. **质量（P2）**
   - `shared_actions.py` 残留 `padx=20` 硬编码，未走 `design_tokens`。
   - `workbench_panel._open_current_asset_dir` / `_start_scan` 把 `import os, subprocess` 与 `from tkinter import filedialog` 放在方法内，每次调用都付一次 import 成本。

## 处理方案

### P0-1 · `PanelHost.get_global_usb_drive` 协议补齐

- 在 `host_types.PanelHost` 协议里显式声明 `def get_global_usb_drive(self) -> str: ...`。
- 新增 `test_panel_host_protocol.py`：4 个测试覆盖 `_is_runtime_protocol` 标志、方法签名、契约完整性、最小实现满足 `isinstance()` 检查。
- 行为零变更：协议补全后，IDE/mypy 能识别依赖关系；`MockHost` 原本就实现了该方法，UI 测试无回归。

### P0-2 · `_poll_task_queue` 销毁保护

- 新增 `_safe_winfo_exists()`：包裹 `winfo_exists()`，自身抛错时返回 `False`（Tk 在已 GC 的 widget 上调用方法会抛 `RuntimeError`）。
- `_poll_task_queue()`：
  1. 入口检查 `_safe_winfo_exists()`，关闭后直接 `return`，不消费队列、不调度 `after`。
  2. 每次 `on_done` 调用套 `try/except`；用户回调抛错仅记日志，不打断轮询链。
  3. 每次 `on_done`/`_handle_task_failure` 后再次检查 widget 状态——回调本身可能触发销毁。
  4. `self.after(120, ...)` 调度前最后再检查一次，并 try/except 兜住「检查与调度之间 widget 被销毁」的窄竞态。
- 新增 `test_base_panel_poll.py`：5 个测试覆盖销毁时立即返回、不调度 after、中途销毁停 drain、回调抛错不破坏后续、正常路径不变。

### P1-1 · 搜索刷新 debounce

- 新增常量 `SEARCH_REFRESH_DEBOUNCE_MS = 180`。
- `_on_search_changed()`：取消上一个 `self._search_after_id`（错误吞掉以兼容 widget 销毁中），调度 180ms 后再调 `_refresh_sidebar_tree` + `_refresh_main_grid`。
- 延迟回调内先 `winfo_exists()` 复检，销毁则放弃。
- `self.after` 本身抛错时降级为立即刷新，保证用户至少看到结果。
- **`_refresh_sidebar_tree()` 自身未被改**——非搜索路径（型号切换、扫描完成等）调用它时仍立即执行，**不**被 debounce 误延迟。这是契约的核心。
- 新增 4 个测试到 `test_workbench_panel_helpers.py`：立即路径不被调度影响、连续输入只留最后一个 after、销毁场景不刷表。

### P1-2 · `SchemeWorkbenchModel` 资产缓存

- `bind()` 阶段一次性 `query_assets(path=self.db_path)` 加载到 `self._all_assets`。
- 新增 `_filter_assets(keyword=, category=, scheme_name=)`：缓存非空时在 Python 层过滤（与 `query_assets` 等价语义）；缓存空时退回 `query_assets`。
- 改写 `load_all_models / build_sidebar_tree / get_common_modules / get_scheme_modules / get_all_modules / _load_model_root_paths` 全部走 `_filter_assets` 或直接读 `_all_assets`。
- 关键字过滤保留原有跨字段 OR 语义（`label/directory_name/firmware_label/firmware_type/version/model/series/path` 任一命中即保留）。
- 缓存随 `bind()` 重新加载；不存在的「重扫」入口调用 `bind()` 即可失效。
- 新增 5 个测试到 `test_scheme_workbench_model.py`：bind 后 hot path 不再调 `query_assets`、关键字过滤语义不变、平台回源仍生效、未 bind 的 model 走退化路径、`bind()` 重新加载使新增资产可见。

### P2-1 · `shared_actions.py` 间距 token 化

- `padx=20` → `padx=SPACE_LG`（=16）。20 不在 token 表里，最接近且符合"通用收紧"目标是 `SPACE_LG`。
- 新增 `test_shared_actions_uses_design_tokens_not_magic_numbers`：静态扫描 `shared_actions` 源文件，断言 `padx=20` 不再出现。
- 视觉影响：操作按钮列与左右屏边距由 20px 收到 16px，与工作台其他区域（`SIDEBAR`/`MAIN` 的内边距）一致。

### P2-2 · `workbench_panel.py` 方法内 import 整理

- 顶部新增 `import os`、`import subprocess`、`from tkinter import filedialog`。
- 移除 `_open_current_asset_dir` 内的 `import os, subprocess`。
- 移除 `_start_scan` 内的 `from tkinter import filedialog`。
- 调用逻辑零变更；只是把 import 成本从每次方法调用降到模块加载时一次。
- 新增 `test_workbench_panel_has_no_in_method_imports_for_known_offenders`：静态扫描确认类体（首个 `class` 定义之后）不再出现这两个导入语句。

## 验证记录

- 自动化门禁：
  - `python -m py_compile src/fwasset/ui/base_panel.py src/fwasset/ui/workbench_panel.py src/fwasset/ui/operation_panels/host_types.py src/fwasset/ui/operation_panels/shared_actions.py src/fwasset/ui/view_models/scheme_workbench_model.py`：通过。
  - `python -m pytest -m "not ui" -q --no-cov`：**192 passed, 34 deselected**（34 个 UI 标记的测试需在有 display 的环境人验，本机跳过）。
  - 新增测试覆盖：`test_panel_host_protocol.py`（4）、`test_base_panel_poll.py`（5）、`test_workbench_panel_helpers.py` 新增（4 + 2 静态契约）、`test_scheme_workbench_model.py` 新增（9 = 5 缓存 + 4 回归 bugfix）。
- 人验回归期发现 2 个真 bug，已在本次 commit 一并修复（见 `docs/CHANGELOG.md` Unreleased 段对应条目）：
  1. **空格分词搜索被压扁**：用户输 `主板 防夹` 期待 AND 命中，缓存层用 `kw in hay` 整段子串匹配退化为「单 token 单 substring」。修复：复刻 `query_assets` 的 `keyword.split()` + 10 字段 OR + token 间 AND。
  2. **通用模块全部标为定制专属**：`get_scheme_module_tree` 用 `c.is_fallback` 推断 `source_kind` 漏了「`is_fallback=False` 不等于 `custom`」的语义。修复：给 `ModuleCardData` 加 `source_kind` 字段，3 个 caller 显式写入。
- 人工验收待办（按 AGENTS.md 流程）：UI 改动的稳定性与性能需在真实 GUI 跑过：
  - 关闭主窗口时若后台烧录任务在跑，不抛 `TclError`（P0-2 回归）。
  - 搜索框快速输入不再每键重建侧栏/主表（P1-1）。
  - 同一 UI 刷新下 SQLite 查询次数肉眼可感知下降（P1-2，可用 DEBUG 日志核对）。
  - 切型号/点扫描完成按钮时**不**有 180ms 延迟（P1-1 反向契约）。
  - 操作按钮列与左右屏边距变紧但无错位（P2-1）。
  - 双击变体行开目录、点「扫描目录」选目录，行为不变（P2-2）。
  - 搜索 `主板 防夹` 应只命中防夹功能目录（BUG-2）。
  - 点通用模块区的主板行，展开后每条变体的「程序归属」应显示 `通用默认`（BUG-1）。

## 状态

- [x] 全部 6 项按 TDD 完成实现 + 自动化测试
- [x] 人验反馈的 2 个真 bug（空格分词、通用模块归属）已一并修复并补测试
- [x] 等待用户人工回归后拆分 commit
- [x] 按 `docs/COMMIT_TEMPLATE.md` 出 Conventional Commit：
  - `fix(ui): harden workbench task polling and host contract`（P0-1 + P0-2）
  - `perf(ui): debounce workbench search refresh`（P1-1）
  - `perf(ui): cache scheme workbench assets`（P1-2，**含 BUG-1 source_kind 字段 + BUG-2 空格分词复刻**）
  - `refactor(ui): clean minor review findings`（P2-1 + P2-2）

## 关联 Commit

- （占位，待人工验证后填写）见上 4 个 commit hash。
- 对应规划：`specs/archive/TASK-20260706-ui-review.md` 全部勾选。
