# Firmware Flash Automation

用于固件刷机自动化与测试台账管理的 Python 工具集，当前已落地模块为手控 UI。

## 当前结构

```text
Firmware Flash Automation/
├── run.py
├── src/
│   └── handcontrol/
│       ├── __init__.py
│       ├── app.py
│       └── core/
├── tests/
├── config.toml
└── pyproject.toml
```

## 环境要求

- Windows 10/11
- Python >= 3.8
- 推荐使用 `uv`

## 安装

```powershell
uv venv .venv
.venv\Scripts\Activate.ps1
uv sync --extra dev
```

## 启动

项目支持两种启动方式：

```powershell
python run.py
```

```powershell
uv run handcontrol
```

## 配置

主要配置位于 `config.toml`：

- `paths.root_dir`：扫描根目录
- `paths.excel_path`：Excel 台账路径，支持相对项目根目录
- `excel.sheet` / `excel.header_row`：Excel 工作表配置
- `usb.*`：U 盘清理和诊断配置
- `scan.*`：文件识别规则、扩展名和排除目录规则

## 测试

运行全部测试：

```powershell
python -m pytest -q
```

当前覆盖率门禁：

```text
--cov=src/handcontrol --cov-fail-under=80
```

统一脚本：

```powershell
.\scripts\test.ps1
```

## 说明

- 源码已迁移到标准 `src layout`
- 根目录不再保留旧 `app.py` 和 `core/` 兼容入口
- 包入口为 `handcontrol`
