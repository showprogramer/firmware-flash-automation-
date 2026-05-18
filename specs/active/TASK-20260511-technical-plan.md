# fwasset 技术债务与演进路线图

> 文档版本：v1.0  
> 最后更新：2026-05

---
## 文档说明

本文档记录当前架构的已知问题、风险等级、建议改造方向，以及优先级排序。
目标是让任何接手成员都能快速理解"现在哪里痛、为什么痛、下一步怎么动"。

分类标记说明：

- 🔴 **高优先级** — 已影响可维护性或存在明确扩展阻塞
- 🟡 **中优先级** — 短期可接受，中期需解决
- 🟢 **低优先级** — 现阶段稳定，未来有需求时再处理
- 💡 **架构机会** — 非债务，但是可以主动优化的方向

复杂度标记说明：

- **低复杂度** — 单模块或小范围改动，接口影响小，回归范围可控
- **中复杂度** — 跨 UI / core / tests 多处改动，需要兼容现有行为
- **高复杂度** — 涉及核心流程、文件系统、索引或多模块状态一致性，需要分阶段实施和人工验证

---

## Issue 1 🔴 FirmwareListPanel — God Object

**文件：** `src/fwasset/ui/firmware_list_panel.py`  
**行数参考：** 第 43 行 class 定义起，全文约 1000+ 行

### 现象

单个类同时承担以下职责：

- UI 布局（侧边栏、详情卡、操作区、日志区）
- 资产筛选与排序
- 树形分组逻辑
- 选中状态管理
- 隐藏条目管理
- 扫描触发与回调
- 工具发现与启动
- USB 刷机操作区渲染
- 串口操作区装配
- 剪贴板操作与目录打开

### 风险

- 任何新功能（新 flash_mode、新筛选维度、新操作区）都必须修改同一个大类
- UI 改动与业务逻辑改动相互牵连，回归测试范围难以收窄
- 单元测试几乎无法覆盖（UI 依赖导致所有逻辑都无法独立测试）

### 建议拆分方向

```
FirmwareListPanel（只做装配和事件路由）
├── AssetFilterModel        # 筛选/排序/分组逻辑（纯 Python，可单元测试）
├── AssetSelectionModel     # 选中状态、隐藏状态
├── SidebarPanel            # 左侧树形列表区
├── DetailPanel             # 右侧资源详情卡
├── OperationPanelFactory   # flash_mode → 操作面板的注册表（见 Issue 5）
└── LogPanel                # 日志区（已相对独立，易拆）
```

### 行动项

- [x] 新建 `src/fwasset/ui/view_models/asset_filter_model.py`，将筛选查询、排序键选择、树形分组和可见叶子计算迁移进去
- [x] 新建 `src/fwasset/ui/view_models/asset_selection_model.py`，封装 `_selected_idx`、隐藏条目相关方法
- [x] 新建 `src/fwasset/ui/view_models/tree_expansion_model.py`，封装 `_tree_expanded` 树展开状态管理
- [x] 新建 `src/fwasset/core/asset_helpers.py`，将 `_asset_usb_flow`、`_asset_rom_pkg_files`、`_asset_path_text`、`_primary_file_path_text` 提取为独立可测试的纯函数
- [x] 新建 `src/fwasset/ui/operation_panels/host_types.py`，定义 `PanelHost` Protocol，规范化操作面板与宿主面板之间的接口契约
- [x] 将 `_make_bool_var` 提取到 `src/fwasset/ui/shared_widgets.py`，公共组件复用
- [x] `AutoUsbPanel` 改用独立函数 `asset_usb_flow`/`asset_rom_pkg_files`/`make_bool_var`，减少 `panel_host` 依赖面
- [x] `FirmwareListPanel._asset_usb_flow` 等方法改为委托到 `asset_helpers` 模块
- [x] 树展开状态从 `self._tree_expanded` 迁移到 `self._tree_expansion = TreeExpansionModel()`
- [x] 新建 `src/fwasset/ui/panels/log_panel.py`，将日志区拆分为 `LogPanel`
- [x] 新建 `src/fwasset/ui/panels/sidebar_panel.py`，将左侧搜索、类型筛选、扫描按钮和资源树装配拆分为 `SidebarPanel`
- [~] FirmwareListPanel 保留为装配器，筛选/排序/树分组已委托给 AssetFilterModel，选中状态与隐藏判定已委托给 AssetSelectionModel，树展开状态已委托给 TreeExpansionModel，操作面板已通过 PanelHost Protocol 解耦；左侧栏和日志区已拆分为独立 Panel

