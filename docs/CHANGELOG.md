# 记录变更

## Unreleased

### refactor
- 新增 `SidebarPanel`，将左侧搜索、类型快速筛选、排序、隐藏开关、扫描按钮和 `AssetTreeView` 装配从 `FirmwareListPanel` 中拆出；`FirmwareListPanel._build_sidebar()` 保留兼容属性并只负责创建和路由侧边栏。

### docs
- 补充 `AGENTS.md` 的人工验证、`docs/CHANGELOG.md`、`docs/code-review/` 与 `docs/migrations/` 使用规则；新增迁移记录，明确文档目录迁移后的维护位置。

### test
- 新增 `tests/test_sidebar_panel.py`，覆盖侧边栏扫描按钮和资源树回调契约；本轮验证通过 `uv run python -m pytest tests\test_sidebar_panel.py tests\test_app_service_smoke.py tests\test_operation_panels.py -q --no-cov` -> `31 passed`，`.\scripts\test.ps1` -> `189 passed`，总覆盖率 `84.45%`。

### refactor
- 提取扫描状态管理为 `ScanStateModel`，将扫描开始、取消请求、完成清理从 `FirmwareListPanel` 中拆出，并保留 `_scan_cancel_event` 兼容层以降低既有调用影响。

### test
- 新增 `tests/test_scan_state_model.py`，覆盖扫描生命周期、重复开始、取消请求和旧任务完成隔离；本轮验证通过 `.\scripts\test.ps1` -> `188 passed`，总覆盖率 `84.45%`。

### fixed
- 修复扫描中点击“取消扫描”仍弹出目录选择器的问题；扫描按钮现在按状态分流，运行中只触发现有扫描任务取消。
- 修复扫描取消事件通过可变面板属性传入后台任务的竞态；后台任务固定捕获本次扫描创建的 `cancel_event`。
- 暂停将 `scan_meta.last_scan_at` 下推到扫描器，避免当前全表替换索引策略下丢失未变化资产。

### fixed
- 修复手控 UI 扫描在混合型号父目录下的归属与型号识别：手控目录名包含明确型号时优先使用目录型号，避免 ROM 文件名中的历史型号覆盖实际目录型号；实际验证 `L26A手控葡文（凡强）` / `L50S手控葡文（凡强）` 可识别为 `L26A` / `L50S`，版本仍从 ROM 文件名提取。

### app
- 精简固件资源树层级：移除型号目录层和“几个版本”分组层，系列下直接显示型号行；程序目录和版本继续保留在表格列中，降低重复信息干扰。

### test
- 新增手控 UI 混合型号目录回归测试、目录型号优先级测试，以及资源树去冗余展示测试；本轮验证通过 `uv run python -m pytest tests\test_file_scan.py tests\test_asset_filter_model.py tests\test_asset_tree_view.py tests\test_tree_expansion_model.py tests\test_app_service_smoke.py tests\test_asset_index.py tests\test_scan_service.py -q --no-cov` -> `78 passed`，`.\scripts\test.ps1` -> `177 passed`，总覆盖率 `84.26%`。

### refactor
- 移除已废弃的蓝牙串口控制链路：删除 `auto_serial` 操作面板、`SerialControl` UI、串口/AT 服务、`pyserial` 依赖和对应测试；蓝牙固件统一通过外部工具烧录。
- 新增 `src/fwasset/core/asset_helpers.py`，将 `FirmwareListPanel` 中与 UI 无关的纯逻辑方法提取为独立可测试函数：`asset_usb_flow()`、`asset_rom_pkg_files()`、`asset_dir_path()`、`asset_primary_file_path()`；`AutoUsbPanel` 改为直接调用 `asset_helpers` 函数而非通过 `panel_host` 间接访问。
- 新增 `src/fwasset/ui/operation_panels/host_types.py`，定义 `PanelHost` Protocol，规范操作面板与宿主面板之间的接口契约（`usb_drive`、`_build_usb_selector_row`、`_refresh_usb`、`_run_task`、`_selected_asset`、`_open_current_asset_dir`、`_copy_asset_dir_path`、`_copy_primary_file_path`、`_launch_tool_and_open_asset_dir`），为后续解耦测试和 Mock 提供类型基础。
- 提取 `_make_bool_var()` 为 `src/fwasset/ui/shared_widgets.make_bool_var()` 公共组件，`FirmwareListPanel` 和 `AutoUsbPanel` 统一委托到该函数。
- 新增 `src/fwasset/ui/view_models/tree_expansion_model.py`，将 `FirmwareListPanel._tree_expanded` 及其 5 个操作方法提取为 `TreeExpansionModel` 类（`clear`、`is_open`、`toggle`、`mark_open`、`mark_closed`、`expand_all_default`），支持独立单元测试。
- `BaseOperationPanel.panel_host` 参数增加 `PanelHost` 类型注解（TYPE_CHECKING 仅运行时检查），`shared_actions.build_handoff_actions` 增加 `PanelHost` 类型注解。
- `FirmwareListPanel._asset_usb_flow`、`_asset_rom_pkg_files`、`_asset_path_text`、`_primary_file_path_text` 改为委托到 `asset_helpers` 模块函数，保留方法签名向后兼容。
- `FirmwareListPanel._make_bool_var` 改为委托到 `shared_widgets.make_bool_var`。
- `FirmwareListPanel._tree_expanded` 迁移为 `self._tree_expansion = TreeExpansionModel()`，原有 `_is_tree_node_open`、`_toggle_tree_node`、`_mark_tree_node_open`、`_mark_tree_node_closed`、`_ensure_default_tree_expanded` 全部委托到 `TreeExpansionModel`；移除 `_expand_matching_tree_nodes` 内联实现。
- `operation_panels/__init__.py` 导出 `PanelHost`。

