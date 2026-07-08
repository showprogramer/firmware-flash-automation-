# TASK-20260708: UI 框架迁移 CustomTkinter → PySide6

## 背景与目标

CTk + ttk.Treeview 的交互天花板（右键菜单靠手拼、无行内编辑、无原生拖拽、单元格无徽章控件）挡住了后续 CRUD 的交互需求，观感也达不到预期。经选型讨论（见 2026-07-08 会话）确定迁移到 **PySide6**：模型/视图原生虚拟化、右键/拖拽/行内编辑委托齐全、原生字体渲染与高 DPI、PyInstaller 打包成熟。

**目标**：UI 壳完整迁移，功能与现状 1:1 对齐（工作台、设默认、多型号、四类操作面板、扫描、日志），迁移期间不夹带新功能。CRUD（增删改、替换程序文件）在新壳落地后再做——避免在旧框架上建一遍再重写。

## 不变的部分（迁移的资产）

- `core/**` 全部：扫描、索引、服务层、平台配置。零改动。
- `ui/view_models/scheme_workbench_model.py`：不依赖 tkinter，原样带走（`SchemeWorkbenchModel` 是 UI 的大脑）。
- `ui/view_models/scan_state_model.py`：纯 threading，原样带走。
- 领域约束不变：`定制专属/通用默认` 文案、禁"回源"、`STANDARD_MODULE_ORDER`、平台按型号隔离。
- 非 UI 测试全部不变（覆盖率口径 `pyproject.toml` 已 omit `ui/*`）。

## 需要重写的文件清单

| 现文件 | 去向 |
|---|---|
| `ui/shell.py` (`UnifiedFlashPlatform`, CTk root) | `QMainWindow` + QFluentWidgets `FluentWindow`（视主题决策） |
| `ui/base_panel.py` (`BaseFlashPanel`：`_run_task` queue+after 轮询、USB 扫描) | `QWidget` 基类；后台任务改 **worker QThread + Signal**（跨线程自动 queued，去掉 120ms 轮询） |
| `ui/workbench_panel.py` | 主工作台：侧边树(QTreeWidget)、型号 chips、搜索(QLineEdit + QTimer 防抖)、U盘选择、右键菜单(QMenu) |
| `ui/panels/data_grid_panel.py` (ttk.Treeview) | `QTreeView` + `QStandardItemModel`（数据量小，不需要自定义 model）；★默认 徽章可做成带样式的 item；右键/双击/斑马纹原生 |
| `ui/panels/log_panel.py` | `QPlainTextEdit`（只读） |
| `ui/operation_panels/*`（registry、host_types、auto_usb、tool_launch、manual_doc、disabled） | 注册表模式和 `PanelHost` 协议**原样保留**（AGENTS.md 契约），仅把每个面板的控件层换成 Qt |
| `ui/design_tokens.py`（light/dark 元组） | QSS 全局样式表 + 主题库变量；沿用"禁止硬编码色值/字号"规则 |
| `app.py` 入口 | `QApplication` 启动 |

## 主题决策（迁移第 0 步定案）

| 方案 | 观感 | 许可 | 备注 |
|---|---|---|---|
| QFluentWidgets | 最好（Fluent，现成组件全） | **GPLv3**（商用需付费授权） | 内部工具可用，但需明确不对外分发 |
| PyQtDarkTheme / qt-material | 中等（配色+控件皮肤） | MIT / BSD | 零风险，观感弱于前者 |
| 纯 QSS 自绘 | 可控 | - | 工作量最大，不推荐 |

推荐：先用 **QFluentWidgets** 出 spike，若许可有顾虑（未来可能对外分发 exe）降级 PyQtDarkTheme。

## 分阶段计划

**Phase 0 — Spike（半天）** ✅ 已完成（2026-07-08，分支 feature/pyside6-migration）
- 依赖：`pyside6 6.11.1` + `pyside6-fluent-widgets 1.11.2`（optional extra `qt`，`uv sync --extra qt`）。
- `scripts/spike_pyside6.py`：FluentWindow + 导航 + TreeWidget，对接真实 `SchemeWorkbenchModel`（扫 `D:\按摩器程序`，70 资产），支持 `--screenshot / --quit-after` 自动化验证。
- **结论：通过，迁移放行。** 实测：
  - 源码启动 1.9~2.7s、打包 exe 启动 **1.5s**（含实时扫描 70 资产建临时索引）
  - onefile exe **52.1 MB**，在预估 30~50MB 区间边缘，可接受
  - 中文字体清晰、高 DPI 正常、整机层级/归属列/方案导航渲染正确
