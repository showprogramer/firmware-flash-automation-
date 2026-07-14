# 代码审查：PySide6 迁移 Phase 3 + 核心域审计

- 日期：2026-07-09
- 类型：UI 框架迁移（双轨收尾）+ 核心域稳定性审计
- 模块：
  - `src/fwasset/ui_qt/workbench_window.py`（Phase 3 操作面板宿主 / PanelHost 实现）
  - `src/fwasset/ui_qt/operation_panels/*`（registry / host_types / base / 四面板）
  - `src/fwasset/core/asset_index.py`、`core/services/scan_service.py`、`core/file_scan.py`、`core/scheme_config.py`
- 来源：`specs/active/TASK-20260708-pyside6-migration.md` Phase 3 段 + `AGENTS.md` 服务/契约约束
- 触发条件：`ui_qt/operation_panels/registry.py` 注册表与 `host_types.py` PanelHost 协议变更（AGENTS.md「注册表/UI 入口变更」）

## 0. 进度与整体评价

**迁移进度**：Phase 0~3 全部完成（commit `72f8a70` 为最新）。`ui/`(CTk) 已冻结、仅保留兼容，`ui_qt/`(PySide6) 成为事实上的新壳。Phase 4（对齐/切换默认入口）待执行。

**自动化门禁（本机重跑）**：
```
uv run python -m pytest -q -m "not ui"  →  219 passed, 49 deselected, coverage 82.98% (≥80% 达标)
```
Qt smoke 与 pytest-qt 契约测试已就位（`test_qt_smoke.py`、`test_operation_panels.py` 等），不再出现上一轮「Qt 零测试」的缺口。

**优点**：
- 跨线程日志全部经 `log_message` Signal 回投 UI 线程（`workbench_window.py:209-215`），无 worker 直写控件；
- `PanelHost` 协议已正确去掉 `usb_drive: tk.StringVar` / `_build_usb_selector_row`（CTk 隐性耦合清零），`WorkbenchInterface` 实现完整；
- 注册表经包 `__init__` 自动装载，`get_panel` 对未知 `flash_mode` 返回 `None` 并被优雅处理；
- 核心服务层（`flash/usb_repair/music/usb` 等）均满足 `ServiceResult` 契约、中文消息、`log_fn=print` 默认、错误码不裸抛。

**仍未关闭的上一轮遗留**：`REVIEW-20260708-pyside6-p1-p2.md` 第 4 节「人验回归 11 项」状态仍为 **待用户执行**（含一键烧录/真实 U 盘流程、暗色主题观感）。

---

## 1. 发现（按严重度）

### P1 — 高（潜在数据丢失 / 契约破坏）

#### 1.1 `save_assets()` 无条件 `DELETE FROM assets`，且 `assets` 表无 `root_dir` 列
- 文件：`src/fwasset/core/asset_index.py`
- 问题：`assets` 全表只有一份全局索引，但 `scan_meta` 是按 `root_dir` 多行设计的（暗示多根支持）。若用户先后扫描两个不同根目录，第二次会替换整库。
- **处置（2026-07-09，选 B）**：产品定为单工作区；`save_assets` 全表替换 assets + 清空后只写一行 `scan_meta`；换根 = 切换工作区（intentional）。见 `MIGRATION-20260709-single-workspace-index.md` 与 `REVIEW-20260709-branch-pyside6.md` Issue 1。
- 状态：**fixed**

### P2 — 中（运行时错误 / 契约 / 并发）

#### 1.2 `build_cached_scan_result()` 仅捕获 `AssetIndexError`，DB 锁等异常会裸抛
- 文件：`src/fwasset/core/services/scan_service.py`
- **处置（2026-07-09）**：`except Exception` → `index_unavailable`。状态：**fixed**

#### 1.3 `file_scan.py` 读取 `平台配置.toml` 却从未使用（`platform` 字段对通用资产恒为空）
- 文件：`src/fwasset/core/file_scan.py:177`（`platform_defaults = load_platform_config(root_path)`），全文件仅此 1 处引用（grep 确认）。
- 问题：每次扫描热循环都读一次 `平台配置.toml` 但结果被丢弃。结合 CLAUDE.md「平台默认值仅由 `平台配置.toml` 驱动」，`FirmwareAsset.platform` 对通用资产始终为空字符串——若 UI 期望从 TOML 解析平台，则数据缺失。这是**死代码 + 潜在功能缺口**。
- 建议：要么删除该调用（若平台只用于双核目录段标记，见 `_DUAL_CORE_DIR` 分支），要么在 `_infer_asset_context` 中对 common 资产真正用 `platform_defaults` 解析 `platform`。先确认 `platform` 语义再决定。

