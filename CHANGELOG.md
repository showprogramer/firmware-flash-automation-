# 记录变更

## Unreleased

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