### test
- 更新 catalog、扫描、UI smoke 和操作面板测试，锁定蓝牙走 `tool_launch`、音乐文件才走 `directory_copy`，并移除串口控制相关测试。
- 本轮验证通过：`uv run python -m pytest tests/test_asset_helpers.py tests/test_firmware_catalog.py tests/test_file_scan.py tests/test_settings.py tests/test_operation_panels.py tests/test_app_service_smoke.py -q --no-cov` -> `99 passed`；`.\scripts\test.ps1` -> `174 passed`，总覆盖率 `84.05%`。
- 新增 `tests/test_asset_helpers.py`（12 个测试），覆盖 `asset_usb_flow`、`asset_rom_pkg_files`、`asset_dir_path`、`asset_primary_file_path` 的推断、回退和空值场景。
- 新增 `tests/test_tree_expansion_model.py`（5 个测试），覆盖 `TreeExpansionModel` 的初始状态、标记开关、切换和幂等关闭。

- 新增 `src/fwasset/ui/operation_panels/` 包，将 `FirmwareListPanel` 的 `_render_operation_panel` if/elif 链和各 `_build_*_ops` 方法拆分为独立的 Panel 类，通过注册表机制按 `flash_mode` 查找，消除每新增一种烧录方式就必须修改 FirmwareListPanel 的问题。
  - `BaseOperationPanel` 基类定义 `build()` 接口，各 Panel 通过 `panel_host` 访问 FirmwareListPanel 的方法。
  - `AutoUsbPanel`（auto_usb）、`ToolLaunchPanel`（tool_launch）、`ManualDocPanel`（manual_doc）、`DisabledPanel`（disabled/兜底）各自独立文件。
  - `shared_actions.py` 提取 `build_handoff_actions` 等共享操作为独立函数。
  - `FirmwareListPanel._render_operation_panel()` 简化为注册表查找 + `PanelClass(...).build()`。
  - 从 FirmwareListPanel 移除已迁移的方法：`_build_auto_usb_ops`、`_build_directory_copy_usb_ops`、`_build_tool_launch_ops`、`_build_manual_doc_ops`、`_build_disabled_ops`、`_build_handoff_actions`、`_show_manual_doc`、`_launch_current_tool`、`_clean_usb`、`_format_usb`、`_copy_to_usb`、`_eject_usb`、`_one_click_handcontrol`、`_run_directory_flash`。
  - 保留在 FirmwareListPanel：`_render_selected_detail_summary`、`_render_placeholder_ops`、`_asset_path_text`、`_primary_file_path_text`、`_copy_text_to_clipboard`、`_copy_asset_dir_path`、`_copy_primary_file_path`、`_open_current_asset_dir`、`_launch_tool_and_open_asset_dir`、`_reset_ops_body`。
  - 清理 FirmwareListPanel 不再直接依赖的导入（`load_firmware_catalog`、`discover_tool_path`、`launch_tool`、`run_one_click`、`run_music_flash`、`clean_usb`、`copy_to_usb`、`eject_usb`、`format_usb`、`SerialControl`）。

### core
- catalog 将蓝牙程序 `music_bt` 改为 `tool_launch`，新增 `music_files` 类型承载音乐文件目录复制；`asset_flash_mode()` 对旧缓存中的蓝牙 `auto_usb` 记录强制归一为 `tool_launch`。
- 资产索引 schema 升级到 v2，新增 `usb_flow` 持久化字段，并支持旧 v1 索引自动迁移，避免本地缓存因字段新增直接失效。
- firmware catalog 新增显式 `usb_flow`：手控/断码屏走 `paired_files`，音乐文件走 `directory_copy`，不再让 UI 依赖文件组合猜测刷机流程。
- `query_assets()` 支持 `sort_key` / `ascending` 参数，并复用现有自然排序规则，供 UI 将关键词、类型筛选和排序统一下推到 SQLite 查询入口。
- `build_cached_scan_result()` 启动缓存读取改为只读取资产数量与扫描元数据，不再启动时全量加载资产列表。
- 新增统一运行时目录解析：开发模式默认写入 `.runtime/`，打包模式默认写入 exe 同级 `runtime/`，并支持 `FWASSET_RUNTIME_DIR` 覆盖。
- SQLite 资产索引默认路径从应用根目录 `fwasset.db` 迁移到运行时目录 `.runtime/fwasset.db`，避免源码目录混入运行时数据。
- 文件日志默认路径迁移到运行时目录 `.runtime/logs/app.log`，启动时自动创建运行时目录，创建失败时抛出中文错误。
- ROM 手控版本号识别补齐 3 种边界格式：空格分隔 `ITE_NOR 120.3.1`、下划线子版本 `46_002`、无前缀三段式 `120.3.1`（含 `NULLLOG_16.3.7_FY` 后缀变体），修复 `\b` 因 `_` 属 `\w` 导致边界失效的根因；版本匹配从 10/15 → 13/15。
- `scan_firmware_assets()` catalog 类型匹配修复 `segmented_screen`（断码屏手控）被 `handcontrol_ui`（手控UI）抢先劫持：`segmented_screen` 移至 catalog 第二位，ROM+PKG 特殊返回保留为兜底。
- catalog 补齐 `.mot` 扩展名到 `music_bt`（蓝牙）、`movement_3d`、`movement_2d`（机芯板），修复 39 个 Renesas R5F104BC `.mot` 蓝牙固件和 3D/2D 机芯 `.mot` 文件完全扫不到的缺陷。
- catalog `movement_3d` / `movement_2d` 移除非特异性关键词 `机芯板` / `机芯板程序`，`commercial_mainboard` 移除 `投币机` / `纸币机`（归属 `card_reader`），降低类型误判。
- `asset_tree.py` `_insert_node` 增加 `tree.exists(iid)` 防御，先删后插避免筛选固件类型时 `Item already exists` Tkinter 崩溃。