- **踩坑记录**（Phase 1+ 必读）：
  1. 装 pyside6 后 `pyinstaller.exe` shim 损坏（报 `Failed to canonicalize script path`）——一律用 `uv run python -m PyInstaller`。
  2. 冻结 exe 旁必须放 `firmware_catalog.toml`（否则扫描 0 资产、界面空白无报错）——与现有交付物结构一致，但值得在启动时加显式警告。
  3. FluentWindow 的 Mica 半透明 + `grab()` 截图在暗色主题下抓取不全——暗色观感需人工开窗验证，自动化截图仅用亮色。

**Phase 1 — 壳与骨架** ✅ 已完成（2026-07-08，与 Phase 2 同批交付）
- `ui_qt/`（`workbench_window.py` / `data_grid.py` / `log_panel.py`）并行目录，`ui/` 未动。
- `app.py` 加 `FWASSET_UI=qt` 环境开关，默认仍走 CTk；coverage omit 加 `ui_qt/*`。
- 设计令牌暂由 QFluentWidgets 主题承担，未引入自定义 QSS（后续按需加）。

**Phase 2 — 数据面** ✅ 已完成（2026-07-08）
- 侧边树（通用模块计数 + 定制方案分区）、型号 chips（4+溢出下拉）、搜索 180ms 防抖 → 对接 `SchemeWorkbenchModel`。
- DataGrid（QTreeWidget）：模块行/变体子行、★默认徽章、右键菜单（设为平台默认/打开目录/复制路径）、双击开目录。
- 扫描/取消（threading + Signal 跨线程回投）、缓存加载；**较 CTk 版的增强**：缓存加载时若未配置 DEFAULT_ROOT，从 scan_meta 恢复上次扫描根（CTk 版会绑到 "." 产生噪声假型号）。
- 自动化验证钩子：环境变量 `FWASSET_QT_SCREENSHOT` / `FWASSET_QT_QUIT_MS`。
- 已验证（真实数据截图 .runtime/qt_phase1b.png）：双型号 chips、侧边树 7 模块 + 6 方案、徽章、归属列。
- 待人工验证：右键设默认全流程、扫描取消、暗色主题观感。

**Phase 3 — 操作面与任务（1~2 天）**
- `PanelHost` 协议在 Qt 壳实现；四个操作面板迁移；`_run_task` → QThread+Signal；扫描取消（threading.Event 沿用）。
- U盘选择器、设默认确认框（QMessageBox）。

**Phase 4 — 对齐与切换（1 天）**
- 逐项过功能清单（下方验收）；`@pytest.mark.ui` 测试改 pytest-qt 重写关键契约（全局 USB 选择器存在、启动自动刷 U 盘、设默认菜单出现条件）。
- 默认入口切到 Qt；CTk 目录保留一个版本周期后删除；`fwasset.spec` 更新 PySide6 hooks，剔除 customtkinter。

## 验收清单（与现状 1:1）

- [ ] 扫描/取消/缓存加载；多型号根双型号识别；单型号根兼容
- [ ] 侧边树、全部/通用/方案三种视图、搜索空格分词、防抖
- [ ] 方案视图整机层级：单变体折叠、多变体展开、定制专属/通用默认、无"回源"字样
- [ ] 右键设默认（单/多平台）、★默认徽章、toml 写回、免重扫生效
- [ ] 四类操作面板 + 一键烧录 + 全局 U 盘选择器 + 日志
- [ ] PyInstaller exe 可运行；`.\scripts\test.ps1` 通过

## 风险

- QFluentWidgets GPLv3：内部使用无碍，对外分发前必须决策（换主题或购license）。
- exe 体积增加约 30~50MB（Qt 运行库）：可接受，spike 确认。
- 双轨期两套 UI 的维护窗口要短：Phase 1~4 期间冻结旧 UI 的功能性改动，只修阻断性 bug。
- `PanelHost` 协议里 tkinter 类型（如 `StringVar`）的隐性耦合：Phase 3 逐个清点，必要时协议侧加薄适配。

## 后续（迁移完成后，另立 TASK）

- CRUD：添加（上下文预填对话框）、删除（回收站 + 影响检查）、替换程序文件、重命名/版本（文件名解析预览）——设计已在 2026-07-08 会话敲定。
- 应用内变更 → 增量重扫（`asset_write_service`），QFileSystemWatcher 监听外部改动。
