# 排序功能规划

## 1. 架构设计——三层分离

排序逻辑与 UI 完全解耦

- 数据层（已有）
  - `core/file_scan.py`
  - 保留默认路径排序（确保扫描结果稳定）
- 排序层（新建）
  - `core/sort_config.py`
  - `SortKey` 枚举 + 排序函数
  - `apply_sort(folders, sort_key, ascending)` 纯函数
- UI 层（`app.py`）
  - 持有 `self.folder_sort_key_var` / `self.folder_sort_order_var` / `self.folder_status_filter_var`
  - 搜索 + 状态筛选 + 排序串联 `_filter_folder_list()` 渲染列表

> 排序函数放在 `core/` 下而不是 `app.py`，便于单元测试和替换 UI 框架（CTK/PyQt）时复用。

---

## 2. 排序维度规划

当前 4 个（需求内）+ 预留扩展槽

### V1 上线（必须实现）
- 按型号
  - key: `model`
  - 自然排序：`L30 → L36 → L50`
  - 数字部分做数值比较
- 按版本号
  - key: `version`
  - 语义版本比较：`V1.2 < V10.0`
  - 拆成 `tuple(int)` 比较
- 按文件夹名
  - key: `Path(path).name`
  - 字母序，忽略大小写
  - 还原原始默认路径排序
- 按测试状态
  - key: `status_map[(MODEL, VERSION)]`
  - 排序：待确认 > 测试通过 > 未操作
  - 备注含扩展文本时按前缀归一化（如 `测试通过 | xxx`）

### 可扩展（未来）
- 按修改时间
  - key: `mtime`
  - 文件夹最新修改时间
  - 需在扫描时读取元数据
- 自定义多键
  - key: `List[SortKey]`
  - 例如：先型号再版本
  - 传 `keys` 列表即可

---

## 3. UI 交互设计

搜索框下方添加状态筛选与排序控件

- 状态筛选：`全部状态` / `待确认` / `测试通过` / `未操作`
- 排序维度：`文件夹名` / `型号` / `版本号` / `测试状态`
- 排序方向：`升序` / `降序`
- 搜索/筛选/排序链：`_filter_folder_list()`
- 状态保持：`_scan()` 后应用当前筛选与排序配置

---

## 4. 具体改动文件清单

共 2 个文件

- 新建
  - `core/sort_config.py`
    - `SortKey` 枚举（`PATH`, `MODEL`, `VERSION`, `STATUS`）
    - `apply_sort(folders, sort_key, ascending, status_map)` 纯函数
- 修改
  - `app.py`
    - 新增状态变量：关键字、状态筛选、排序键、升降序
    - 扩展 `_filter_folder_list()`：关键字过滤 + 状态过滤 + 排序 + 渲染
    - 在左侧面板添加状态筛选与排序控件
    - 写表/审核/一键更新后，按 `(MODEL, VERSION)` 更新状态并自动重算列表
- 不动
  - `core/services/` 下所有逻辑（不关心排序）

---

## 5. 可扩展性设计要点

- 枚举驱动：新增排序维度只需 `SortKey` 增项 + `sort_key_func` case
- 多键排序：`apply_sort(folders, keys: list[SortKey], ascending: bool)`
  - 目前用单 key 包装列表，未来支持 `[MODEL, VERSION]` 二级排序
- 状态维度：`_scan()` 时填状态字段，排序函数读字段即可
- 持久化：`config.toml` `[ui]` 保存 `sort_key` + `sort_asc`，`settings.py` TOML 读写可复用

> 核心原则：`SortKey` 是唯一扩展点，新增维度不改 UI 布局，仅改 `core/sort_config.py`。
