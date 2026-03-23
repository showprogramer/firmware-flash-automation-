# 记录变更

## Unreleased

### test
- 新增 `pytest` 测试框架基础配置（`tests` 目录与 `tool.pytest.ini_options`）。
- 新增 `tests/test_file_scan.py`，覆盖 `parse_rom_filename`、`guess_model_from_path`、`find_handcontrol_folders` 的核心场景（识别、过滤、排序）。
- 新增 `tests/test_excel_ops.py`，覆盖 `write_excel_record` 的新建写入、同型号版本覆盖更新、占用回退与异常失败分支，以及读取函数行为校验。
- 新增 `tests/test_usb_ops.py`，覆盖 `get_usb_drives`、`clean_usb`、`copy_to_usb`、`eject_usb`、`format_usb` 的成功与失败路径（基于 mock，无真实设备操作）。
- 阶段 1/2/3/4 验证通过：`python -m pytest -q`，当前用例全部通过。
- 阶段 5 完成：新增覆盖率门禁（`core` 覆盖率 >= 70%）并通过测试。
- 新增 `tests/test_app_preview_cache.py`，覆盖预览缓存增量更新（insert/update）与 Excel 行映射逻辑。
- 新增 `tests/test_scan_service.py`、`tests/test_excel_service.py`、`tests/test_flash_service.py`，覆盖 service 层扫描聚合、写表转换与一键流程编排。
- 新增 `tests/test_app_service_smoke.py`，验证 `app.py` 通过 service 返回结果做 UI 渲染与提示。
- 扩展 `tests/test_usb_ops.py`：覆盖 `diagnose_usb_health` 与 `repair_usb_driver` 的成功、失败、权限分支。
- 新增 `tests/test_usb_repair_service.py`，覆盖 USB 修复 service 的成功、失败与异常分支。

### chore
- `pyproject.toml` 增加 `dev` 额外依赖组：`pytest>=8.0.0`，用于本地单元测试。
- `pyproject.toml` 增加 `pytest-cov` 及默认参数：`--cov=core --cov-fail-under=70`。
- 新增 `scripts/test.ps1` 统一测试入口（`uv sync --extra dev` + `pytest`）。

### docs
- 新增 `COMMIT_TEMPLATE.md`，提供中文 commit message 标准模板、`type` 对照与项目示例。
- 新增 `README.md`，补充项目简介、功能说明、运行环境、安装依赖、使用步骤、常见问题与后续规划。
- 更新 `README.md` 安装与测试说明：明确 `uv sync --extra dev` 路径，新增“测试与阶段进度”章节，启动阶段 5 文档收口。
- 更新 `README.md`：新增覆盖率门禁执行方式，阶段 5 状态改为已完成。

### app
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

### core
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

### data
- 更新 `data/handcontrol_ui_template.xlsx` 模板内容（二进制文件变更）。

### config
- 新增 `config.toml`，用于集中配置扫描目录、Excel 参数和 USB 清理规则。
- `config.toml` 示例 `paths.root_dir` 改为空字符串，避免模板携带特定机器绝对路径。
- `config.toml` 新增 `usb.auto_diagnose_on_insert` 与 `usb.health_check_interval_sec` 配置项。

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


