# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — 打包为单文件 Windows .exe。

生成命令:  uv run pyinstaller fwasset.spec
输出文件:  dist/fwasset.exe

交付物结构（分发时 exe 同目录需放置）:
  fwasset.exe
  ├── config.toml             # 运行时配置（用户可编辑）
  ├── firmware_catalog.toml   # 固件类型定义
  └── logs/                   # 诊断日志（运行后自动创建）
"""

import sys
from pathlib import Path

# ── 隐藏导入 ──────────────────────────────────────────────
# customtkinter 使用了 __import__ / importlib 延迟加载某些模块
HIDDEN_IMPORTS = [
    "customtkinter",
    "customtkinter.windows.widgets",
    "customtkinter.windows.widgets.theme",
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
    "serial",
    "serial.tools",
    "serial.tools.list_ports",
    "serial.tools.list_ports_common",
    "serial.tools.list_ports_windows",
    "queue",
    "ctypes",
    "ctypes.wintypes",
    "logging",
    "logging.handlers",
    "tomllib",
]

# ── 数据文件 ──────────────────────────────────────────────
# 配置文件不打入 exe 内部，而是放在 exe 同目录，方便用户编辑
# 下面的 datas 只在 --onedir 模式生效，--onefile 时文件会打入 exe 内部
# settings.py 在 frozen 模式下会从 sys.executable.parent 读取
DATAS = []

# ── 排除模块 ──────────────────────────────────────────────
# 减少 exe 体积（这些模块未被项目使用）
EXCLUDES = [
    "tkinter.test",
    "matplotlib",
    "numpy",
    "scipy",
    "pandas",
    "PIL.ImageQt",
    "PIL.ImageShow",
    "pytest",
    "hypothesis",
    "setuptools",
    "pip",
    "wheel",
]

a = Analysis(
    ["run.py"],
    pathex=["src"],
    binaries=[],
    datas=DATAS,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="fwasset",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # GUI 应用，不显示命令行窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="x86_64",
    codesign_identity=None,
    entitlements_file=None,
    icon=None,               # TODO: 添加 .ico 图标路径
)
