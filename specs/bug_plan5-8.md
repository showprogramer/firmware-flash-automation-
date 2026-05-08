# bug_plan5-8: 固件扫描引擎问题修复

> 状态: 已完成
> 创建: 2026-05-08
> 完成: 2026-05-08
> 来源: YJ-按摩椅家用/商用程序汇总 目录深度分析

---

## 背景

对 `YJ-按摩椅家用，商用程序汇总` 目录（58个产品目录、797个子目录、2011个文件）进行深度分析后，发现固件扫描引擎存在若干匹配失败和分类冲突的问题。

---

## P0-1: ROM文件名空格分隔导致版本号丢失

**严重度:** P0
**影响文件:** `config.toml` [scan] version_patterns, `settings.py` _DEFAULTS
**相关代码:** `file_scan.py:162-171` parse_rom_filename()

### 问题描述

ROM 文件名 `ITE_NOR 120.3.1.ROM` 中，`ITE_NOR` 与版本号 `120.3.1` 之间使用**空格**分隔而非下划线。

现有全部 5 个 `version_patterns` 都要求版本号前有 `_` 或 `V`/`v` 前缀：

| 模式 | 正则 | 匹配 `120.3.1`? |
|------|------|:---:|
| 1 | `[Vv](\d+\.\d+(?:\.\d+)?(?:_\d+)?)` | 无 V 前缀 |
| 2 | `_(\d+\.\d+(?:\.\d+)?(?:_\d+)?)$` | 无 `_` 前缀 |
| 3 | `_UI_(\d+\.\d+(?:\.\d+)?(?:_\d+)?)` | 无 `_UI_` |
| 4 | `_(\d+\.\d+\.\d+(?:_\d+))$` | 无 `_` 前缀 |
| 5 | `_(\d+\.\d+\.\d+(?:_\d+)?)$` | 无 `_` 前缀 |

### 失败链路

```
parse_rom_filename("ITE_NOR 120.3.1.ROM")
  → stem = "ITE_NOR 120.3.1"
  → model patterns: 需要 L 前缀 → 无匹配 → model = ""
  → version patterns: 需要 _ 或 V 前缀 → 全不匹配 → version = ""
  → 返回 ("", "")

_extract_model_version() 回退到路径猜测:
  guess_model_from_path("...\手控") → "L36" ✓ (从父目录匹配)
  guess_version_from_path("...\手控") → "" ✗ (手控不含版本号)

最终: 型号=L36, 版本="" → 版本号 120.3.1 完全丢失
```

### 受影响文件

当前仅 1 个文件: `L36  以色列家用定制（蓝牙RoyaI Z9）\手控\ITE_NOR 120.3.1.ROM`

### 修复方案

在 `version_patterns` 末尾增加无前缀三部分版本号模式：

```toml
"(?<![0-9A-Za-z])(\\d+\\.\\d+\\.\\d+(?:_\\d+)?)(?![0-9A-Za-z])"
```

> **注意**: 初始方案用 `\\b` 是**错误的**，因为 `_` 在正则中属于 `\\w`（单词字符）。`\\b` 不会在 `_` 和数字之间匹配，所以 `NULLLOG_16.3.7_FY` 中的 `16.3.7` 无法被 `\\b` 捕获。正确做法是用 `(?<![0-9A-Za-z])` / `(?![0-9A-Za-z])` 明确排除字母数字，使 `_` 成为有效边界。

`\b` 确保 `120.3.1` 前面是空格，不会误匹配 `V120.3.1`。

---

## P0-2: .mot 蓝牙固件完全扫不到

**严重度:** P0
**影响文件:** `firmware_catalog.toml` music_bt.file_extensions, movement_3d.file_extensions, movement_2d.file_extensions
**相关代码:** `file_scan.py:46-54` _files_match_extensions()

### 问题描述

实际的蓝牙板固件全部使用 `.mot` 格式（Renesas R5F104BC 的 Motorola S-record），但 `music_bt` 类型只配置了 `.bin`, `.hex`, `.mp3` 扩展名。

```
实际文件: YJ_Bt_Eng_Massage_R5F104BC_Pro_V15.mot (共 39 个 .mot 蓝牙文件)
catalog:  music_bt.file_extensions = [".bin", ".hex", ".mp3"]
                                    ↑ 缺少 ".mot"
```

同样，3D/2D 机芯板也使用 `.mot` 文件，但 `movement_3d` 和 `movement_2d` 也都缺少 `.mot`。

