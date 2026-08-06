# TASK-20260806-r1-r10-write-gate：配置根权威 + 写入口统一门闩

## 状态

| 项 | 状态 |
| --- | --- |
| 类型 | UI 状态判定 + 写入口统一禁用（安全边界） |
| 当前状态 | ✅ 人工验证通过，记录已更新 |
| 前置 | REVIEW-20260728 R1（P1·阻断）+ R10（P2） |
| 父任务 | CRUD 前置（REVIEW-20260728-pre-crud-readiness） |
| 分支 | `feature/pyside6-migration` |
| 完成 commit | （待填） |

---

## 目标

实现 REVIEW-20260728 前置条件清单 **#1**（R1 + R10）：确立「配置文件 `root_dir` 是写操作的唯一权威来源」，配置为空时只读浏览缓存并禁用全部写入口；新增统一写门闩判定，接入现有 3 个写入口（设为默认、共享登记、共享取消登记），并为未来 CRUD 写入口提供同一门闩。

## 关键决策

- **三层权威来源**（按 REVIEW R1）：
  - 配置文件 `root_dir`：写操作唯一权威。不得用 `scan_meta` / `active_workspace_root()` 替代（它只代表最近一次扫描根）。
  - `scan_meta`（`active_workspace_root()`）：仅用于启动时恢复上次浏览状态。
  - 配置为空时：允许只读浏览缓存内容，禁止所有写操作，只允许浏览 + 前往设置。
- **写入口三检查**（缺一不可，R10 门闩）：

  ```python
  configured_root = normalize(DEFAULT_ROOT)   # Path.resolve() + normcase
  scanned_root    = normalize(active_workspace_root())

  if not configured_root:
      # 禁止写入，提示「请先在设置中配置程序文件夹」
  if scanned_root != configured_root:
      # 禁止写入，提示「配置已变更，请先重新读取程序文件夹」
  if not is_under_workspace(target_path, configured_root):
      # 禁止写入，路径越界
  ```

- **门闩还须覆盖**（R10）：扫描进行中（`scan_state_model.cancel_event is not None`）、烧录任务进行中（`_busy`）、当前选中资产 `path` 不在配置根之下（防陈旧选中、异步回调、共享来源外部路径）。
- **门闩判定做成纯函数**放 `ui_common`（可单测），第三条复用 R5 的 `assert_within_workspace`；`normalize` 统一 `Path.resolve()` + `os.path.normcase()`。
- 写入口拦截后必须给用户可见提示（`QMessageBox` 或日志），不能静默失败。

## 文件变更

### Task 1：门闩纯函数  `complexity: low`

**复杂度理由：** 单文件纯函数 + 用例，无 UI 控件与 schema 变化。

**Files:** `src/fwasset/ui_common/workbench_helpers.py`（或新建独立模块）、`src/fwasset/tests/test_workbench_helpers.py`

- 新增类似 `write_gate_check(configured_root, scanned_root, target_path) -> ServiceResult` 风格的结果（`ok` + 中文 `message`），三条件按序判定：
  - 空配置根 → 拒绝「请先在设置中配置程序文件夹」；
  - `scanned_root != configured_root` → 拒绝「配置已变更，请先重新读取程序文件夹」；
  - 目标路径越界 → 复用/委托 `assert_within_workspace` 拒绝。
- 路径归一统一 `Path.resolve()` + `os.path.normcase()`（含 Windows 分隔符语义，参照 `path_guard` 的回归教训：先 normcase 再统一斜杠）。
- 测试用例：空根拒绝；配置/扫描根不一致拒绝；一致但目标越界拒绝（含 `..`）；一致且在区内放行；Windows 大小写/分隔符差异（`_fake_win_normcase` 风格回归用例）。

### Task 2：UI 接入门闩  `complexity: high`

**复杂度理由：** 跨 `workbench_window.py` 多个触点（3 个写入口 + 右键菜单生成 + 缓存恢复路径），涉及 Qt 交互与提示文案，需 UI 冒烟与人工回归。

**Files:** `src/fwasset/ui_qt/workbench_window.py`

- 新增统一入口 `_write_allowed(target_path) -> bool`：先跑 Task 1 的纯函数，再叠加「扫描进行中 / 烧录进行中」两态；不通过时弹提示并返回 `False`。
- 接入现有写入口，执行前先过门闩：
  - `_set_default_variant`（`:847`）；
  - `_register_shared_source`（`:869`，含 `_do_register_shared` `:1017` 的目标路径检查，登记的目标根也须在配置根之下）；
  - `_unregister_shared`（`:1057`）。
- 右键菜单生成（`_on_grid_right_click` `:781`）：门闩不通过时**不显示**写操作项（设为默认 / 共享登记 / 共享取消登记），只保留打开目录、复制路径等只读项；菜单生成与执行时双重判断。
- 缓存恢复路径（`_handle_scan_result` `:462-471`）：保持「配置为空时从 `scan_meta` 恢复根」的只读浏览行为不变，但 `set_configuration_required` / `configuration_notice` 状态与门闩一致。
- `scanned_root` 来源：优先用 `active_workspace_root()`；UI 侧可用 `workbench_model.root_dir` 或最近一次 payload 的 `scan_meta` 等价推导，需在实现时确认与 `active_workspace_root()` 一致。