**预估工作量：** 3～5 天（可分批渐进迁移，不需要一次重写）

### 当前状态

第三阶段已完成。`FirmwareListPanel` 的纯业务逻辑已提取为独立可测试函数（`asset_usb_flow`、`asset_rom_pkg_files`、`asset_dir_path`、`asset_primary_file_path`）；树展开状态管理已提取为 `TreeExpansionModel`；操作面板通过 `PanelHost` Protocol 与宿主解耦，`AutoUsbPanel` 直接调用 `asset_helpers` 而非 `panel_host` 方法；`make_bool_var` 提取为公共组件；日志区已拆分为 `src/fwasset/ui/panels/log_panel.py`；左侧搜索、类型筛选、扫描按钮和资源树装配已拆分为 `src/fwasset/ui/panels/sidebar_panel.py`。

---

## Issue 2 🔴 SQLite 只作缓存，筛选仍走内存全量

**文件：** `src/fwasset/ui/firmware_list_panel.py` 第 557 行 `_filter_assets()`  
**对比：** `src/fwasset/core/asset_index.py` 中 `query_assets()` 已有完整 SQL 查询

### 现象

```python
# 当前做法：全量加载 → 内存过滤
for item in self._all_assets:
    if keyword not in haystack:
        continue
```

`query_assets()` 已经支持关键词过滤和 firmware_type 过滤，但 UI 层没有使用它，
而是每次键盘输入都重新遍历完整列表并重建树。

### 风险

- 资产条目达到千级时，每次搜索触发的内存遍历 + 树重建会造成 UI 卡顿
- `self._all_assets` 常驻内存，数据量大时内存占用不可控
- SQLite 的索引（`idx_assets_type`、`idx_assets_model`）形同虚设

### 建议改造

```python
# 目标做法：筛选下推到 SQLite
def _filter_assets(self):
    keyword = self.search_var.get().strip()
    selected_types = list(self._selected_types())
    self.assets = query_assets(keyword=keyword, firmware_types=selected_types)
    self._render_asset_tree()
```

同时废弃 `self._all_assets`，启动时不再全量加载，改为按需查询。

### 行动项

- [x] 将 `_filter_assets()` 改为调用 `query_assets()`
- [x] 移除 `self._all_assets` 全量缓存，改用 `_has_index_assets` 维护空状态提示
- [x] 确认 `query_assets()` 的排序参数支持 SortKey 枚举
- [x] 为 `query_assets()` 补充 `sort_key` 和 `ascending` 参数

### 当前状态

已完成。筛选、类型过滤和排序下推到 SQLite 查询入口；隐藏条目仍在 UI 层按现有规则过滤，保持右键恢复能力不变。

**预估工作量：** 1 天

---

## Issue 3 🟡 扫描引擎缺少增量策略

**文件：** `src/fwasset/core/file_scan.py` 第 103 行 `scan_firmware_assets()`

### 现象

每次"扫描根目录"都是完整的 `os.walk` 全量遍历，无任何跳过机制。

### 风险场景

| 根目录类型 | 预计影响 |
|---|---|
| 本地 SSD | 当前无感知 |
| 本地机械盘 | 目录多时明显变慢 |
| 公司 NAS / 共享盘 | 网络 IO，可能需要数分钟 |
| 云盘同步目录 | 可能触发大量网络请求 |

### 缺失的机制

1. **mtime 跳过**：对比目录的 `st_mtime` 与上次扫描时间，未变更则跳过
2. **按型号目录刷新**：只重扫指定的一个型号目录，而不是整棵树
3. **目录变更检测**：监听文件系统事件（`watchdog` 库）
4. **扫描取消**：长时间扫描时用户无法中断
5. **扫描进度**：只有完成没有进度百分比

### 建议行动项

