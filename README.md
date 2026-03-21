# HandControlUITool

## 项目简介

HandControlUITool 是一个 Windows 桌面刷机辅助工具，用于手控 UI 程序的日常作业流程：扫描 ROM/PKG 文件夹、准备 U 盘、记录测试状态，并同步到 Excel 台账。  
项目当前采用 `app.py (UI)` + `core/* (业务能力)` 的模块化结构。

## 功能说明

- 递归扫描根目录，识别同时包含 `.ROM` 和 `.PKG` 的可刷机目录。
- 自动解析型号与版本（支持从 ROM 文件名和路径补偿识别）。
- U 盘操作流程：清理垃圾文件、格式化 FAT32、复制 ROM/PKG、安全弹出。
- 一键执行流程：清理 -> 复制 -> 弹出 -> 写入 Excel（默认“待确认”）。
- 审核页支持写入 `logo / 语言 / 业务员 / 备注 / 测试状态`。
- Excel 被 WPS/Excel 占用时，自动写入备用文件 `*_刷机记录_待导入.xlsx`。
- 支持 `config.toml` 配置默认路径、Excel 参数、USB 清理规则。
- 扫描、复制、格式化、写表等耗时操作在后台线程执行，界面保持可响应。
- 预览区采用内存缓存与增量更新；外部修改 Excel 后请点击“刷新预览”手动同步。

## 运行环境

- 操作系统：Windows 10/11（依赖盘符与 PowerShell 弹出逻辑）。
- Python：`>= 3.8`（推荐 `3.11+`，可直接使用内置 `tomllib`）。
- 依赖库：
- `openpyxl>=3.1.0`
- `psutil>=5.9.0`
- `tomli>=2.0.0`（仅 Python 3.8-3.10 读取 `config.toml` 时需要）

## 安装依赖

### 方式一：使用 uv（推荐）

```powershell
uv venv .venv
.venv\Scripts\Activate.ps1
uv sync --extra dev
```

启动：

```powershell
uv run python app.py
```

### 方式二：使用 pip

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install openpyxl>=3.1.0 psutil>=5.9.0 pytest>=8.0.0
```

## 使用步骤

1. 准备并激活虚拟环境（见“安装依赖”）。
2. 启动程序：

```powershell
python app.py
```

3. 首次运行前检查 `config.toml`：
- `paths.root_dir`：程序扫描根目录。
- `paths.excel_path`：Excel 台账路径（相对路径按项目根目录解析）。
- `excel.sheet` 与 `excel.header_row`：Excel 工作表与表头起始行。
- `usb.junk_extensions` 与 `usb.junk_filenames`：U 盘清理规则。
4. 在界面中点击“扫描目录”，选择目标型号记录。
5. 选择 U 盘盘符并执行刷机步骤，或直接使用“一键执行”。
6. 测试后在“审核填写”页保存结果，写入 Excel。
7. 若出现 Excel 占用提示，先关闭 WPS/Excel，再补录或合并备用文件。

## 测试与阶段进度

执行测试：

```powershell
.venv\Scripts\python.exe -m pytest -q
```

执行带覆盖率门禁测试（当前门禁：`core` 覆盖率 >= 70%）：

```powershell
.\scripts\test.ps1
```

当前阶段状态：
- 阶段 1（测试骨架）: 已完成
- 阶段 2（`file_scan`）: 已完成
- 阶段 3（`excel_ops`）: 已完成
- 阶段 4（`usb_ops`）: 已完成
- 阶段 5（质量门禁与文档收口）: 已完成（当前门禁 70%，后续可提升到 80%）

## 常见问题

### 1) 检测不到 U 盘

- 先点击“刷新”按钮重试。
- 确认 U 盘已被系统识别并有盘符。
- 部分设备分区格式不在常见可移动盘识别范围内时，建议先在系统中重新挂载。

### 2) Excel 写入失败或提示被占用

- 关闭正在打开目标文件的 WPS/Excel。
- 查看同目录下 `*_刷机记录_待导入.xlsx` 备用文件是否已生成。
- 若失败原因不是占用，请根据弹窗错误信息排查路径权限、文件损坏或工作表名配置。

### 3) 型号或版本识别不准确

- 优先检查 ROM 文件命名是否符合当前规则（如 `Lxx`、`Vx.x.x`）。
- 若文件名不完整，工具会尝试从路径推断型号。
- 可在审核页人工补充备注并完成台账修正。

### 4) 启动时报依赖缺失

- 确认在虚拟环境中运行。
- 使用 uv 时优先执行 `uv sync --extra dev`。
- 使用 pip 时重新安装依赖：`pip install openpyxl>=3.1.0 psutil>=5.9.0 pytest>=8.0.0 pytest-cov>=5.0.0`。

### 5) `config.toml` 修改后未生效

- 启动后查看日志顶部配置加载提示。
- 若显示“配置回退”，请按提示检查 `config.toml` 路径、语法，或在 Python 3.8-3.10 下确认已安装 `tomli`。

## 后续规划
- 增加 service 层，进一步减少 UI 代码中的流程编排逻辑。
- 为关键返回结构增加更严格类型注解（如 `TypedDict`）。
- 增加错误日志落盘与最小化诊断信息导出能力。
- 持续完善 `CHANGELOG.md` 与提交规范模板，统一协作流程。
