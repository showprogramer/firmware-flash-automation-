# firmware-flash-automation

用于按摩椅固件程序资产的搜索、定位、工具启动、刷机流程和运行日志管理。当前已落地模块包括手控 UI 与音乐固件流程。

## 当前能力

- 统一资产搜索与目录定位
- 手控 UI 目录扫描、资源详情展示、U 盘刷机流程
- 音乐固件串口连接、AT 指令和刷机流程
- 诊断包导出、日志收集与基础设备修复工具

## 运行

```powershell
uv sync --extra dev
.\.venv\Scripts\python.exe run.py
```

## 配置

`config.toml` 当前保留以下配置段：

- `paths.root_dir`
- `usb.*`
- `scan.*`
- `music.*`
- `serial.*`

## 测试

```powershell
.\scripts\test.ps1
```