- [ ] 在 `scan_firmware_assets()` 中加入 mtime 比对逻辑（与 `scan_meta` 表对比）
- [ ] 新增 `scan_single_directory(model_dir: str)` 函数，支持局部刷新
- [x] `_run_task` 扫描任务加入 `cancel_event: threading.Event` 参数
- [x] UI 扫描按钮在扫描中变为"取消"状态
- [ ] （可选，低优先级）集成 `watchdog` 实现后台自动检测变更

**预估工作量：** mtime 跳过 0.5 天；取消机制 1 天；watchdog 3 天

---

## Issue 4 🟡 配置是 import-time 全局常量，不可运行时重载

**文件：** `src/fwasset/core/settings.py` 第 198 行起

### 现象

```python
# import 时执行，之后不可更改
_cfg, CONFIG_LOAD_STATUS, CONFIG_LOAD_ERROR = load_toml_config(CONFIG_PATH)
DEFAULT_ROOT = str(_cfg_get(_cfg, "paths", "root_dir", ...))
TOOL_ROOT = _resolve_path(...)
```

### 架构代价

- UI 中修改配置（如切换根目录）无法即时生效，需要重启应用
- 单元测试需要 `monkeypatch` 模块级变量，测试隔离困难
- 未来的"配置管理界面"或"多环境配置"方案受阻
- `tool_discovery`、`scan`、`logging` 等模块都隐含依赖 import 顺序

### 建议改造方向

将全局常量收敛为 `Settings` 单例对象：

```python
# 目标
class Settings:
    def __init__(self, config_path: Path): ...
    def reload(self): ...          # UI 保存配置后调用
    
    @property
    def root_dir(self) -> str: ...
    @property
    def tool_root(self) -> str: ...

# 全局单例
settings = Settings(CONFIG_PATH)
```

各模块从 `from fwasset.core.settings import settings` 取值，而不是直接引用常量。

### 行动项

- [ ] 新建 `Settings` 类，封装现有所有全局常量
- [ ] 保留旧常量作为 `settings.xxx` 的别名（向后兼容，渐进迁移）
- [ ] 新增 `settings.reload()` 方法
- [ ] 将 `tool_discovery`、`file_scan` 中对全局常量的直接引用改为 `settings.xxx`

**预估工作量：** 2 天（含兼容层）

---

## Issue 5 ✅ flash_mode 操作区注册表拆分（已完成）

**文件：** `src/fwasset/ui/firmware_list_panel.py` 第 982 行 `_render_operation_panel()`

### 现象

```python
if flash_mode == "auto_usb":
    self._build_auto_usb_ops(asset)
elif flash_mode == "auto_serial":
    ...
elif flash_mode == "tool_launch":
    ...
elif flash_mode == "manual_doc":
    ...
else:
    self._build_disabled_ops(asset)
```

每新增一种烧录方式，必须修改 `FirmwareListPanel`。

### 建议改造：操作面板注册表

```python
# src/fwasset/ui/operation_panels/__init__.py

_REGISTRY: dict[str, type[BaseOperationPanel]] = {}

def register(flash_mode: str):
    def decorator(cls):
        _REGISTRY[flash_mode] = cls
        return cls
    return decorator

def get_panel(flash_mode: str) -> type[BaseOperationPanel]:
    return _REGISTRY.get(flash_mode, DisabledPanel)

# 使用
@register("auto_usb")
class AutoUsbPanel(BaseOperationPanel): ...

@register("tool_launch")
class ToolLaunchPanel(BaseOperationPanel): ...
```

`FirmwareListPanel` 的 `_render_operation_panel()` 简化为：

```python
def _render_operation_panel(self, asset):
    PanelClass = get_panel(asset.get("flash_mode", ""))
    panel = PanelClass(self.ops_body, asset=asset, log_fn=self._log)
    panel.pack(fill="both", expand=True)
```

### 行动项

- [x] 新建 `src/fwasset/ui/operation_panels/` 目录
- [x] 定义 `BaseOperationPanel(ctk.CTkFrame)` 基类，规范接口
- [x] 将现有五个 `_build_xxx_ops()` 方法迁移为独立 Panel 类（AutoUsbPanel、AutoSerialPanel、ToolLaunchPanel、ManualDocPanel、DisabledPanel）
- [x] 实现注册表机制（`register` / `get_panel`）
- [x] FirmwareListPanel 中 `_render_operation_panel()` 改为调用注册表
- [x] 新增 `tests/test_operation_panels.py` 覆盖注册表与 Panel smoke test