### 受影响文件

- 39 个蓝牙 `.mot` 文件，分布在 `蓝牙`/`蓝牙板`/`蓝牙程序` 目录中
- 3D/2D 机芯板 `.mot` 文件

### 修复方案

```toml
# music_bt
file_extensions = [".bin", ".hex", ".mp3", ".mot"]

# movement_3d
file_extensions = [".bin", ".hex", ".mot"]

# movement_2d
file_extensions = [".bin", ".hex", ".mot"]
```

由于 `dir_keywords` 不同（`蓝牙` vs `机芯`），不会产生错误分类。

---

## P0-3: handcontrol_ui 劫持所有 ROM+PKG 目录

**严重度:** P0
**影响文件:** `firmware_catalog.toml` (类型顺序), `file_scan.py:57-71` _match_catalog_type()
**相关代码:** `file_scan.py:61-65` ROM+PKG 早期返回

### 问题描述

`_match_catalog_type()` 中 `handcontrol_ui` 有特殊逻辑：只要目录里存在 ROM+PKG 文件就**立即返回**，不检查 `dir_keywords`：

```python
if cfg.get("key") == "handcontrol_ui":
    has_rom = ...
    has_pkg = ...
    if has_rom and has_pkg:
        return cfg  # 立即返回，跳过关键词检查
```

这导致 `segmented_screen`（断码屏手控，排在 catalog 末尾）永远没有匹配机会。任何包含 ROM+PKG 的目录都会被 `handcontrol_ui` 优先匹配。

```
实际场景: L39MAX 断码屏亚克力手控--家用款带语音\手控\*.ROM + *.PKG
  → 匹配为 handcontrol_ui（ROM+PKG 特殊逻辑）
  → 应该匹配 segmented_screen（断码屏手控）
```

### 修复方案

将 `segmented_screen` 移到 `firmware_catalog.toml` 中 `handcontrol_ui` **之前**。因为 `segmented_screen` 的 `dir_keywords` 包含 `["断码屏", "断码屏亚克力手控"]`，在循环中会先匹配：

1. `segmented_screen`（第一个）→ 检查关键词 `断码屏` → 匹配 → 返回
2. `handcontrol_ui`（第二个）→ 仅在 `segmented_screen` 不匹配时才会走到

保留 `handcontrol_ui` 的 ROM+PKG 早期返回作为**兜底**。

---

## P1-4: movement_3d/movement_2d 关键词重叠无法区分

**严重度:** P1
**影响文件:** `firmware_catalog.toml` movement_3d.dir_keywords, movement_2d.dir_keywords

### 问题描述

两个类型共享关键词 `["机芯板", "机芯板程序"]`，当目录名只叫 `机芯板` 时，先配置的 `movement_3d` 总是胜出。

### 修复方案

从两个类型的 `dir_keywords` 中移除共享的泛化关键词 `"机芯板"` 和 `"机芯板程序"`，仅保留带有 3D/2D 标识的关键词：

```toml
# movement_3d
dir_keywords = ["3d机芯", "3d机芯板", "3d机芯机芯板上程序", "机芯板上程序"]

# movement_2d
dir_keywords = ["2d机芯", "2d机芯板", "2d机芯机芯板下程序", "机芯板下程序"]
```

---

## P2-5: commercial_mainboard/card_reader 关键词重叠

**严重度:** P2
**影响文件:** `firmware_catalog.toml` commercial_mainboard.dir_keywords, card_reader.dir_keywords

### 问题描述

两个类型共享关键词 `["投币机", "纸币机"]`，可能产生错误分类。

### 修复方案

从 `commercial_mainboard` 中移除 `"投币机"` 和 `"纸币机"`（这些更偏支付模块，属于 `card_reader` 的职责）：

```toml
# commercial_mainboard
dir_keywords = ["商用主板", "商用一体机程序", "云管家"]

# card_reader
dir_keywords = ["刷卡机", "刷卡机程序", "投币机", "纸币机", "白卡", "白卡程序", "刷卡"]
```

---

## P2-6: 单目录多固件类型混杂

**严重度:** P2
**影响文件:** `file_scan.py:57-71` _match_catalog_type()

### 问题描述

`_match_catalog_type()` 为每个目录只返回一个固件类型，但在实际目录中，某些目录可能混合了多种固件（如商用机目录同时有主板 bin 和刷卡机 hex）。

当前一个目录返回第一个匹配的类型后，其他文件类型会被忽略。

### 修复方案