#### 1.4 `scheme_for_path()` 前缀匹配未按路径深度排序，嵌套/乱序方案会绑定错方案
- 文件：`src/fwasset/core/scheme_config.py:102-107`
- 问题：按 `schemes` 列表顺序返回**第一个** `asset_path.relative_to(scheme.path)` 成功的方案。若方案目录存在嵌套（如 `定制/方案A` 与 `定制/方案A/变体`），或 `discover_schemes` 返回顺序非「最外先」，资产会绑到错误的方案。`discover_schemes` 仅收集 `model_root/定制` 与 `model_root/*/定制` 两层（`:42-58`），更深层级（`model_root/A/B/定制`）会漏掉。
- 建议：候选方案按 `len(str(path))` 降序（最深优先）再做前缀判定；`discover_schemes` 用 `rglob("方案配置.toml")` 或向下多递归一层。

#### 1.5 `_start_scan` 不检查 `_busy`：扫描可与操作任务并发、中途重建 UI
- 文件：`src/fwasset/ui_qt/workbench_window.py`、`ui/workbench_panel.py`
- **处置（2026-07-09）**：双向互锁（忙时不扫 / 扫描中不跑任务）。状态：**fixed**

#### 1.6 `_run_task` 把 `on_done` 可调用对象经跨线程 Signal 透传
- 文件：`src/fwasset/ui_qt/workbench_window.py:79`（`_task_done = Signal(str, object, object)`）、`:227`（`self._task_done.emit(name, result, on_done)`）
- 问题：worker 线程把一个 Python 可调用（`on_done` lambda）作为 `object` 经 queued Signal 传到 UI 线程。PySide6 虽通常能 marshal 任意 `object`，但**跨线程传递 callable 是脆弱反模式**（版本/绑定依赖），与「任务结果用 Signal 回投」的初衷相悖；`on_done` 本就该在 worker 内同步执行。
- 建议：在 `worker()` 内直接调用 `on_done(result)`（worker 已能 `log_fn` 回投 UI 线程），Signal 仅传 `(name, result)`；删除 `on_done` 的透传。`auto_usb_panel.py:94-99` 的目录刷机结果上报随之改为 worker 内 `log_fn(result.get("message"))`。

### P3 — 低（性能 / 健壮性 / 卫生）

#### 1.7 `build_scan_result` 重复遍历目录树
- 文件：`src/fwasset/core/services/scan_service.py:27`（`folders = find_handcontrol_folders(root)`），`find_handcontrol_folders`（`file_scan.py:336-361`）内部再次调用 `scan_firmware_assets(root)`。
- 问题：每次扫描把整棵树走两遍（一次算 assets，一次算 handcontrol folders），I/O 翻倍。已有 `assets` 可直接派生 `HandcontrolFolder`。
- 建议：用已计算的 `assets` 推导 `folders`，去掉二次 `os.walk`。

#### 1.8 `connect_asset_index()` 无 `timeout` / `check_same_thread`，只读辅助可能裸抛
- 文件：`src/fwasset/core/asset_index.py:30-38`
- 问题：默认连接 5s busy timeout + 严格线程亲和。长事务 `save_assets`（DELETE+executemany+prune）会阻塞并发读者；`query_assets/count_assets/load_assets` 无异常守卫，锁表时把 `OperationalError` 直接抛给调用方。
- 建议：连接加 `timeout=30`，必要时 `check_same_thread=False` 配纪律性使用；只读辅助加宽捕获或文档声明单写者预期。

#### 1.9 `handcontrol_ui` 特殊规则在任何 `dir_keywords`/`file_extensions` 之前短路
- 文件：`src/fwasset/core/file_scan.py:69-73`
- 问题：只要目录同时含 `.rom` 与 `.pkg` 就被判为 `handcontrol_ui`，无视 catalog 顺序与关键词。一个并非手控、但恰好同时含 `.rom+.pkg` 且排在 `handcontrol_ui` 之后的目录会被误判。
- 建议：在文档/代码注释显著标注此顺序敏感规则；或在 `handcontrol_ui` 也要求 `dir_keywords` 命中（若关键词存在）再判定。

#### 1.10 增量扫描 `continue` 未剪枝子树
- 文件：`src/fwasset/core/file_scan.py:194-200`
- 问题：`dir_mtime < last_scan_at` 时 `continue`，但 `os.walk` 仍会单独 yield 该目录的子项，父目录被跳过而子项被重新扫。
- 建议：跳过时 `dirs[:] = []` 剪枝（若 `os.walk` 用法允许），或显式 `continue` 前清空子目录列表。