**预估工作量：** 2 天

---

## Issue 6 🟢 catalog 匹配是启发式，缺少可解释性与冲突检测

**文件：** `src/fwasset/core/file_scan.py` 第 57 行 `_match_catalog_type()`

### 现象

匹配逻辑依赖关键词列表 + 文件扩展名 + 顺序优先：

```python
for cfg in type_configs:
    keywords = [...]
    if keywords and not any(keyword in part ...):
        continue
    if not _files_match_extensions(filenames, cfg.get("file_extensions", [])):
        continue
    return cfg   # 第一个匹配的就用，不检测多重命中
```

### 风险

- 关键词重叠时，结果依赖 `firmware_catalog.toml` 中的定义顺序（隐式优先级）
- 同一目录包含多种固件类型的文件时，只返回第一个匹配，其余被静默丢弃
- 排除词（`旧`、`照片` 等）会持续补丁式增长，无法系统管理
- 非开发人员维护 `firmware_catalog.toml` 时，无法知道"为什么这个目录被识别成了 X 类型"

### 建议改造方向

1. **返回匹配报告而非单一结果**：`_match_catalog_type()` 返回所有命中的类型及命中原因
2. **冲突检测**：多个类型同时命中时，记录警告而不是静默选第一个
3. **可解释结果**：在 UI 的资源详情区增加"匹配依据"字段，方便排查误判

### 行动项

- [ ] `_match_catalog_type()` 改为返回 `list[dict]`（所有命中），调用方处理多命中情况
- [ ] 扫描完成后，将多命中警告记录到日志
- [ ] （可选）UI 详情面板增加"匹配依据"只读字段

**预估工作量：** 1.5 天

---

## 补充：本次讨论新增发现

### Issue 7 🟡 固件资产 CRUD 能力缺失

**背景：** 当前工具只展示扫描结果，员工无法在 UI 内直接管理固件文件，必须手动切回资源管理器操作。

需要支持的三种操作：

| 操作 | 描述 | 示例 |
|---|---|---|
| 修改（Update） | 重命名固件版本文件名 | `v1.0.bin` → `v1.0_20260511.bin` |
| 新增（Create） | 新建型号目录或添加程序文件 | 新建 `L36-DX/主板程序/`，或放入新版本 `.mot` |
| 删除（Delete） | 删除过期/错误的程序文件或空目录 | 删除测试版固件 `v0.9_old.bin` |

这些操作需要同时更新文件系统 + 刷新 SQLite 索引 + 刷新 UI 树表，保证三者一致。

### 行动项

- [ ] 新建 `src/fwasset/core/asset_crud.py`，封装文件系统操作（rename / create dir / create file / delete）与对应的索引更新
- [ ] 每次 CRUD 操作后自动触发 `query_assets()` 刷新和 Treeview 重载
- [ ] 右键菜单增加"重命名"、"删除程序"选项（型号目录和固件类型节点的删除需警告确认）
- [ ] 工具栏增加"新建型号目录"入口
- [ ] 所有写操作记录操作日志

**预估工作量：** CRUD 核心逻辑 1.5 天；UI 右键/工具栏接入 1 天；日志与确认弹窗 0.5 天

---

### Issue 8 🟢 日志系统是单文件追加写，无轮转无结构化

**文件：** `src/fwasset/core/logging_utils.py`

当前实现是简单的文件追加写入，长期运行后日志文件会无限增长，且无法按模块、级别过滤。

### 行动项（低优先级，有需求时再做）

- [ ] 接入 Python 标准库 `logging` 模块，替换 `FileLogger`
- [ ] 配置 `RotatingFileHandler`（按大小轮转）
- [ ] UI 日志区改为订阅 logging handler，而不是直接传 `log_fn` 回调

---

## 优先级汇总与建议执行顺序

