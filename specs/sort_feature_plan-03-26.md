# 排序功能规划

## 1. 架构设计——三层分离

排序逻辑与 UI 完全解耦

- 数据层（已有）
  - `core/file_scan.py`
  - 返回原始 folders 列表
  - 删除末尾 `results.sort(key=lambda x: x["path"])`
- 排序层（新建）
  - `core/sort_config.py`
  - `SortKey` 枚举 + 排序函数
  - `apply_sort(folders, keys, ascending)` 纯函数
- UI 层（`app.py`）
  - 持有 `self.sort_key` / `self.sort_asc`
  - 搜索 + 排序串联 `_apply_filter_and_sort()` 渲染列表

> 排序函数放在 `core/` 下而不是 `app.py`，便于单元测试和替换 UI 框架（CTK/PyQt）时复用。

---

## 2. 排序维度规划

当前 3 个 + 预留扩展槽

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

### 可扩展（未来）
- 按测试状态
  - key: `status_map`
  - 排序：待确认 > 通过 > 未操作
  - 需在扫描时注入状态字段
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

搜索框旁边添加排序控件

- 排序按钮组：`文件夹名` / `型号` / `版本号`
- 升/降序：`▲ 升序` / `▼ 降序`
- 操作规则：
  1. 点击当前选中按钮，切换升/降序
  2. 点击其他按钮，切换排序键并重置为升序
- 搜索/排序链：`_apply_filter_and_sort()`
- 交互扩展点：当前排序键高亮、值修改即渲染
- 状态保持：`_scan()` 后应用当前排序配置

---

## 4. 具体改动文件清单

共 3 个文件，`core/` 只新增不改动其他文件

- 新建
  - `core/sort_config.py`
    - `SortKey` 枚举（`MODEL`, `VERSION`, `FOLDER_NAME`）
    - `sort_key_func(key)` 返回排序 key lambda
    - `apply_sort(folders, keys, ascending)` 纯函数
- 修改
  - `core/file_scan.py`
    - 删除 `results.sort(key=lambda x: x['path'])`
    - 返回未排序原始列表（由上层排序）
  - `app.py`
    - 新增状态变量：`self.sort_key`, `self.sort_asc`
    - 新增 `_apply_filter_and_sort()`：过滤 + 排序 + 渲染
    - 在左侧面板添加排序按钮组
    - `scan` 完成后调用 `_apply_filter_and_sort()` 而不是直接渲染
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