#### 1.11 `firmware_type/flash_mode/usb_flow` 用 `# type: ignore[typeddict-item]` 绕过校验
- 文件：`src/fwasset/core/asset_index.py:389,391,392`
- 问题：读库时强转 `str`，旧/未知固件类型静默放行，绕过 `FirmwareType`/`FlashMode`/`UsbFlow` Literal 契约。运行时安全，但失去类型护栏。
- 建议：读取时归一化/校验（或内部用宽松别名接受 `str`）。低优。

#### 1.12 其它（来自子代理审计，未逐一人工复核，供参考）
- `ui_qt/workbench_window.py:327-329` `_load_cached_assets` 在 UI 线程同步执行 `build_cached_scan_result`，大索引会短暂卡顿（与 CTk 行为一致，非回退，可后置到 worker）。
- `ui_qt/workbench_window.py:386-420` 型号 `EditableComboBox` 每次型号变更都销毁重建，丢弃输入中文本（低优）。
- `ui_qt/data_grid.py` `populate_tree` 的 `tree.clear()` 触发 `itemSelectionChanged` 重入（用 `blockSignals` 包裹更稳）。
- `ui_qt/operation_panels/shared_actions.py:27-28,51` `include_tool_combo=True` 分支在 Qt 壳从未被触发（死分支，CTk 同款）。
- **行为差异（需确认）**：Qt 型号选择器**始终**显示可搜索 `EditableComboBox`（即便 ≤4 型号），而 plan 写「4+溢出下拉」、CTk 仅溢出时显示。属有意偏离，请确认是否符合预期。
- **验收项核对**：「搜索空格分词」在 Qt 与 CTk 均把原始 `search_kw` 原样传给 model 层，需确认 `SchemeWorkbenchModel` 确实按空格分词（否则该 1:1 验收项在两壳均未满足）。

---

## 2. 优先修复顺序

| 序 | 编号 | 动作 | 性质 |
|---|---|---|---|
| 1 | 1.1 | 厘清 `assets` 单根 vs `scan_meta` 多根，消除休眠数据丢失 | 设计 + 测试 |
| 2 | 1.2 | `build_cached_scan_result` 加宽异常捕获 → `index_unavailable` | 契约修复 |
| 3 | 1.5 | 扫描入口加 `_busy` 互锁，禁止与操作任务并发 | 并发修复 |
| 4 | 1.6 | 去掉 `on_done` 跨线程透传，改 worker 内执行 | 反模式修复 |
| 5 | 1.3 | 澄清 `platform` 语义，删除死代码或真正解析 | 死代码/功能 |
| 6 | 1.4 | `scheme_for_path` 最长前缀匹配 + 深层发现 | 正确性 |
| 7 | 1.7~1.11 | 性能/健壮性 polish | 低优 |

---

## 3. 验证记录

- 自动化：`uv run python -m pytest -q -m "not ui"` → **219 passed, 49 deselected, 82.98%**(≥80% 达标)。
- 人工：1.1 / 1.5 / 1.6 为源码直接核对确认；1.2 / 1.3 / 1.4 为源码 + grep 确认。
- 待用户人验（沿用上轮清单 + 本轮并发项）：一键烧录/真实 U 盘流程、暗色主题、扫描与操作任务并发互锁、设默认全流程。

## 4. 状态

- [x] 阻断/P1：1.1 已修（单工作区 B）
- [x] 阻断/P1：1.2 已修（缓存宽捕获）
- [x] P2：1.5 已修（扫描/任务互锁）；1.3、1.4、1.6 待修
- [ ] P3：1.7~1.11 待修
- [x] 自动化门禁通过（219 passed, 82.98%）
- [ ] 人验回归（含并发互锁）待执行
- [ ] Commit：待用户拍板（修复轮完成后按 `docs/COMMIT_TEMPLATE.md` 提交并更新 `docs/CHANGELOG.md`）

## 5. 关联 Commit / 计划

- `72f8a70 feat(qt): 型号可搜索下拉改常驻 + 切换防抖`（本次审查对象之一）
- `b091730 feat(qt): 操作面板与后台任务迁移（Phase 3）`
- `1e0e4ef fix(qt): 落实 P1-P2 代码审查整改（REVIEW-20260708-pyside6-p1-p2）`
- 计划：`specs/active/TASK-20260708-pyside6-migration.md` Phase 3 完成、Phase 4 启动前补本审查项。