## 非目标

- 不做 R3（CRUD 定点写 API + 子树对账）——后续任务。
- 不做 R8（TOML 引用反查）、R6d（命名规范）。
- 不改 schema、不改扫描器。
- 不改变「配置为空时只读浏览缓存」的现有行为（这是本任务要保留的语义，不是要移除的）。

## 验收标准

- 配置为空但存在旧缓存：只读浏览可用，三个写入口全部被拦截并给出中文提示，不落盘。
- 配置变更未重读（`scanned_root != configured_root`）：写入口被拦截。
- 扫描 / 烧录进行中：写入口被拦截（烧录态若现有按钮已禁用，确认一致）。
- 门闩纯函数全部单测通过；既有测试全绿（`-m "not ui"`）；`FWASSET_QT_*` 钩子冒烟可用。
- REVIEW-20260728 前置条件清单 #1 更新为已完成。
- CHANGELOG Unreleased 记录本次改动。

---

## 验证记录

### 自动化验证（已完成）

| 平台 | 环境 | 命令 | 结果 |
| --- | --- | --- | --- |
| WSL/Linux | `.venv-wsl` | `.venv-wsl/bin/python -m pytest src/fwasset/tests/test_path_guard.py src/fwasset/tests/test_workbench_helpers.py -q --no-cov` | 通过（28 passed） |
| WSL/Linux | `.venv-wsl` | `.venv-wsl/bin/python -m pytest -m "not ui" -q` | 通过（391 passed, 3 skipped；覆盖率 88.72%） |
| WSL/Linux | `.venv-wsl` | `.venv-wsl/bin/ruff check src scripts` | 通过 |
| WSL/Linux | `.venv-wsl` | `.venv-wsl/bin/mypy` | 通过（32 文件） |
| Windows | `.venv` | `.\.venv\Scripts\python.exe -m pytest -q`（经 WSL `powershell.exe` 调用） | 通过（425 passed, 1 warning；覆盖率 94.78%） |

- 门闩纯函数 12 个用例：空根/None 根拒绝、配置-扫描根不一致拒绝、越界/`..` 逃逸或区内折返/空目标拒绝、区内与根相等放行、Windows 归一（`_win_normcase` 模拟）。路径归一及归属判定均委托 `core.path_guard`，不再维护第二套实现。
- smoke 测试修复：`test_context_menu_*` 与 `test_shared_source_picker_*` 注入 fake gate（真实门闩由 test_workbench_helpers 覆盖），新增 `test_context_menu_hides_write_actions_when_gate_blocks`。此前在 Windows 全量跑时菜单门闩导致 2 例失败 + 1 例模态框卡死，已消除。
- 实现过程中发现并修复：`_on_grid_right_click` 登记分支漏门闩（`else:` → `elif write_ok:`）；路径归一与归属判定现统一委托 `core.path_guard`，避免 Windows 模拟下的二次归一前缀问题及 POSIX 对 `\` 分隔符的差异。
- 已知平台差异：无（WSL 与 Windows 全量均通过；UI 测试在 WSL 按 `-m "not ui"` 排除、在 Windows 全量验证）。
- 提交：（待填）

### 人工验证（已完成）

- 平台：Windows 实机（开发模式 `uv run fwasset`）
- 方式：`scripts/verify_write_gate.py` 全场景引导（`uv run python scripts\verify_write_gate.py`，全部场景验证通过）
- 结论：
  1. **Phase 1 正常基线**：资产树/★默认 徽章正确；「量产_默认」右键无「设为默认」、仅「登记共享来源…」；「备用_V2.1」右键含「设为默认」且执行成功（徽章转移）；
  2. **Phase 2 配置为空 + 旧缓存（核心）**：日志「使用上次读取的程序文件夹」、只读浏览缓存、右键菜单仅「打开所在目录/复制目录路径」、写入口全部被拦截；
  3. **Phase 3 恢复与扫描中拦截**：重读后写入口恢复；切换到 `程序根B` 重新读取期间写操作项不可用，完成后恢复。
- 场景脚本缺陷（非应用代码）：平台配置模板裸键含中文（TOML 非法）导致「平台配置读取失败」——已改为引号键并复验（PLATFORM ok / 5 资产 / SETDEFAULT True）。

## 文档与收口

- Review：REVIEW-20260728 前置清单 #1 已更新为 ✅ 已完成（含验证记录回填）。
- CHANGELOG：Unreleased → Fixed 已新增条目（已完成）。
- 迁移说明：不适用（无路径/配置/运行时迁移）。

---

## Task DoD

- [x] Task 1：门闩纯函数 `write_gate_check` 已委托 `core.path_guard` 的规范化与路径守卫，消除重复实现
- [x] Task 2：三个写入口 + 右键菜单接入门闩；登记目标根二次检查；扫描/烧录进行中两态叠加
- [x] 自动化验证已记录（WSL 全量 + Windows 全量 425 passed）
- [x] 人工验证（Windows 实机：`scripts/verify_write_gate.py` 全场景通过）已记录
- [x] Review 已更新（REVIEW-20260728 #1 关闭）
- [x] CHANGELOG 已同步