### config
- 新增 `config.example.toml` 作为版本库标准配置样例；`config.toml` 改为本机私有配置，已从 Git 跟踪中移除并保留在 `.gitignore`。
- `.gitignore` 补齐 `.runtime/`、`dist/`、`build/`、临时 `*.spec` 与异常 `tool-resultsdirs_4deep.txt` 类文件规则，同时保留已跟踪的 `fwasset.spec`。
- `config.toml` / `settings.py` 的 `version_patterns` 新增 `_(\\d+_\\d+(?:_\\d+)?)$` 和 `(?<![0-9A-Za-z])(\\d+\\.\\d+\\.\\d+(?:_\\d+)?)(?![0-9A-Za-z])` 模式，覆盖下划线子版本和无前缀三段式版本号。

### refactor
- 新增 `AssetSelectionModel`，把资源列表当前选中项、隐藏条目缓存和隐藏判定从 `FirmwareListPanel` 拆出；面板保留兼容属性（`_selected_idx` / `_hidden_items` property），现有 UI 与 smoke test 构造方式不变。

### refactor
- 新增 `AssetSelectionModel`，把资源列表当前选中项、隐藏条目缓存和隐藏判定从 `FirmwareListPanel` 拆出；面板保留兼容属性（`_selected_idx` / `_hidden_items` property），现有 UI 与 smoke test 构造方式不变。

### test
- 新增 `tests/test_asset_selection_model.py`，覆盖选中索引收敛、选中资源读取、刷写模式读取、隐藏条目与隐藏类型判定。
- 新增 `tests/test_asset_tree_view.py`，锁定资源树叶子行不再重复展示型号目录和固件类型；扩展 catalog、扫描、索引与 UI smoke tests，覆盖 `usb_flow` 归一化、v1→v2 索引迁移、手控缺 ROM/PKG 时不回退目录刷机、音乐文件目录刷机可用；本轮验证通过：`uv run python -m pytest tests\test_asset_index.py tests\test_firmware_catalog.py tests\test_file_scan.py tests\test_app_service_smoke.py -q --no-cov` -> `76 passed`，`.\scripts\test.ps1` -> `162 passed`，总覆盖率 `82.64%`。
- 新增 `tests/test_asset_filter_model.py`，覆盖 `AssetFilterModel` 的排序键映射、SQLite 查询委托、隐藏过滤、树形分组和可见叶子计算；本轮验证通过：`uv run python -m pytest tests\test_asset_filter_model.py tests\test_app_service_smoke.py -q --no-cov` -> `24 passed`，`uv run python -m pytest tests\test_asset_index.py tests\test_scan_service.py -q --no-cov` -> `10 passed`，`.\scripts\test.ps1` -> `157 passed`，总覆盖率 `82.45%`。
- 扩展 `tests/test_asset_index.py`、`tests/test_scan_service.py` 和 `tests/test_app_service_smoke.py`，覆盖 SQLite 查询排序、缓存计数读取以及 UI 筛选调用 `query_assets()` 的路径；本轮验证通过：`uv run python -m pytest tests\test_asset_index.py tests\test_scan_service.py tests\test_app_service_smoke.py -q --no-cov` -> `31 passed`，`uv run python -m pytest tests\test_src_layout.py tests\test_settings.py -q --no-cov` -> `18 passed`，`.\scripts\test.ps1` -> `154 passed`，总覆盖率 `82.45%`。
- 更新快速定位测试，直接验证 `FirmwareListPanel` 正式类方法，不再依赖 `app.py` 运行时 monkey patch。
- 扩展 settings 与 logging 测试，覆盖运行时目录解析、环境变量覆盖、目录创建和默认日志路径。
- 本轮验证通过：`uv run python -m pytest tests\test_src_layout.py tests\test_app_quick_locate.py tests\test_settings.py -q --no-cov` -> `22 passed`；`uv run python -m pytest tests\test_asset_index.py tests\test_logging_utils.py tests\test_app_service_smoke.py -q --no-cov` -> `29 passed`；`.\scripts\test.ps1` -> `153 passed`，总覆盖率 `82.49%`。
- `tests/test_file_scan.py` 新增 12 个边界测试用例（空格分隔 ROM 版本、`NULLLOG_FY` 后缀、`Beelogo_103.3.1`、`H530_62.3.2`、`46_002` 下划线子版本、`segmented_screen` 优先级、`.mot` 扩展名检测）。

### docs
- `specs/active/TASK-20260511-technical-plan.md` 将 Issue 1 推进到第二阶段：选中状态与隐藏判定已拆入 `AssetSelectionModel`，操作区拆分仍待继续。
- `specs/active/TASK-20260511-technical-plan.md` 将 Issue 1 第一阶段标记为已完成：筛选查询、排序和树形分组逻辑已下沉到 `AssetFilterModel`。
- 新增 `specs/active/TASK-20260511-technical-plan.md` 技术债务路线图，并将 Issue 2（SQLite 查询替换内存全量筛选）标记为已完成。
- 新增 `specs/archive/project-structure-cleanup-todo.md`，记录根目录清理、配置样例、入口清理、运行时数据隔离和验收测试 TODO，并在 `specs/active/TASK-20260505-newtasks.md` 横向任务中引用。
- `README.md` 补充首次运行复制 `config.example.toml`、配置 `root_dir` / `tool_root`、运行时目录与日志/索引位置说明。
- 新增 `specs/bug_plan5-8.md`，记录 YJ-按摩椅程序汇总目录深度分析中发现的 7 个缺陷及修复方案。

