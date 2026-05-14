# fwasset — 按摩椅固件资产管理平台

用于按摩椅固件程序资产的搜索、定位、工具启动、刷机自动化与运行日志管理的桌面应用。基于 Python (CustomTkinter) 构建，支持 20 种固件类型的智能识别与多种烧录模式。

## 主要功能

### 资产发现与动态分类
- 基于 `firmware_catalog.toml` 注册表扫描固件根目录，按目录关键字和文件后缀自动匹配固件类型。
- 支持 20 种固件类型：主板、断码屏手控、手控 UI、蓝牙、音乐文件、语音、快捷键、3D/2D 机芯板、旋钮开关、腿部、膝盖机、音波板、健康检测、商用主板、占座提醒、刷卡机、乐摇摇、三合一蓝牙版、老化程序。
- 从文件名和目录路径中自动提取产品型号与版本号，支持正则可配置。
- 资产数据持久化到 SQLite 索引库 (`fwasset.db`)，支持增量扫描与缓存加载。

### 多模式刷机流程
- **USB 自动刷写 (`auto_usb`)**：支持配对文件模式（ROM+PKG）和音乐文件整目录拷贝模式，集成 U 盘插入检测、垃圾文件清理、自动拷贝与校验。
- **外部工具拉起 (`tool_launch`)**：自动发现 `tool_root` 下的烧录工具（`.exe`/`.bat`），支持模糊匹配与收藏/最近使用追踪。
- **文档说明 (`manual_doc`)**：对无需烧录工具的固件类型提供操作说明。

### U 盘诊断与修复
- U 盘插入自动健康检查（文件系统错误、垃圾文件识别）。
- 一键清理垃圾文件（可配置扩展名与文件名）。
- FAT32 格式化、安全弹出。
- Windows 驱动修复（`chkdsk` / `pnputil`）。

### 工具中心
- 独立的工具管理窗口，查看所有已发现的外部烧录工具。
- 支持按固件类型筛选、使用频率追踪、快速启动。

### 系统诊断
- 一键导出诊断包（ZIP），包含脱敏后的配置文件、应用日志、运行状态快照，方便线上排查。
- 应用内嵌日志查看面板，实时滚动显示运行日志。

### 用户体验
- 左侧资产树按 系列 → 型号 → 资产 三级分组，支持自然排序。
- 关键字搜索、固件类型筛选、隐藏已刷资产。
- 支持亮色/暗色主题切换。

## 项目架构

```
core/                        # 业务逻辑层（无 UI 依赖）
├── settings.py              # TOML 配置加载、路径解析、默认值
├── firmware_catalog.py      # 固件类型注册表解析
├── file_scan.py             # 目录扫描、类型匹配、型号/版本提取
├── asset_index.py           # SQLite 资产索引（CRUD、查询、隐藏）
├── asset_helpers.py         # 资产属性辅助（usb_flow、ROM/PKG 文件）
├── tool_discovery.py        # 工具路径自动发现（模糊匹配）
├── tool_usage.py            # 工具收藏/最近使用追踪（JSON）
├── usb_ops.py               # USB 底层操作（检测、清理、拷贝、格式化、弹出、修复）
├── diagnostics.py           # 诊断包构建（ZIP）
├── logging_utils.py         # 线程安全文件日志
├── sort_config.py           # 自然排序
└── services/                # 服务编排层
    ├── scan_service.py      # 扫描 → 入库 → 缓存加载
    ├── flash_service.py     # 一键 USB 刷写流程
    ├── music_flash_service.py  # 音乐文件整目录刷写
    └── usb_repair_service.py   # USB 健康诊断与驱动修复

ui/                          # GUI 层（CustomTkinter）
├── shell.py                 # 主窗口
├── base_panel.py            # 基类面板（任务队列、轮询、USB 选择、日志）
├── firmware_list_panel.py   # 主面板（侧边栏、详情、操作区）
├── tool_center_panel.py     # 工具中心窗口
├── asset_tree.py            # 资产树组件
├── design_tokens.py         # 设计系统（颜色/字体，亮暗主题）
├── shared_widgets.py        # 可复用组件
├── operation_panels/        # 操作面板（注册模式，按 flash_mode 动态加载）
│   ├── registry.py          # @register 装饰器 + get_panel() 查找
│   ├── host_types.py        # PanelHost Protocol（依赖倒置）
│   ├── auto_usb_panel.py    # USB 刷写面板
│   ├── tool_launch_panel.py # 外部工具启动面板
│   ├── manual_doc_panel.py  # 文档说明面板
│   ├── disabled_panel.py    # 禁用类型占位
│   └── shared_actions.py    # 通用按钮操作
└── view_models/             # 视图模型
    ├── asset_filter_model.py   # 筛选、排序、分组
    ├── asset_selection_model.py # 选择状态与隐藏项追踪
    └── tree_expansion_model.py  # 树节点展开/折叠状态
```

### 关键设计模式