| # | Issue | 优先级 | 复杂度 | 建议时机 | 预估工时 |
|---|---|---|---|---|---|
| 2 | SQLite 查询替换内存过滤 | 🔴 高 | 低复杂度 | 立即 | 1 天 |
| 1 | FirmwareListPanel 拆分（ViewModel 层） | 🔴 高 | 高复杂度 | 下个迭代开始 | 3～5 天 |
| 5 | flash_mode 操作面板注册表 | 🟡 中 | 中复杂度 | 拆分 Issue 1 时同步做 | 2 天 |
| 7 | 固件资产 CRUD（文件系统增删改，同步索引+UI） | 🟡 中 | 高复杂度 | 有增删改需求时 | 3 天 |
| 4 | Settings 对象化 | 🟡 中 | 中复杂度 | 有配置界面需求时 | 2 天 |
| 3 | 增量扫描（mtime + 取消） | 🟡 中 | 中复杂度 | 出现慢扫描投诉时 | 1.5 天 |
| 6 | catalog 匹配可解释化 | 🟢 低 | 中复杂度 | 有误判投诉时 | 1.5 天 |
| 8 | 日志轮转与结构化 | 🟢 低 | 低复杂度 | 运维阶段 | 1 天 |

**建议第一步：先做 Issue 2（1 天），改动小、收益直接、风险低，同时为 Issue 1 的拆分铺路。**

---

## 不建议做的事（当前阶段）

- ❌ 引入 Flask / FastAPI 等 Web 框架——这是桌面工具，无多用户并发需求
- ❌ 整体重写——现有架构分层清晰，渐进迁移风险更低
- ❌ 引入 ORM（SQLAlchemy 等）——当前 SQLite 使用量不大，原生 sqlite3 已够用

---

*本文档应随每次架构决策同步更新。*
---

## 2026-05-14 修复记录：Issue 3 扫描取消与索引安全

- 已完成扫描取消基础链路：UI 扫描按钮增加调度入口，扫描中点击不再打开目录选择器，而是触发现有扫描任务取消。
- 已修复取消事件竞态：后台扫描任务固定捕获本次扫描创建的 `cancel_event`，不再从可变面板属性读取。
- 暂不启用 `scan_meta.last_scan_at` 下推：当前索引保存仍是全表替换，增量跳过会造成未变化资产丢失；后续若要做 mtime 增量扫描，必须先实现旧索引与本次变更结果的合并策略。
- 验证：`uv run python -m pytest tests\test_file_scan.py tests\test_scan_service.py tests\test_app_service_smoke.py -q --no-cov`，66 passed。

---

## 2026-05-16 更新记录：Issue 1 扫描状态模型拆分

- Issue 1 继续推进：新增 `ScanStateModel`，将扫描开始、取消请求、完成清理从 `FirmwareListPanel` 中提取为可单测的 ViewModel。
- `FirmwareListPanel` 仍保留 `_scan_cancel_event` 兼容层，当前测试和潜在外部调用无需同步大改；后续可在确认无依赖后删除兼容属性。
- Issue 3 已完成的扫描取消链路保持不变：扫描中再次点击按钮触发取消，不打开目录选择器；后台任务继续捕获本次扫描创建的 `cancel_event`。
- 当前自动化验证：`uv run python -m pytest tests\test_scan_state_model.py tests\test_app_service_smoke.py -q --no-cov`，22 passed。

---

## 2026-05-18 更新记录：Issue 1 SidebarPanel 拆分

- Issue 1 继续推进：新增 `SidebarPanel`，将左侧搜索框、类型快速筛选、排序菜单、隐藏开关、扫描按钮和 `AssetTreeView` 装配从 `FirmwareListPanel` 中拆出。
- `FirmwareListPanel._build_sidebar()` 现在只负责创建 `SidebarPanel` 并接回 `scan_btn`、`type_quick_menu`、`sort_menu`、`asset_tree` 兼容属性，现有调用路径保持不变。
- 同步 Issue 3 清单状态：扫描取消事件和扫描中按钮状态已完成；mtime 跳过与局部刷新仍待后续处理。
- 当前自动化验证：`uv run python -m pytest tests\test_sidebar_panel.py tests\test_app_service_smoke.py -q --no-cov`，18 passed。