暂不修复。`os.walk` 按目录遍历，单目录多类型的场景较少。如将来需要，可改为文件粒度匹配。

---

## 补充修复 (第二轮): 下划线分隔子版本 + Treeview 重复 iid 崩溃

### P0-1b: `46_002` / `47_005` 格式版本号无法识别

**根因:** `ITE_NOR_yj_massage_4d_l65_46_002.ROM` 和 `zey_standard_project_l50s_47_005.ROM` 的版本号使用下划线而非点号分隔 `46_002` / `47_005`，所有现有模式都要求 `\d+\.\d+`（必须有点号）。

**修复:** 新增 `_(\d+_\d+(?:_\d+)?)$` 模式，匹配 `_46_002`, `_47_005` 等下划线分隔的版本号。

### P0-7: Treeview `item already exists` 崩溃

**根因:** `asset_tree.py` 的 `_insert_node` 方法在已有同名 iid 时直接 `tree.insert`，导致 Tkinter 抛出 `_tkinter.TclError: Item ... already exists`。在固件类型筛选变化时，`populate()` 的 `clear()` 可能未彻底清理所有子节点，或 `_build_tree_groups` 重复调用产生相同 key。

**修复:** `_insert_node` 插入前检查 `self.tree.exists(iid)`，如已存在则先删除再插入。

### 新增文件
- `asset_tree.py:_insert_node` — 防御性 exists+delete

### 测试新增
- `parse_rom_filename`: `46_002` / `47_005` 格式 → `V46_002` / `V47_005`

---

## 修复进度

| # | 严重度 | 问题 | 状态 |
|---|--------|------|:----:|
| 1 | P0 | ROM 空格分隔版本号丢失 | 已完成 |
| 2 | P0 | .mot 蓝牙固件扫不到 | 已完成 |
| 3 | P0 | handcontrol_ui 劫持 ROM+PKG | 已完成 |
| 4 | P1 | movement_3d/2d 关键词重叠 | 已完成 |
| 5 | P2 | commercial_mainboard/card_reader 关键词重叠 | 已完成 |
| 7 | P0 | Treeview 重复 iid 崩溃 | 已完成 |
| 6 | P2 | 单目录多固件类型混杂 | 暂缓 |

---

## 变更清单

### config.toml
- `[scan] version_patterns` 新增 `"\\b(\\d+\\.\\d+\\.\\d+(?:_\\d+)?)\\b"` 模式

### settings.py
- `_DEFAULTS["scan"]["version_patterns"]` 新增 `r"\b(\d+\.\d+\.\d+(?:_\d+)?)\b"` 模式

### firmware_catalog.toml
- `segmented_screen` 移至 `handcontrol_ui` 之前（第2位）
- `music_bt.file_extensions` 新增 `".mot"`
- `movement_3d.file_extensions` 新增 `".mot"`
- `movement_3d.dir_keywords` 移除 `"机芯板"` / `"机芯板程序"`
- `movement_2d.file_extensions` 新增 `".mot"`
- `movement_2d.dir_keywords` 移除 `"机芯板"` / `"机芯板程序"`
- `commercial_mainboard.dir_keywords` 移除 `"投币机"` / `"纸币机"`

### tests/test_file_scan.py
- 新增 `parse_rom_filename` 参数化用例: `"ITE_NOR 120.3.1.ROM"` → `("", "V120.3.1")`
- 新增 `parse_rom_filename` 参数化用例: `"ITE_NOR_yj_massage__NULL_s_V50.3.6.ROM"` → `("", "V50.3.6")`
- 新增 `parse_rom_filename` 参数化用例: `"NULLLOG_16.3.7_FY.ROM"` → `("", "V16.3.7")`
- 新增 `parse_rom_filename` 参数化用例: `"ITE_NOR_yj_Smassage_L36_4d_Beelogo_103.3.1.ROM"` → `("L36", "V103.3.1")`
- 新增 `parse_rom_filename` 参数化用例: `"ITE_NOR_yj_Smassage_L36_H530_62.3.2.ROM"` → `("L36", "V62.3.2")`
- 新增 `test_segmented_screen_before_handcontrol_ui_in_catalog`
- 新增 `test_music_bt_detects_mot_files`
- 新增 `test_movement_3d_detects_mot_files`
- 新增 `test_version_extracted_from_space_separated_rom`

### 测试结果
- `tests/test_file_scan.py`: 37 passed (原27 + 10新增)
- 全量回归: 147 passed, 0 failed
