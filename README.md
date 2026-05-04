# firmware-flash-automation

用于按摩椅固件程序资产的搜索、定位、工具启动、刷机流程自动化和运行日志管理的桌面平台。本项目提供了一个基于 Python (CustomTkinter) 的图形化界面应用，能够显著提升固件版本管理与烧录效率。

## 当前能力

- **资产发现与动态分类：** 基于可配置的注册表 (`firmware_catalog.toml`) 扫描固件目录，支持近 20 种固件类型（手控UI、主板、蓝牙、语音、3D/2D机芯等）的智能识别。
- **手控 UI 刷机自动化：** 智能提取目录和文件中的产品型号与版本号；支持 U 盘状态动态监控、垃圾文件清理以及自动化资源拷贝刷机流程。
- **音乐蓝牙固件流程：** 集成串口连接控制、预设 AT 指令快速下发及蓝牙配置刷入流程。
- **系统级诊断服务：** 提供环境体检、诊断包一键导出、日志收集聚合等功能，方便线上排查。

## 安装与运行

本项目使用 `uv` 进行依赖和虚拟环境管理：

```powershell
# 同步依赖（包含开发和测试库）
uv sync --extra dev

# 运行应用
.\.venv\Scripts\python.exe run.py

# 或者使用快捷命令
uv run fwasset
```

## 配置说明

系统行为由项目根目录下的两个 TOML 文件控制：

### `config.toml`
核心参数配置文件，当前支持以下配置段：
- `paths.*`: `root_dir` (固件根目录默认路径)
- `usb.*`: U 盘监控与清理策略 (如 `junk_extensions`, `auto_diagnose_on_insert`)
- `scan.*`: 扫描匹配规则、型号/版本号提取正则、过滤关键字等
- `music.*`: 默认音乐固件资源目录
- `serial.*`: 串口默认波特率与常用 `at_presets`

### `firmware_catalog.toml`
固件资产类型注册表，动态驱动左侧边栏和搜索策略：
- `dir_keywords` / `file_extensions`: 该类型固件的目录关键字与文件后缀特征。
- `flash_mode`: 定义刷机行为（支持 `auto_usb` U盘自动刷写, `tool_launch` 拉起外部工具, `manual_doc` 提供文档说明）。
- `tool_name` / `tool_path`: 关联的具体烧录工具配置。

## 测试

执行基础测试、连通性检查与测试覆盖率报告：

```powershell
.\scripts\test.ps1
```