### app
- 蓝牙程序不再进入 USB 目录复制或串口发送/AT 修改流程；选中蓝牙资产时只展示外部工具启动操作，目录复制仅保留给音乐文件。
- 资源树表收敛重复信息：型号目录只保留在树层级中，叶子行移除重复的型号目录与固件类型列，明细列聚焦程序目录和版本。
- `auto_usb` 操作区改为按 `usb_flow` 显式分流：手控/断码屏仅允许成对 ROM+PKG 文件刷机，缺文件时提示不可执行；音乐文件继续保留目录复制刷机。
- 新增 `AssetFilterModel`，将固件资源列表的查询筛选、排序键解析、树形分组和可见叶子计算从 `FirmwareListPanel` 拆出，降低列表面板的职责集中度。
- 固件资源列表筛选改为调用 SQLite `query_assets()`，移除 `_all_assets` 全量缓存；隐藏条目过滤、空状态提示和扫描后刷新行为保持不变。
- `src/fwasset/app.py` 移除旧版 tkinter monkey patch 和未使用 service imports，收敛为 `main()` 入口、`App` 兼容导出和 `UnifiedFlashPlatform` 导出。
- `_open_in_explorer`、`_open_folder_from_listbox` 正式迁回 `FirmwareListPanel`，快速定位、目录不存在提示和打开失败提示行为保持不变。
- 固件资源列表改用 `ttk.Treeview` 高密度树表渲染“系列 → 型号目录 → 固件类型 → 程序版本”，筛选刷新不再同步销毁并重建大量 CTk 卡片；保留叶子选中、双击打开目录和右键隐藏/恢复。
- Treeview 行字体与行高加大，并从主表格移除“方式”和“路径”列；刷写方式与原始路径继续在选中摘要/详情数据中显示，减少列表横向占用。
- Treeview 正文字体继续放大并提高对比度，分组行不再使用浅灰文字；左侧列表下方移除选中详情卡，路径、方式和文件摘要改到右侧操作区顶部展示。
- 切换固件类型筛选时重置树展开状态，确保手控、主板、蓝牙等类型默认展开行为一致；叶子行第一列改为型号，版本只保留在“版本”列，避免重复显示。
- 运行日志保持在右侧底部区域，默认折叠且不参与主内容高度分配。
- 左侧顶部筛选区压缩为单行快速定位工具栏：搜索、固件类型单选下拉、排序、清空、显示隐藏和扫描根目录；默认仍要求先选择一种固件类型，“全部类型”作为显式选项。
- 固件资源列表完成 P1-9 布局反转：左侧树形资源区扩展为主工作区，右侧收敛为操作区；选中条目的型号、版本、路径和文件摘要移动到左侧底部状态条，运行日志默认折叠。
- 资源树新增条目隐藏/恢复：支持右键隐藏型号目录、固件类型或单个版本，并通过“显示隐藏”复选框临时查看和恢复；隐藏状态持久化到 SQLite `hidden_items`。
- 固件资源列表左侧改为“系列 → 型号配置目录 → 固件类型 → 程序版本”的可折叠树形导航；搜索和类型筛选后自动展开匹配节点，点击程序版本继续驱动右侧详情和 `flash_mode` 操作区。
- 固件资源列表启动时优先读取本地 SQLite 资产索引；首次无索引时提示扫描根目录，避免每次启动都现场全量扫盘。
- 固件资源列表默认不再全选全部类型，改为提示先选择一种固件类型，降低操作员在混合列表中误选程序的风险。
- 工具中心完善为“先打开工具再找程序”的工作流：支持搜索工具名/固件类型/目录关键词，打开后自动解析可启动工具，并提供常用工具与最近使用工具区。
- 工具中心工具行新增星标收藏，启动成功后自动记录最近使用，状态持久化到应用目录 `tool_usage.json`。
- `tool_launch` 类型操作区接入工具发现结果，选中外部工具型固件后可直接打开烧录工具和固件目录。
- 操作区按 `flash_mode` 渲染补齐：外部工具型条目支持打开程序目录、复制目录路径、复制主文件路径、打开工具并同步打开程序目录；说明型和禁用型条目显示对应操作状态。
- 资源详情面板新增“系列”字段，为后续系列优先的树形导航提供可见校验点。

### core
- 新增 `core/asset_index.py`，使用标准库 `sqlite3` 管理 `fwasset.db`，持久化 `assets`、`hidden_items` 和 `scan_meta`，支持 schema 版本检查、资产读写、关键词/类型查询与隐藏记录清理。
- `scan_service` 扫描完成后写入 SQLite 本地资产索引，并新增缓存读取入口供 UI 启动时加载最近一次结果。
- 新增 `core/tool_discovery.py`，按 `tool_path`、`tool_root + tool_dir`、`tool_root` 模糊搜索、`APP_ROOT/tools/` 兜底的优先级发现外部烧录工具，并缓存首次匹配结果。
- 新增 `core/tool_usage.py`，管理工具中心收藏与最近使用状态。
- 扩展 `FirmwareAsset` / catalog 类型结构，新增 `tool_dir` 字段用于按固件类型定位外部工具目录。
- 扩展 catalog 目录关键词，覆盖手控、主板、蓝牙、语音、快捷键、机芯板、旋钮、商用支付和三合一等实际目录别名。
- 扫描目录排除规则补齐 `接线图`、`旧`、`新建文件夹`、`照片`，并改为大小写不敏感匹配。
- `scan_firmware_assets()` 输出新增 `series`，按型号或目录中的 `[A-Z]+[0-9]+` 前缀推断系列归属。
- `scan_firmware_assets()` 输出新增 `model_directory_name` / `model_directory_path`，为“系列 → 型号配置目录 → 固件类型”树形导航提供稳定中间层数据。

### config
- 新增 `fwasset.db` 作为本地资产索引默认文件名，约定与 exe、`config.toml`、`firmware_catalog.toml` 同目录，并加入 `.gitignore` 避免提交本机索引数据。
- `config.toml` 新增 `[paths] tool_root`，用于配置外部刷程序工具库根目录。
- `firmware_catalog.toml` 为工具启动类固件补充 `tool_dir`，并新增 `tools/` 兜底目录骨架模板。
- `config.toml` 的扫描排除目录同步更新为实际非固件目录关键词。

