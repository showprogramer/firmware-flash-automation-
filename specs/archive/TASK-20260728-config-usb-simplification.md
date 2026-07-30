# TASK-20260728：配置简化 + USB 烧录流程对齐

## 状态


| 项    | 状态                                            |
| ---- | --------------------------------------------- |
| 类型   | 设计 + 拆解（多子任务）                                 |
| 当前状态 | ✅ T1/T2/T3 全部实现并人验通过（2026-07-28）；REVIEW Issue 1–7 已闭环并归档；后续「设置页统一接收 `root_dir`」由 `TASK-20260728-program-folder-settings-entry` 承接 |
| 前置   | Phase C 已完成；`feature/pyside6-migration` 已通过人验 |
| 父任务  | —                                             |
| 分支   | `feature/pyside6-migration` |


---

## 背景与动机

### 1. config.toml 过度暴露内部配置

`config.example.toml` 目前有 35 行，包含正则表达式、USB 垃圾文件列表、音乐源目录等内容。
实际上这些字段从未被烧录员手动修改过，暴露出来只会造成困惑甚至误改。

**根因**：早期开发时把「可能需要调试/覆盖的参数」全部做成可配置，
但 `settings.py` 的 `_DEFAULTS` 已经包含所有正确的默认值，
config.toml 里的 `[scan]` / `[usb]` / `[music]` 实际上只是覆盖接口，从未被用到。

### 2. USB 手控烧录流程与实际工作不匹配

当前 `[usb]` 配置包含垃圾文件检测（`junk_extensions`、`junk_filenames`）和
USB 健康检查（`auto_diagnose_on_insert`、`health_check_interval_sec`）。

**实际烧录员工作流**：格式化 U 盘 → 复制文件 → 弹出。
格式化本身清空所有内容，垃圾文件检测解决的是一个不存在的问题。
正确的设计是**「格式化 + 复制」一键流程**，而不是在已有内容的 U 盘上做检测清理。

### 3. 音乐文件没有独立的全局源目录

`[music].default_source_dir` 假设音乐文件放在一个独立目录。
实际上音乐文件（`music_files` 类型）和其他固件一样，
存放在各型号程序目录下，扫描后已在索引中，不需要全局路径配置。

### 4. config.toml 放在 exe 旁边不利于发布