- **Panel Registry**：操作面板通过 `@register("flash_mode")` 装饰器注册，主面板按固件类型的 `flash_mode` 动态加载对应面板，共 4 种面板实现。
- **PanelHost Protocol**：操作面板依赖 `PanelHost` 协议而非具体类，实现依赖倒置，便于单独测试。
- **后台任务队列**：耗时操作在守护线程中执行，通过 `queue.Queue` + 120ms 定时轮询将结果投递回 UI 线程，避免界面卡顿。
- **SQLite 索引**：资产扫描结果持久化到 `fwasset.db`，支持增量扫描与跨启动缓存。数据库含 schema 版本迁移机制。

## 安装与运行

本项目使用 `uv` 管理依赖与虚拟环境：

```powershell
# 克隆仓库
git clone <repo-url>
cd firmware-flash-automation

# 同步依赖（含开发与测试库）
uv sync --extra dev

# 运行应用（开发模式）
uv run fwasset

# 或直接运行
.\.venv\Scripts\python.exe run.py
```

### 打包为 exe

```powershell
uv run pyinstaller fwasset.spec
```

## 配置说明

系统行为由项目根目录下的 TOML 文件控制。首次运行前先复制样例配置：

```powershell
Copy-Item config.example.toml config.toml
```

然后按本机环境填写 `config.toml` 中的 `paths.root_dir`（固件根目录路径）和 `paths.tool_root`（外部烧录工具目录路径）。

> `config.toml` 是本机运行配置，已在 `.gitignore` 中排除；`firmware_catalog.toml` 是项目级固件类型注册表，随代码版本管理。

### `config.toml` 配置段

| 配置段 | 说明 |
|---|---|
| `paths.root_dir` | 固件根目录默认路径 |
| `paths.tool_root` | 外部烧录工具所在目录 |
| `usb.junk_extensions` | U 盘垃圾文件扩展名列表 |
| `usb.junk_filenames` | U 盘垃圾文件名列表 |
| `usb.auto_diagnose_on_insert` | 插入 U 盘时自动诊断 |
| `usb.health_check_interval_sec` | U 盘健康检查间隔（秒） |
| `scan.rom_extensions` / `scan.pkg_extensions` | ROM/PKG 文件扩展名 |
| `scan.exclude_dir_keywords` | 扫描排除的目录关键字 |
| `scan.model_patterns` | 从文件名提取型号的正则列表 |
| `scan.version_patterns` | 从文件名提取版本号的正则列表 |
| `scan.path_model_patterns` | 从路径提取型号的正则列表 |
| `scan.path_version_patterns` | 从路径提取版本号的正则列表 |
| `music.default_source_dir` | 音乐固件默认源目录 |

### `firmware_catalog.toml` — 固件类型注册表

每个固件类型包含以下字段：

| 字段 | 说明 |
|---|---|
| `key` | 类型标识符 |
| `label` | 中文显示名 |
| `dir_keywords` | 匹配目录关键字列表 |
| `file_extensions` | 匹配文件后缀列表 |
| `flash_mode` | 烧录模式：`auto_usb` / `tool_launch` / `manual_doc` / `disabled` |
| `usb_flow` | USB 模式子类型：`paired_files`（ROM+PKG 配对）或 `directory_copy`（整目录拷贝） |
| `tool_name` | 关联的外部工具名称 |
| `tool_dir` | 工具所在子目录（相对于 `tool_root`） |
| `enabled` | 是否启用该类型 |

## 烧录模式

| 模式 | 说明 | 适用固件 |
|---|---|---|
| `auto_usb` | 自动检测 U 盘，拷贝固件文件后弹出，用户插入设备完成刷写 | 手控 UI、断码屏手控、音乐文件 |
| `tool_launch` | 自动发现并拉起外部烧录工具（如 ISP 工具） | 主板、语音、快捷键、机芯板等 |
| `manual_doc` | 展示操作说明文档，不执行自动化 | 占座提醒 |
| `disabled` | 该类型暂不提供操作 | 老化程序 |

## 运行时目录

运行时生成的数据（索引库、日志等）默认写入以下位置：

| 运行模式 | 默认路径 |
|---|---|
| 开发模式 (`uv run`) | 项目根目录 `.runtime/` |
| 打包 exe | exe 同级目录 `runtime/` |

可通过环境变量 `FWASSET_RUNTIME_DIR` 自定义路径（支持绝对路径或相对于应用根目录的路径）。

目录内容：
- `fwasset.db` — SQLite 资产索引数据库
- `logs/app.log` — 应用运行日志

## 测试

```powershell
# 运行全部测试（含覆盖率报告，阈值 80%）
.\scripts\test.ps1

# 跳过 UI 相关测试（无桌面环境时）
uv run pytest -m "not ui" -q

# 仅运行核心逻辑测试
uv run pytest tests/core/ -q
```

测试框架：pytest + pytest-cov + hypothesis。UI 测试标记为 `@pytest.mark.ui`，在 CI 或 headless 环境中可通过 `-m "not ui"` 跳过。

## 技术栈

- **Python** >= 3.8
- **CustomTkinter** — 现代 Tkinter GUI 框架
- **psutil** — U 盘/磁盘分区检测
- **openpyxl** — Excel 读写
- **SQLite** — 资产索引持久化
- **uv** — 依赖与虚拟环境管理