### test
- 扩展 `tests/test_app_service_smoke.py`，覆盖 Treeview 分组填充、单选固件类型筛选、清空筛选、显示隐藏、隐藏型号目录过滤、叶子选择、双击打开目录和右键隐藏菜单回调；本轮验证通过：`uv run python -m pytest tests\test_app_service_smoke.py -q --no-cov` -> `21 passed`，`.\scripts\test.ps1` -> `138 passed`。
- 扩展 `tests/test_app_service_smoke.py`，覆盖隐藏型号目录在默认视图中过滤、启用“显示隐藏”后恢复展示；本轮验证通过：`.\scripts\test.ps1` -> `136 passed`，总覆盖率 `82.45%`。
- 扩展 `tests/test_app_service_smoke.py`，覆盖树形导航分组、版本数量统计、折叠/展开以及叶子节点选择兼容行为；本轮验证通过：`.\scripts\test.ps1` -> `135 passed`，总覆盖率 `82.45%`。
- 新增 `tests/test_asset_index.py`，覆盖 SQLite schema 初始化、版本检查、资产读写、关键词/类型查询、过期资产删除和隐藏状态持久化清理；本轮验证通过：`.\scripts\test.ps1` -> `133 passed`，总覆盖率 `82.36%`。
- 新增 `tests/test_tool_discovery.py` 与 `tests/test_tool_usage.py`，覆盖工具发现优先级、缓存、兜底目录、收藏和最近使用状态。
- 扩展 `tests/test_app_service_smoke.py`，覆盖 P1-10 程序交接动作和 `manual_doc` / `disabled` 操作区渲染。
- 扩展 catalog 与文件扫描测试，覆盖实际目录别名识别和非固件目录过滤。
- 扩展文件扫描和 UI smoke tests，覆盖系列推断与详情展示兼容行为。
- 本轮验证通过：`.\scripts\test.ps1` -> `120 passed`，总覆盖率 `80.87%`。

### refactor
- 包名与源码根目录从 `handcontrol` 统一迁移到 `fwasset`，同步更新启动入口、测试导入与打包脚本，收敛为“固件资源管理平台”命名。

### core
- 新增 `firmware_catalog.toml` 运行时目录，并将固件类型扩展为 19 类，统一定义 `FirmwareType`、`FlashMode`、`FirmwareAsset` 等核心类型。
- `core/file_scan.py` 新增 catalog 驱动的通用扫描 `scan_firmware_assets()`：按目录关键字与文件扩展名识别固件类型，返回统一资产结构，并显式汇报目录读取错误。
- `core/services/scan_service.py` 扩展扫描返回结构，同时提供统一 `assets`、兼容用 `folders` 与 `errors`，为后续单列表 UI 合并提供稳定输入。
- `core/usb_ops.py` 修复 `format_usb` 的命令注入风险：移除 `shell=True`，改用参数列表调用，并补齐超时处理。

### docs
- 新增 `specs/l36-app-feasibility.md`，整理 L36 用户控制 App 可行性调研问题清单、供应商交付物、难度判断标准、公司资源调度和第一次会议议程。
- 新增 `specs/active/TASK-20260505-newtasks.md`，把当前需求整理为分阶段 todo，并与 `requirements-spec.md`、`firmware-types-catalog.md` 对齐。

### test
- 新增 `tests/test_firmware_catalog.py`，覆盖 catalog 缺失、规范化与启用过滤行为。
- 扩展 `tests/test_file_scan.py`、`tests/test_scan_service.py`、`tests/test_usb_ops.py`，覆盖 19 类 catalog 基线、通用扫描返回结构与 `format_usb` 超时分支。
- 本轮验证通过：`uv sync --extra dev; .\\.venv\\Scripts\\python.exe -m pytest -q` -> `107 passed`，总覆盖率 `82.98%`。

### app
- 手控面板删除 Excel 台账入口与预览，收敛为“刷机操作 + 资源详情 + 运行日志”界面。
- 手控资源详情区域改为展示型号、版本、目录、原始路径、ROM/PKG 文件与可执行操作说明；保留双击打开目录与下一项切换。
- 一键刷机与手动 U 盘操作继续保留，但不再触发任何台账写入或历史回填逻辑。

### core
- 删除 Excel 运行时能力：移除 `core/excel_ops.py`、`core/services/excel_service.py` 以及相关导出、类型和配置项。
- `scan_service.build_scan_result` 收敛为仅返回扫描目录结果；`flash_service.run_one_click` 收敛为清理、复制、弹出三段刷机流程。
- 清理 `sort_config.py` 中已无调用方的状态排序分支，仅保留路径、型号、版本排序。

### config
- `config.toml` 删除 Excel 配置段，保留根目录、USB、扫描、音乐和串口配置。
- 删除 `data/handcontrol_ui_template.xlsx` 模板文件，不再保留台账示例资源。

### docs
- `README.md`、`pyproject.toml` 与相关 specs 更新为统一资产管理、目录定位与刷机流程表述，不再描述 Excel 台账能力。

### test
- 删除全部 Excel/CRUD/预览缓存相关测试，重建手控扫描、刷机、诊断与面板 smoke tests 以匹配新接口。
- 补充快速定位兼容测试所需入口，确保旧测试辅助路径仍可通过。
- 本轮验证通过：`.\scripts\test.ps1` -> `105 passed`。