目前 `dist/` 必须有 `config.toml`（或用户首次手动创建）。
挪到 `%APPDATA%\fwasset\` 后，`dist/` 只剩 `fwasset.exe` +
`firmware_catalog.toml`，发布更干净，也符合 Windows 应用惯例。

---

## 关键决策（已明确）


| #   | 决策                                                                          |
| --- | --------------------------------------------------------------------------- |
| A   | `firmware_catalog.toml` 继续放 exe 旁边，不嵌入 exe，不做设置界面                           |
| B   | `config.toml` 只保留 `[paths]` 节：`root_dir`（必填）、`tool_root`（预留，暂未使用）           |
| C   | `[usb]`、`[scan]`、`[music]` 全部从用户配置移除；`_DEFAULTS` 保留在 `settings.py`          |
| D   | `config.toml` 迁移到 `%APPDATA%\fwasset\config.toml`；旧版 exe 旁的文件由用户手动删除，无需自动迁移 |
| E   | 首次启动检测到配置缺失时弹**配置向导**（可跳过）；向导本质上是设置页的首次启动态，`root_dir` 后期统一收入设置              |
| F   | USB 手控烧录改为**格式化（FAT32）+ 复制**一键流程；需格式化确认弹窗防误操作；移除垃圾文件检测逻辑                    |
| G   | `tool_root` / 一键烧录工具启动**推迟实现**（各厂商工具差异大，待后期烧录员自设置）；当前 `tool_launch` 面板保持现状  |
| H   | `exclude_dir_keywords` 随工厂目录规范统一后失去价值；硬编码最小集（如系统目录），不再作为用户配置暴露              |


---

## 待讨论的问题

> 以下问题已在 2026-07-28 讨论中确认，决策见上方「关键决策」表。


| #   | 问题                     | 结论                                             |
| --- | ---------------------- | ---------------------------------------------- |
| 1   | 向导触发时机                 | 仅首次启动（检测到配置缺失时）弹出                              |
| 2   | 向导跳过选项                 | 有跳过；`root_dir` 后期统一收入设置页                       |
| 3   | 旧版迁移                   | 用户手动删除 exe 旁的旧 `config.toml`，无需自动迁移            |
| 4   | USB 格式化参数              | FAT32；需格式化确认弹窗；失败时日志 + UI 提示                   |
| 5   | `tool_root` / 工具启动     | 推迟实现；各厂商工具差异大，待后期烧录员自设；当前 `tool_launch` 面板保持现状 |
| 6   | `exclude_dir_keywords` | 随工厂目录规范统一后失去价值；硬编码最小集（系统目录等），不再作为用户配置暴露        |


---

## 子任务拆解

### Task 1：config.toml schema 精简  `complexity: medium`

**复杂度理由：** 纯 `settings.py` + `config.example.toml` 改动，无 UI / 无 schema 迁移；需清理对 `[usb]`/`[scan]`/`[music]` 节的所有 `_cfg_get` 引用，影响面在单文件内。
**Files:**

- Modify `src/fwasset/core/settings.py`：移除 `[usb]`/`[scan]`/`[music]` 的 `_cfg_get` 调用；保留 `_DEFAULTS` 作为程序内默认值；`CONFIG_PATH` 先不动（Task 2 处理）
- Modify `config.example.toml`：缩短为只含 `[paths]`（`root_dir`、`tool_root`）两行
- Modify `src/fwasset/tests/` 中依赖 usb/scan/music config 的测试（若有）

**验收：** `.\ scripts\test.ps1` 通过；扫描行为与精简前一致。

---

### Task 2：config.toml 迁移到 AppData + 首次配置向导  `complexity: high`

**复杂度理由：** 跨 `settings.py`（CONFIG_PATH 变更）+ `app.py`（启动检测）+ 新 Qt 对话框（向导UI）三层；需处理冻结 exe 下 `%APPDATA%` 路径解析；UI 需人验。
**Files:**

- Modify `src/fwasset/core/settings.py`：`CONFIG_PATH` 改为 `Path(os.environ["APPDATA"]) / "fwasset" / "config.toml"`；目录不存在时自动创建
- Modify `src/fwasset/app.py`：启动时检测 `root_dir` 是否已配置，未配置时弹向导
- Create `src/fwasset/ui_qt/setup_wizard.py`：Qt 对话框，两个路径选择器（固件根目录、工具根目录）+ 跳过按钮；完成后写入 AppData config
- Modify `docs/README.md`：更新启动说明（config 位置变化）

**验收：** 新机无 AppData config → 弹向导 → 填路径 → 进主界面；跳过 → 进主界面（root_dir 空）；已有 config → 直接进主界面；人验通过。

---

### Task 3：USB 手控烧录改为格式化 + 复制流程  `complexity: high`

**复杂度理由：** 跨 `AutoUsbPanel`（UI）+ `flash_service`（service）两层；格式化调用系统 API / 外部命令；需处理确认弹窗、失败日志、进度反馈；需人验真实 U 盘。
**Files:**

- Modify `src/fwasset/ui_qt/operation_panels/auto_usb_panel.py`：移除垃圾文件检测 UI；改为「格式化（FAT32）+ 复制」流程；加格式化确认弹窗
- Modify `src/fwasset/core/services/flash_service.py`：移除 junk 清理逻辑；加格式化步骤（Windows `format` 命令或 `win32api`）
- Evaluate `src/fwasset/core/services/usb_repair_service.py`：评估是否整体裁剪
- Modify `src/fwasset/core/settings.py`：`_DEFAULTS["usb"]` 清理（Task 1 后处理）

**验收：** 格式化确认弹窗出现；格式化成功 + 文件复制 = 任务完成；失败时日志有明确提示；人验真实 U 盘通过。

---

## 验收定义（草稿）

- [x] `dist/` 目录只含 `fwasset.exe` + `firmware_catalog.toml`
- [x] 新机器首次启动弹向导，配置完成后正常进入主界面
- [x] 已有配置的机器升级后行为不变（迁移策略确认）
- [x] 手控烧录流程：格式化成功 + 文件复制成功 = 任务完成
- [x] `.\scripts\test.ps1` 通过，覆盖率 ≥ 80%

## 最终验证记录（2026-07-28 收口）

- T1 config schema 精简：`e8558d2`
- T2 config.toml 迁移 AppData + 首次配置向导：`ebcc197`；后续 `QDialog` import 修复 `1adf724`，向导后自动扫描 `d6a846f`
- T3 USB 手控烧录改为格式化 + 复制流程：`3286975`；格式化改 PowerShell `Format-Volume` + 等待就绪 `47529e0`
- 配套代码审查：`REVIEW-20260728-config-usb-simplification.md`，Issue 1–7 全部闭环（`1adf724` / `1e42607` / `4999f13` / `b9e9c13` / `4b9f07a`），已归档至 `docs/code-review/archive/`
- 后续「`root_dir` 统一收入设置页」由 `TASK-20260728-program-folder-settings-entry` 承接（commit `a8f3691`）