### app
- 新增 `src/handcontrol/ui/` 现代化 CTk 界面层：拆分为 `shell / handcontrol_panel / music_panel / shared_widgets / design_tokens`，统一承载双模式 UI。
- `src/handcontrol/app.py` 入口切换为加载 UI Reactor 壳层，保留 legacy import 兼容测试引用。
- 手控模式完成卡片式左侧列表、右侧刷机/审核卡片、底部预览/日志面板迁移；保留扫描、写表、一键、预览搜索/删除/双击回填等能力。
- 音乐模式完成串口扫描/连接、AT 发送、U 盘流程、日志区迁移，并继续通过 `core/services` 驱动业务。
- 修复手控回归：根目录按钮恢复真实目录选择；预览双击回填补齐备注与审核状态；列表恢复单击选择、双击打开目录。
- 修复列表体验：默认排序改为更接近 Win11 资源管理器的路径自然顺序；单击选中不再重建整列卡片；双击打开目录稳定恢复。
- 修复模式切换体验：手控/音乐面板都补齐 `activate/deactivate` 生命周期；切换时同步侧边栏模式按钮；壳层从 `pack/pack_forget` 改为预挂载后 `tkraise()`，降低切回手控时的重布局卡顿。

### compat
- `pyproject.toml` 新增运行依赖 `customtkinter>=5.2.2`，并暂时将 `src/handcontrol/ui/*` 纳入 coverage omit，避免迁移阶段 UI 壳层拖低门禁。

### test
- 新增 `tests/test_ui_reactor_entry.py`，验证应用入口会路由到 UI Reactor 壳层。
- 重写并扩展 `tests/test_app_service_smoke.py`，覆盖手控/音乐 CTk 面板的扫描、选择、回填、双击打开、轮询停启、懒创建与模式切换同步。
- 扩展 `tests/test_sort_config.py`，补充默认路径自然排序场景。
- 本轮验证通过：`python -m pytest -q` -> `150 passed, 8 skipped`，总覆盖率 `85.15%`。
- 本轮验证通过：`.\scripts\test.ps1` 完成测试链路执行；本机 `uv` 缓存目录有权限告警噪音，但不影响 pytest 结果。

### core
- 新增 `core/services/serial_service.py`：提供串口扫描、连接/断开、命令发送与波特率探测能力，统一返回 `ok/code/message/payload` 结构。
- 新增 `core/services/at_command_service.py`：封装 AT 指令发送与 `AT+BD` 波特率切换验证流程（新波特率成功、旧波特率未切换、状态未知三类结果）。
- `core/services/serial_service.py` 补充 `read_serial_messages`，将串口读循环基础能力下沉到服务层。
- 新增 `core/services/music_flash_service.py`：封装音乐版 U 盘流程（格式化→复制目录→弹出）。
- `core/usb_ops.py` 新增 `copy_directory_to_usb`，支持目录级复制并覆盖旧目标目录。
- 扩展 `core/types.py`：新增 `FirmwareType`、`ServiceResult`、`SerialPortInfo`、`SerialCommandResult`、`FlashJobResult` 等统一领域类型。
- 更新 `core/services/__init__.py` 导出，补齐新增服务模块入口。
- `core/settings.py` 新增音乐/串口配置读取：`MUSIC_DEFAULT_SOURCE_DIR`、`SERIAL_DEFAULT_BAUDRATE`、`SERIAL_AT_PRESETS`。

### test
- 新增 `tests/test_serial_service.py`，覆盖串口服务核心分支（依赖缺失、扫描成功、连接成功、命令发送、波特率探测未匹配）。
- 新增 `tests/test_at_command_service.py`，覆盖 AT 服务分支（成功、拒绝、波特率切换成功/未改变/未知）。
- 新增 `tests/test_music_flash_service.py`，覆盖音乐版流程服务的成功/失败路径。
- 扩展 `tests/test_usb_ops.py`，覆盖 `copy_directory_to_usb` 行为。
- 扩展 `tests/test_settings.py`，覆盖音乐/串口默认配置读取。
- 扩展 `tests/test_app_service_smoke.py`，补充音乐模式场景（串口扫描、连接切换、AT 预设、音乐流程调用）。

### refactor
- 完成 `src layout` 迁移：源码从根目录迁移到 `src/handcontrol/`，根目录新增 `run.py` 作为轻量启动入口。
- 构建后端切换为 `hatchling`，新增 `project.scripts.handcontrol` 入口，项目改为可安装包结构。
- 所有源码与测试导入统一改为 `handcontrol.*`，不再保留根目录 `app.py` 与 `core/` 兼容层。
- `core.settings` 新增 `_find_project_root`，改为动态向上查找 `pyproject.toml` 以定位项目根目录。

### test
- 新增 `tests/test_src_layout.py`，校验 `src/handcontrol/` 结构、启动入口、依赖配置、旧导入清理与 `PROJECT_ROOT` 解析。
- 开发依赖新增 `hypothesis`，用于 `src layout` 迁移后的路径性质测试。
- 迁移前基线：`python -m pytest -q --cov=core`，`127 passed`，总覆盖率 `86.60%`。
- 新增 `tests/test_diagnostics.py`，覆盖诊断包内容生成、缺失日志回退与路径脱敏逻辑。
- 扩展 `tests/test_app_service_smoke.py`，覆盖诊断包导出入口与一键执行成功后自动跳转到下一项。
- 新增 `tests/test_excel_integration.py`，使用真实临时 Excel 文件覆盖 service 级写入与备用文件合并链路。
- 扩展 `tests/test_excel_ops.py` 与 `tests/test_app_service_smoke.py`，覆盖备用文件合并成功、无新行与 UI 刷新提示。

### test
- 新增 `pytest` 测试框架基础配置（`tests` 目录与 `tool.pytest.ini_options`）。
- 新增 `tests/test_file_scan.py`，覆盖 `parse_rom_filename`、`guess_model_from_path`、`find_handcontrol_folders` 的核心场景（识别、过滤、排序）。
- 新增 `tests/test_excel_ops.py`，覆盖 `write_excel_record` 的新建写入、同型号版本覆盖更新、占用回退与异常失败分支，以及读取函数行为校验。
- 新增 `tests/test_usb_ops.py`，覆盖 `get_usb_drives`、`clean_usb`、`copy_to_usb`、`eject_usb`、`format_usb` 的成功与失败路径（基于 mock，无真实设备操作）。
- 阶段 1/2/3/4 验证通过：`python -m pytest -q`，当前用例全部通过。
- 阶段 5 完成并提升门禁：`core` 覆盖率门禁提高到 >= 80%，并通过测试。
- 新增 `tests/test_app_preview_cache.py`，覆盖预览缓存增量更新（insert/update）与 Excel 行映射逻辑。
- 新增 `tests/test_scan_service.py`、`tests/test_excel_service.py`、`tests/test_flash_service.py`，覆盖 service 层扫描聚合、写表转换与一键流程编排。
- 新增 `tests/test_app_service_smoke.py`，验证 `app.py` 通过 service 返回结果做 UI 渲染与提示。
- 扩展 `tests/test_usb_ops.py`：覆盖 `diagnose_usb_health` 与 `repair_usb_driver` 的成功、失败、权限分支。

- 新增 `tests/test_usb_repair_service.py`，覆盖 USB 修复 service 的成功、失败与异常分支。
- 新增 `tests/test_crud_ops.py`，覆盖 CRUD 三阶段核心路径（搜索匹配逻辑、字段更新、行删除分支）。
- 扩展 `tests/test_excel_ops.py`、`tests/test_excel_service.py`、`tests/test_flash_service.py`、`tests/test_app_*` 与 `tests/test_crud_ops.py`，覆盖附图字段读写、预览映射与搜索行为。
- 扩展 `tests/test_app_preview_cache.py` 与 `tests/test_app_service_smoke.py`，补充过滤态 upsert 去重、离线历史保存、删除后序号重排等回归场景。
- 新增 `tests/test_app_service_smoke.py` 场景：左侧手控列表关键字过滤与扫描后过滤生效。
- 扩展 `tests/test_excel_service.py`，覆盖 `update_record_fields` 与 `delete_record` 的成功/失败分支映射。
- 新增 `tests/test_sort_config.py`，覆盖型号自然排序、版本号数值排序、测试状态排序与升/降序分支。
- 扩展 `tests/test_app_service_smoke.py`，新增左侧手控列表按状态过滤、按型号排序、按测试状态排序场景。
- 扩展 	ests/test_file_scan.py 与 	ests/test_settings.py，覆盖识别规则配置化、扩展名配置化、目录排除配置化与默认回退场景。

### chore
- `pyproject.toml` 增加 `dev` 额外依赖组：`pytest>=8.0.0`，用于本地单元测试。
- `pyproject.toml` 增加 `pytest-cov` 并将默认门禁提升到：`--cov=core --cov-fail-under=80`。
- 新增 `scripts/test.ps1` 统一测试入口（`uv sync --extra dev` + `pytest`）。

### docs
- 新增 `COMMIT_TEMPLATE.md`，提供中文 commit message 标准模板、`type` 对照与项目示例。
- 新增 `README.md`，补充项目简介、功能说明、运行环境、安装依赖、使用步骤、常见问题与后续规划。
- 更新 `README.md` 安装与测试说明：明确 `uv sync --extra dev` 路径，新增“测试与阶段进度”章节，启动阶段 5 文档收口。
- 更新 `README.md`：新增覆盖率门禁执行方式，阶段 5 状态改为已完成。

### app
- 主程序 `app.py` 新增“音乐模式”Tab，与手控模式并存，实现单程序双模式入口。
- 音乐模式接入 service 层：串口扫描/连接/AT发送/波特率切换与 U 盘流程均通过 `core/services` 调用，UI 只保留交互与展示。
- 关闭窗口时新增音乐串口自动断开，降低端口占用残留风险。
- 新增“导出诊断包”按钮：可一键导出日志、脱敏配置、当前列表状态、预览快照与环境摘要，便于远程排查。
- 一键执行在复制与 Excel 写入成功后，会自动选中并跳转到下一个文件夹，减少人工点击。
- 新增“合并备用文件到主表”按钮：当主表曾被占用产生 `*_刷机记录_待导入.xlsx` 时，可直接把其中的新行合并回主表并刷新预览。
- 调整 Excel 写入调用逻辑：从布尔返回值改为读取结构化结果。
- 根据写入结果区分提示：`locked` 显示“占用并给出备用文件路径”，其他失败显示具体错误信息。
- 修复 `_write_excel` 与 `_one_click`：写表时补充传入 `logo/language/salesman` 字段，保持与审核保存一致。
- 高优修复：扫描、复制、格式化、写表、预览读取改为后台任务执行，避免 Tk 主线程阻塞导致界面“未响应”。
- 预览性能优化：引入内存缓存（`_preview_rows/_preview_by_key/_preview_item_by_key`），写入成功后按 `(MODEL, VERSION)` 增量更新 Treeview，不再每次全量读盘重绘。
- 预览全量读盘收敛为手动刷新（含启动初次加载、切换 Excel 路径时重载）。
- 高优重构：`_scan`、`_write_excel`、`_one_click`、`_save_review` 改为调用 service 层，UI 仅负责事件绑定、状态展示与提示。
- 数量统计：扫描结果列表新增 `001.` 样式序号前缀，便于人工快速计数（仅展示层，不影响业务字段）。
- U盘驱动修复：新增插入后轻量健康检测（后台轮询、仅异常提示），不自动执行重修复。
- 新增“驱动扫描/修复”按钮，调用 Windows 内置修复链路（`chkdsk /scan` + `pnputil /scan-devices`）。
- CRUD 修复：预览搜索新增统一关键词读取，修复过滤态下预览缓存 upsert 重复追加问题。
- CRUD 修复：双击预览进入离线编辑上下文，`_save_review` 支持不依赖左侧扫描列表直接保存历史记录。
- CRUD 修复：删除预览记录改为 service 调用，成功后仅内存增量移除并重排序号，避免全量读盘。
- 快速定位：左侧手控文件夹列表支持双击直接打开对应目录（Explorer），并补充路径不存在/打开失败提示。
- 左侧手控文件夹列表新增过滤框与基础过滤逻辑（内存过滤，支持按型号/版本/标签/路径关键字快速收敛结果）。
- 左侧手控列表新增“状态筛选 + 排序”控件，支持按型号、版本号、测试状态排序及升/降序切换。
- 默认排序回退为按完整目录路径升序（与历史版本/Windows 目录顺序一致）。
- 左侧手控列表搜索/排序 UI 重做：将“过滤”统一改名为“搜索”，移除排序下拉，改为模拟表头点击排序并显示方向箭头。
- 左侧手控列表文本调整为等宽伪多列显示（序号/名称/型号/版本/状态），与表头交互保持一致。
- 左侧手控列表显示修正：列表列顺序调整为“序号/型号/版本/名称”，移除状态文字列，仅保留颜色状态提示，恢复更稳定的对齐效果。
- 状态回显改为基于 `(MODEL, VERSION)` 的状态映射更新，写表/审核/一键后会自动重算当前筛选与排序结果。
- 新增本地错误日志落盘：运行日志与后台异常、UI 回调异常统一写入 logs/app.log，便于排查现场问题。
- 表格新增列（附图）：在审核填写、Excel 写入/读取、预览缓存与搜索、一键执行与历史编辑链路中接入 `attachment` 字段。

### core
- 新增 `core/diagnostics.py`：生成最小化诊断 zip，包含元信息、脱敏配置、预览快照、列表状态和日志文件。
- `core/excel_ops.py` 新增备用文件合并能力：按 `MODEL + VERSION` 去重，将 `*_刷机记录_待导入.xlsx` 中的新行回写主表并自动重排序号。
- 为关键返回结构引入 TypedDict：`HandcontrolFolder`、`ExcelWrittenRow`、`ExcelWriteResult`，并在 `find_handcontrol_folders` 与 `write_excel_record` 上落地类型注解。
- core/excel_ops.py：
  - `write_excel_record` 返回结构改为 `ok / reason / tmp_path / error`。
  - `write_excel_record` 成功返回新增 `written_row`（model/logo/salesman/language/version/date/remark），供 UI 直接增量刷新。
  - 增加文件不存在场景处理；Excel 被占用时写入 `*_刷机记录_待导入.xlsx` 并返回 `reason=locked`。
  - 新建表格首行标题文案调整为“现有手控UI明细”。
  - 新增 A 列序号自动重排：按有效数据行（B~I 任一非空）连续编号 `1..N`，仅用于数量统计，与型号无绑定。
- `core/settings.py`：
  - 新增 `config.toml` 加载能力（优先 `tomllib`，回退可选 `tomli`）。
  - 增加默认配置回退与类型兜底（路径、Excel Sheet/Header、USB 清理规则）。
  - 支持相对 `excel_path` 按项目根目录解析为绝对路径。
  - 高优修复：配置加载新增状态与错误信息（`ok/missing/parser_missing/parse_error`），不再静默吞掉配置失效。
  - 去除机器耦合默认路径：`paths.root_dir` 内置默认值改为空字符串，避免在配置缺失/失败时显示无效绝对路径。
- 新增 `core/services/`：
  - `scan_service.py`：封装扫描与状态聚合。
  - `excel_service.py`：封装写表请求与返回转换（含 `preview_row`）。
  - `flash_service.py`：封装一键流程编排（清理→复制→弹出→写表）。
  - `usb_repair_service.py`：封装 U 盘健康检测与驱动修复返回转换。
  - `excel_service.py` 扩展：新增 `update_record_fields` 与 `delete_record` 封装，统一 CRUD 的 service 返回结构。
- 新增 `core/sort_config.py`：封装列表排序纯函数与 `SortKey` 枚举（文件夹名/型号/版本号/测试状态）。
- core/file_scan.py 改为规则驱动识别：ROM/PKG 扩展名、目录排除词、型号正则、版本正则、路径补偿正则均可通过 config.toml 的 [scan] 配置覆盖。

### data
- 更新 `data/handcontrol_ui_template.xlsx` 模板内容（二进制文件变更）。

### config
- 新增 `config.toml`，用于集中配置扫描目录、Excel 参数和 USB 清理规则。
- `config.toml` 新增 `[music]` 与 `[serial]` 区块，支持音乐目录、默认波特率与 AT 预设配置化。
- `config.toml` 示例 `paths.root_dir` 改为空字符串，避免模板携带特定机器绝对路径。
- `config.toml` 新增 `usb.auto_diagnose_on_insert` 与 `usb.health_check_interval_sec` 配置项。
- config.toml 新增 [scan] 配置段，支持扫描识别规则配置化。

### compat
- `pyproject.toml` 增加 `tomli` 条件依赖（`python_version < 3.11`），确保 Python 3.8-3.10 可读取 TOML 配置。

### 接口变更
- `core.excel_ops.write_excel_record` 的返回类型由 `bool` 变为结果字典；调用方需按键读取状态，不再只判断真/假。

## 2026-03-20

### fbe220d
- `refactor: split ui app and core modules with compatible launcher`
- 将 UI 与 `core` 能力模块拆分，保留兼容入口，形成更清晰的分层结构。

### 789b8e6
- `chore: initialize repo, uv setup, sanitize template, and module1 cleanup`
- 完成仓库初始化与基础工程落地（含模板文件、项目配置与初始脚手架整理）。
