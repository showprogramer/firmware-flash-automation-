# TASK-20260720: 共享登记入口（Phase B2）

> **For Hermes:** 实施时使用 `test-driven-development`，逐项 RED → GREEN → REFACTOR；本 TASK 动 core 服务与**两套 UI**（CTk `ui/` + PySide6 `ui_qt/`），**必须人工验证通过后才能 commit**（右键登记、冲突弹窗为 UI 交互）。范围裁剪（2026-07-23）后**不含 `.ref` 迁移**——已写完的迁移代码与服务按「回退清单」删除。

## 状态

| 项 | 状态 |
| --- | --- |
| 类型 | 父任务 Phase B2（手动登记入口；B3 展示前置） |
| 当前状态 | ✅ **Qt 人验通过（2026-07-23，3 场景）；代码已 commit（`1a03706`）**。CTk 验证故意推迟到 B3 切默认入口同次随带——B2 期 CTk 仍是默认入口但双壳共用 `workbench_helpers` 纯函数保证文案/禁语一致，无需独立再验。范围裁剪：原计划含 `.ref` 一次性迁移已砍掉，迁移独立后置（见 `TASK-20260723-firmware-ref-migration.md`） |
| 父任务 | `specs/active/TASK-20260714-config-takeover.md`（B2 专节 + 落盘文件专节为契约源） |
| 分支 | 继续 `feature/pyside6-migration` |
| 前置（代码） | **B1**（`TASK-20260718`）已提交（`4c8b6db` + 审查修复 `fafd65a`）；B0（`1c287b8`）、原子写（`72d1cca`）已合入 |
| 后续 | 开始 **B3**（角标 / 可烧 / 缺失灰掉 / 列表只显共享）另立 TASK；B3 立项时同切默认入口到 Qt，并随带 CTk 退化验证 |

## Goal

给烧录员**一条**业务登记入口，把一条共享引用写入目标型号根的 `型号配置.toml`（复用 B1 的 `save_shared_module` / `remove_shared_module`）：

1. **手动「设为共享」**：右键当前工作区内**已扫描到的真实来源资产** → 解析出 `source_model_id` + 工作区相对路径 → 选目标型号 + 目标模块 → 写引用。**禁止**手填未导入型号 / 空路径 / 猜同名。
2. **手动「取消共享」**：删除目标模块的引用条目（复用 `remove_shared_module`，只删 toml 不删文件）。

> **范围裁剪（2026-07-23）**：原计划含 `.ref` 一次性迁移入口，已确认砍掉。理由：(1) `-同X`/`.ref` 现场仍是占位、未整理完（父任务约束 4），给不稳定输入喂严格解析器会反复返工；(2) 优先级倒置——先做完"历史目录整理工具"再让烧录员看不到共享效果，是"设置方式奇怪"的根；(3) 个位数关系手登记比写迁移器更快。迁移收尾移至 `TASK-20260723-firmware-ref-migration.md`，待 B3 落地、烧录员真正用上共享后再做（输入也更稳定）。

**只做手动登记入口（写路径 + 冲突不静默覆盖）**；**不**做 B3 展示（角标 / 可烧 / 缺失灰掉 / 列表只显共享来源）——那些留 B3。

## Architecture

新增 `core/services/shared_module_service.py`：`set_shared_module(...)` / `clear_shared_module(...)` 返回 `ServiceResult`（四键，中文消息，专属错误码），内部调 B1 的 `save_shared_module` / `remove_shared_module`；`set_shared_module` 负责从**选中来源资产 + 目标型号**解析出四字段引用、做工作区归属与 id 校验、检测同键冲突。`SchemeWorkbenchModel` 加登记侧 API（`register_shared_module` / `unregister_shared_module`），复用 B1 已有的 `get_shared_modules` / `resolve_shared_module` / `model_root_for_id`。两套 UI（CTk `ui/`、PySide6 `ui_qt/`）各加右键项 + 目标选择/冲突对话框，文案一致。

> **已裁掉**：原 Architecture 含 `shared_migration_service.py` + `preview_ref_migration` / `apply_ref_migration` + 侧栏「从 .ref 导入」按钮与预览对话框。全部移至 `TASK-20260723-firmware-ref-migration.md`。

## Tech Stack

Python 3.11+、`pathlib`、B1 的 `core.model_config`（`SharedModuleRef` / `save_shared_module` / `remove_shared_module` / `load_shared_modules`）、`core.shared_module_resolver`、tkinter（CTk 菜单/对话框）、PySide6（QMenu/QDialog）、pytest。

---

## 契约来源（父任务 B2 / 落盘文件 / B4b 专节，已写死）

本 TASK 不重述、不修改父任务语义；执行必须遵守：

1. **手动入口只选工作区内真实资产**：能从选中资产解析出 `source_model_id`（该资产所在型号根的 `model_id`）+ **工作区相对路径**。**禁止**手填未导入型号、空路径、猜同名。
2. **不静默覆盖**：同一目标模块已有引用 → UI **提示冲突**，用户选覆盖或取消；数据层 `save_shared_module` 本身是幂等覆盖写，**冲突拦截在 service/UI 层**（先 `load_shared_modules` 查重）。
3. **键 = 目标型号规范模块键**（`canonical_module_dir`）；`source_module` 同用规范名（B1 `save_shared_module` 已做规范化，服务层传规范名即可）。
4. **落盘只碰 `型号配置.toml`**：复用 B1 写 API；**禁止**碰 `平台配置.toml` / `save_platform_config`；**禁止**写 `通用/`。
5. **取消共享只删 toml 条目**（B4b）：`remove_shared_module`，**不删任何固件文件**；保留本地副本恢复为有效本地资产（该「恢复」的展示是 B3，B2 只保证不删文件 + 条目已移除）。
6. **双轨 UI 文案一致**（父任务 A6）：CTk 与 Qt 菜单项、冲突措辞相同；行为改在 view model / service，菜单共用 helpers。

> **裁剪说明**：原契约 2/4/7（迁移入口、幂等迁移、`.ref` 非协议）已移至 `TASK-20260723-firmware-ref-migration.md`。「`.ref` 非协议，业务只认 `型号配置.toml` 正规引用」这一条**仍是父任务约束 4 的硬规矩**，本 TASK 不动它、也不在本 TASK 实现 `.ref` 读取。

## 不可变约束

1. **不做 B3 展示**：不加角标「共享自 …」、不改普通模块列表/烧录候选只显共享、不做缺失灰掉可视化、不做「打开来源目录 / 按引用烧」。B2 只登记；B3 才呈现与烧录。
2. **不碰方案回源 / B4**：不改 `get_scheme_modules` / `get_scheme_module_tree`；登记服务**不得**被回源调用。
3. **不引入 `mode` / `follow_default` / `pinned`**（Phase C）。
4. **不改 `平台配置.toml` 读写 / `save_platform_config` / `set_module_default_for_model`**（设默认路径不动）。
5. **不改 B1 的 `save_shared_module` / `remove_shared_module` / 解析器对外行为**；可加新 service 包一层，但四字段 schema 与规范化语义不回退。
6. **不修改 `types.py::FirmwareAsset` / `ServiceResult` 四键结构**；共享引用**只**存 `型号配置.toml`，**不**进 SQLite / 不改 schema。
7. **不移动 / 不复制 / 不删除任何 bin/hex**（复制/移动/删除属 firmware-crud TASK）；B2 只写引用元数据；保留的本地副本属过渡期事实，**物理合并延后至 firmware-crud TASK**。
8. 用户可见消息中文；不要求手写 TOML。
9. 不自动启动 UI、不自动跑 `@pytest.mark.ui`；不对 `D:\按摩器程序` 做破坏性写入（失败注入只在 pytest 临时目录）。
10. 单型号根与多型号父根两种布局都要支持；手动登记的目标型号取自当前工作台选型。
11. **不实现 `.ref` / `-同X` 线索扫描与迁移**（原约束第 7 条的对象）；该能力整建制移至 `TASK-20260723-firmware-ref-migration.md`，待 B3 落地后再做。

---

## 决策：交互方向（**已定，用户确认 2026-07-20**）

**从目标侧发起（B）**：右键**目标型号**（如双机芯）的某模块行 →「为它登记共享来源…」→ 对话框内选**工作区内的真实来源资产** → 写引用。

- 右键项挂在**目标型号的模块行**上，**不是**通用区来源侧（与「设为平台默认」的 `is_common` 显示条件**不同**）。
- 冲突判断天然贴合：右键的就是目标模块，`load_shared_modules(target)` 查该模块是否已有引用 → 有则走覆盖/取消。
- 「取消共享」右键项：目标模块**已处于 shared 有效态**（有引用）时显示。
- 来源资产在对话框里的列法见 Open Question 3（默认预过滤同模块名 + 可放开看全部）。

## 决策：service 契约（实现前写死）

### `set_shared_module`（手动登记）

```
set_shared_module(
    target_model_root: str | Path,   # 目标型号根（写引用的落盘处）
    source_asset: FirmwareAsset,     # 选中的真实来源资产
    workspace_root: str | Path,      # 固件工作区根（算相对路径 + id 归属）
    module_key: str = "",            # 目标模块规范键；空则由来源资产模块推断
    overwrite: bool = False,         # 冲突时是否覆盖
    log_fn=print,
) -> dict  # ServiceResult 四键
```

**流程：**
1. 从 `source_asset["path"]` 取其**型号根**（首段目录相对 `workspace_root`，或 view model 注入 `model_root_for_id` / `_model_root_path_for_name` 反查），读该根 `model_id` → `source_model_id`；缺 id → `code=source_no_id`。
2. 算 `source_relative_path` = 来源**变体/模块目录**相对 `workspace_root`（`Path(...).relative_to(root_dir)` 后统一 `/`）；越界（`..` / 不在工作区）→ `code=out_of_workspace`。**路径粒度**：来源是变体则指变体目录；是模块目录多变体则指模块目录（对齐 B1 解析器 variants 判定）。
3. `module_key` 空则取来源模块规范名（`_module_key_for_asset` / `canonical_module_dir`）；`source_module` = 来源模块规范名。
4. `load_shared_modules(target_root)` 查重：同 `module_key` 已存在且 `overwrite=False` → `code=conflict`（payload 带现有引用，供 UI 弹窗）。
5. 组装 `SharedModuleRef` → `save_shared_module`；成功 `code=ok`，payload 带写入的 ref 摘要 + config_path。

> **分层纪律**：service 接**已拆好的原语**（`source_asset: FirmwareAsset` + `workspace_root` + `target_model_root`），**不**接 `ModuleVariant`（UI 结构不进 core）。从 `variant.asset` 拆出 asset、从 `current_selection` 拆出目标型号、用 `_common_module_parts` 得模块——这些在 **view model 层**（`register_shared_module`）完成后再调 service。core service 只认 `FirmwareAsset` 与路径。

**错误码：** `ok` / `invalid_args`（空目标根 / 空资产）/ `source_no_id`（来源型号根无 model_id）/ `out_of_workspace`（相对路径越界）/ `conflict`（同键已存在且未允许覆盖）/ `write_failed`。

### `clear_shared_module`（取消登记）

```
clear_shared_module(target_model_root, module_key, log_fn=print) -> dict
```
- `remove_shared_module`（只删 toml 条目，不删文件）；不存在的键 → 仍 `ok`（幂等）；`code=write_failed` 兜底。

> **已裁掉**：原 `.ref` 迁移（`scan_ref_clues` / `apply_ref_migration`）一节整建制移至 `TASK-20260723-firmware-ref-migration.md`。本 TASK 不读 `.ref`、不扫 `-同X` 命名线索、不生成「源尚未导入」的引用。

---

## 实施计划（TDD）

> 精确挂载点（右键菜单构建方法、选中资产获取、view model 方法名）见「代码定位」表（探查后补）；以下为 task 骨架，实施时对齐真实 file:line。

### Task 1：`set_shared_module` service（纯数据，无 UI）  `complexity: medium`

**复杂度理由：** 单 service 纯函数，无 UI / 无 schema / 无双壳；错误码 5 种、测试用例 ~7，越界与冲突分支为中粒度而非 low。
**Files:** Create `src/fwasset/core/services/shared_module_service.py`；Create `src/fwasset/tests/test_shared_module_service.py`

**RED** — 临时工作区（源型号根 + 目标型号根）覆盖：
1. 正常：选源资产 + 目标 → 写入引用，`load_shared_modules(target)` 读回，四字段正确、`source_model_id` = 源根盘上 id；
2. `source_relative_path` 相对工作区根、含源型号目录段、统一 `/`；
3. 源根无 `model_id` → `source_no_id`，不写；
4. 相对路径越界（资产在工作区外）→ `out_of_workspace`，不写；
5. 同 `module_key` 已存在 + `overwrite=False` → `conflict`，payload 带现有引用，**不写**；`overwrite=True` → 覆盖；
6. `module_key` 空 → 用来源模块规范名；键规范化（`机芯版`→`机芯板`）；
7. `write_failed`：monkeypatch 写盘失败 → 原文件不变。

**GREEN:** 实现 service，调 B1 `save_shared_module`。

### Task 2：`clear_shared_module` service  `complexity: low`

**复杂度理由：** 复用 B1 `remove_shared_module` + 3 个用例；幂等 + 不删文件断言，单文件单关注点。
**Files:** Modify 同上；Modify 测试

**RED:**
1. 删已存在引用 → `ok`，条目消失，`model_id` 与其它段保留；
2. 删不存在键 → `ok`（幂等），文件不损坏；无 `型号配置.toml` 的根 → `ok` 且不建空文件（复用 B1 `fafd65a` 短路）；
3. **不删文件**：目标根内同模块 bin/hex 仍在磁盘（断言文件存在）。

**GREEN:** 调 `remove_shared_module`。

### Task 3：view model 登记 API（无 UI 逻辑）  `complexity: medium`

**复杂度理由：** 单 view model 文件 + 测试；新增 2 个方法复用 Task 1/2 service；含 B4 隔离回归 ~5 用例，跨入 view model 层但不动 UI / schema。
**Files:** Modify `src/fwasset/ui/view_models/scheme_workbench_model.py`；Modify `src/fwasset/tests/test_scheme_workbench_model.py`

**新增（名称可微调，语义固定）：**
- `register_shared_module(target_model_name, source_asset, module_key="", overwrite=False)` → 调 `set_shared_module`（`workspace_root=self.root_dir`，目标根经 `_model_root_path_for_name`）。
- `unregister_shared_module(target_model_name, module_key)` → `clear_shared_module`。

**RED:**
1. 选源资产 + 目标型号 → `register_shared_module` 成功，`get_shared_modules(target)` 读回；
2. 冲突返回 `conflict`（不写），`overwrite=True` 覆盖；
3. `unregister_shared_module` 删条目、`get_shared_modules` 不含该键、目标目录文件仍在；
4. **B4 隔离回归**：登记后 `get_scheme_modules` / `get_scheme_module_tree` 仍不含共享行；
5. 回归：`load_all_models` / 侧栏 / 设默认 / B0 id / B1 解析 API 全过。

> **已裁掉**：原 Task 3「`.ref` 迁移 scan + apply」与 `preview_ref_migration` / `apply_ref_migration` view model API 整建制移至 `TASK-20260723-firmware-ref-migration.md`。

### Task 4：CTk UI 右键 + 对话框  `complexity: high`

**复杂度理由：** 动 CTk UI 右键菜单构建 + 来源选择对话框 + 冲突弹窗；UI 入口变更需人验；改 `workbench_helpers` 共用文案（与 Task 5 共担 high）。
**Files:** Modify `src/fwasset/ui/...`（右键菜单构建处 + 冲突对话框；见代码定位表）；Modify `src/fwasset/ui/workbench_helpers.py`（共用文案/弹窗 helper）

- **从目标侧发起（B）**：右键**目标型号模块行** → 「为它登记共享来源…」→ 对话框列工作区内可作来源的真实资产（默认预过滤同模块名，可放开）→ 选中 → `register_shared_module`；同模块已有引用 → 覆盖/取消弹窗。
- 目标模块**已 shared 有效**时右键 → 「取消共享」：确认后 `unregister_shared_module`。
- **文案禁「回源」**；用户可见「登记共享来源」「取消共享」「共享自」等。
- UI 测试标 `@pytest.mark.ui`；逻辑测试走 view model（非 UI）。

> **已裁掉**：原「从 .ref 导入共享…」入口 + 预览列表（可解析/无法解析/冲突分区）+ 迁移相关 helper 一并移至后置迁移 TASK。

### Task 5：PySide6 UI 右键 + 对话框  `complexity: high`

**复杂度理由：** Qt 对称 Task 4；双壳人验；QMenu/QDialog 跨文件，文案须与 CTk 一致。两壳合算一次跨壳改，标 high 而非拆 low。
**Files:** Modify `src/fwasset/ui_qt/...`（QMenu action + QDialog）；共用 helper 对齐 CTk 文案

- 与 Task 4 同交互、同文案；QMenu action 槽 → 同一 view model API。

### Task 6：非 UI 门禁  `complexity: low`

**复杂度理由：** 纯门禁跑 pytest + 断言覆盖率 ≥ 80%；不改代码；只读验证。

```bash
uv run python -m pytest -m "not ui" -q
```
Expected: 全部非 UI 通过；coverage ≥ 80%；UI 测试 deselect。

**禁止 Agent 执行**：`scripts/test.ps1`、`uv run fwasset`、`FWASSET_UI=qt uv run fwasset`、任何未过滤 `@pytest.mark.ui` 的全量测试。

### Task 7：审查记录、CHANGELOG 与父任务同步  `complexity: low`

**复杂度理由：** 纯文档同步：REVIEW / CHANGELOG / 父任务勾选；不改代码逻辑。

- Create `docs/code-review/REVIEW-20260720-shared-module-registration.md`（类型：新服务 + 双轨 UI；问题：共享手动登记入口；处理：set/clear service + 两套右键；验证记录；人验状态；commit 后补哈希）。
- Modify `docs/CHANGELOG.md`（Unreleased 增条目，注明 `.ref` 迁移已移至后置 TASK）。
- Modify `specs/active/TASK-20260714-config-takeover.md`（B2 checklist 勾选、注明本 TASK 承载；解锁 B3）。
- Modify 本文件状态与 DoD。

> **Task 编号说明**：原计划 Task 1–8（含迁移 Task 3、Task 5/6 迁移子项）。裁剪后重新编号为 Task 1–7，迁移相关任务整建制移至 `TASK-20260723-firmware-ref-migration.md`。原实施已完成的迁移代码与测试**需在提交前回退**（见「回退清单」）。

---

## 回退清单（裁剪前已写完、已过门禁，提交前必须删）

> 范围裁剪发生在代码完成后，所以这是**反向操作清单**，不是新增清单。逐项删除后，重跑非 UI 门禁确认绿色，再人验 Qt 3 场景。

| 操作 | 路径 | 内容 |
| --- | --- | --- |
| Delete | `src/fwasset/core/services/shared_migration_service.py` | 整文件（`scan_ref_clues` / `apply_ref_migration` / `RefClue`） |
| Delete | `src/fwasset/tests/test_shared_migration_service.py` | 整文件 |
| Modify | `src/fwasset/ui/view_models/scheme_workbench_model.py` | 删 `preview_ref_migration` / `apply_ref_migration` 方法及其测试；保留 `register_shared_module` / `unregister_shared_module` |
| Modify | `src/fwasset/ui/workbench_panel.py` | 删侧栏「从 .ref 导入共享…」按钮 + 预览对话框 + 槽 |
| Modify | `src/fwasset/ui_qt/workbench_window.py` | 同上 Qt 对称 |
| Modify | `src/fwasset/ui/workbench_helpers.py` | 评估 `filter_chosen_for_conflict` 是否仍被 `register_shared_module` 路径用到；仅迁移冲突过滤用 → 连同三个 `test_filter_chosen_for_conflict_*` 一并删；若手动登记也走它则保留 |
| Modify | `src/fwasset/tests/test_scheme_workbench_model.py` | 删迁移相关用例 |
| Modify | `src/fwasset/tests/test_workbench_panel_helpers.py` | 删迁移冲突过滤用例（若 `filter_chosen_for_conflict` 一并删） |
| Modify | `src/fwasset/core/firmware_catalog.py` + `tests/test_firmware_catalog.py` | 评估 `catalog_label_for_dir`：若仅迁移 `.ref` 父目录名映射用 → 删；若有别处复用则保留但补测试 |
| Modify | `docs/CHANGELOG.md` Unreleased | 删/改 `.ref` 迁移条目；改为「手动登记（Phase B2）+ `.ref` 迁移移后置」 |
| Modify | `docs/code-review/REVIEW-20260720-*.md` | 删迁移服务条目 + Issue 1（跨型号冲突过滤纯函数）一并迁往后置 TASK 审查记录 |

> **门禁预期**：删除后 `pytest -m "not ui"` 仍应 ≥ 350 passed、coverage ≥ 80%（原 377 passed 含迁移测试）。`shared_module_service` / `shared_module_resolver` / B1 schema / `register_shared_module` 全部不动。

> **本回退是范围裁剪不是功能去除**：`.ref` 迁移能力**仍承诺做**，只是不在本 TASK 做；后置 TASK 接手后输入更稳定，返工小。

---

## 代码定位（探查已确认，精确 file:line）

> **关键前提**：两套 UI 右键回调拿到的是 **`ModuleVariant`**（dataclass，`scheme_workbench_model.py:82`），**不是** `FirmwareAsset`；资产经 `variant.asset` 取。「设为共享」入口应与「设为平台默认」并列，同样接 `variant`，再 `variant.asset`。

| 关注点 | 位置 | 备注 |
| --- | --- | --- |
| **CTk 右键菜单构建** | `ui/workbench_panel.py:574` `_on_grid_right_click(variant, x_root, y_root)`（`tk.Menu` + `add_command` + `tk_popup`，574-601） | 新「设为共享」项挂同处 |
| CTk 右键信号链 | `ui/panels/data_grid_panel.py:87`（`<Button-3>` 绑定）→ `data_grid_panel.py:234` `_on_tree_right_click`（`_variant_map` 取 variant）→ `workbench_panel.py:255` 注册 `on_right_click` | — |
| CTk「设为平台默认」项 + 回调 | 菜单项 `workbench_panel.py:588-592`；回调 `_set_default_variant(variant)` `workbench_panel.py:603`（messagebox 确认 → `workbench_model.set_default_variant(...)` 615-617 → `_refresh_main_grid`） | 「设为共享」照此对称写 |
| CTk 启用/禁用逻辑 | `workbench_panel.py:580-593`（仅 `is_common` 显示；已是默认则 disabled） | 「设为共享」的显示条件另定（见决策） |
| **Qt 右键菜单构建** | `ui_qt/workbench_window.py:686` `_on_grid_right_click(variant, global_pos)`（`QMenu` + `QAction` + `exec`，687-715） | 新 action 挂同处 |
| Qt 右键信号链 | `ui_qt/data_grid.py:61-62`（`CustomContextMenu`）→ `data_grid.py:189` `_on_context_menu`（`_VARIANT_ROLE` 取 variant）→ `workbench_window.py:199` `variant_right_clicked.connect(...)` | — |
| Qt「设为平台默认」action + 槽 | action `workbench_window.py:703-705`；槽 `_set_default_variant(variant)` `workbench_window.py:717`（`QMessageBox.question` → 同一 view model 方法 → refresh） | Qt「设为共享」照此对称 |
| Qt 启用/禁用逻辑 | `workbench_window.py:692-706`（同 CTk） | — |
| **view model 设默认公共方法** | `scheme_workbench_model.py:590` `set_default_variant(model_name, asset, log_fn, platform_name="") -> dict`（四键返回） | 新登记 API 紧邻 `resolve_shared_module`（293）之后，与之对称 |
| **B1 已有读取 API** | `get_shared_modules`（283）/ `resolve_shared_module`（293）/ `model_root_for_id`（254）/ `resolve_model_id`（243）/ `ensure_model_id`（225）/ `_model_root_path_for_name`（261） | 直接复用 |
| **从资产反推模块 + 相对路径**（B2 核心复用） | `_common_module_parts(asset)`（`scheme_workbench_model.py:449`，以 path 里「通用」段为锚 → `(模块目录名, 变体目录名)`）；`_module_key_for_asset(asset)`（485，规范模块键）；`self.root_dir`（105/130，工作区根）→ `Path(asset["path"]).relative_to(self.root_dir)` 得相对路径（模式见 428/666/676） | 手动登记从这里取 `source_relative_path` / `source_module` |
| 当前工作台选型 | `self.current_selection.model_name`（`WorkbenchSelection`，`workbench_panel.py:74/299`；Qt 同名）；`module_label_from_asset` `ui/workbench_helpers.py:36` | 目标型号/模块默认取值 |
| service 样板 | `core/services/platform_default_service.py::set_module_default_for_model`（197-）/ `set_default_variant`（131-）：四键 / 错误码 / 中文消息 / 落盘校验范式 | 新 service 照此 |
| `SharedModuleRef` 目标字段 | `core/model_config.py:51-59`（`module_key` / `source_model_id` / `source_group` / `source_module` / `source_relative_path`） | B2 从资产 + 上下文填这五字段 |

---

## 人工验证（Qt 通过 2026-07-23；CTk 推迟到 B3）

### Qt 3 场景 — ✅ 通过

1. **手动设为共享** ✅
2. **冲突不静默覆盖** ✅
3. **取消共享不删文件** ✅
> **说明**：CTk 与 Qt 共用 `workbench_helpers` 纯函数保证文案一致；CTk 随 B3 切默认入口同次验证，B2 不独立再验。

> **裁剪**：原场景 4/5（`.ref` 迁移 / 未导入源）整迁出；双轨一致不再作为独立 B2 场景。

### 现场

不修改 `D:\按摩器程序`，在测试副本验证。

**建议提交信息：**
```text
feat(core,ui): 共享手动登记入口（Phase B2）

- set/clear_shared_module 服务：手动登记仅工作区内真实资产，id 归属 + 相对路径校验
- 冲突不静默覆盖（load 查重 → UI 覆盖/取消）；取消只删 toml 条目不删文件
- 工作台 register/unregister API；CTk + Qt 右键与对话框文案一致
- 不碰方案回源（B4 隔离）；不做 B3 展示；无 mode
- 范围裁剪：原计划含 .ref 迁移，已砍掉移至 TASK-20260723-firmware-ref-migration

影响范围:
- core/services/shared_module_service、ui/view_models/scheme_workbench_model
- ui/ 与 ui_qt/ 右键菜单与对话框

验证:
- set/clear 服务测试通过（正常/冲突/越界/不删文件）
- B4 隔离回归通过；非 UI 测试与覆盖率门禁通过
- CTk / Qt 人工验证通过（设共享/冲突/取消不删/双轨一致）
```

---

## Files Likely to Change

| 操作 | 路径 | 目的 |
| --- | --- | --- |
| Create | `src/fwasset/core/services/shared_module_service.py` | `set_shared_module` / `clear_shared_module` |
| Modify | `src/fwasset/ui/view_models/scheme_workbench_model.py` | register/unregister API |
| Modify | `src/fwasset/ui/...`（右键菜单 + 冲突对话框，探查补） | CTk 登记入口 |
| Modify | `src/fwasset/ui/workbench_helpers.py` | 共用文案/弹窗 helper |
| Modify | `src/fwasset/ui_qt/...`（QMenu + QDialog，探查补） | Qt 登记入口 |
| Create | `src/fwasset/tests/test_shared_module_service.py` | 登记/取消服务测试 |
| Modify | `src/fwasset/tests/test_scheme_workbench_model.py` | view model 登记 API + B4 隔离回归 |
| Create | `docs/code-review/REVIEW-20260720-shared-module-registration.md` | 审查记录 |
| Modify | `docs/CHANGELOG.md` | 未发布变更 |
| Modify | `specs/active/TASK-20260714-config-takeover.md` | B2 勾选、解锁 B3 |
| Modify | 本文件 | 进度 |

> **裁剪**：原 Files 含 `shared_migration_service.py` / `preview`/`apply` view model API / `.ref` 扫描 + 幂等迁移 / 迁移服务测试 —— 全部移至 `TASK-20260723-firmware-ref-migration.md`。

预计不改：`model_config.py` / `shared_module_resolver.py`（B1 对外行为）、`platform_config.py` / `save_platform_config` / `set_module_default_for_model`、`get_scheme_modules` / 回源、`types.py`、数据库 schema、`D:\按摩器程序`。

---

## Definition of Done

- [x] `set_shared_module`：手动登记仅工作区内真实资产；`source_model_id` = 源根盘上 id；`source_relative_path` 相对工作区根；`source_no_id` / `out_of_workspace` / `conflict` / `write_failed` 错误码；键规范化。
- [x] `clear_shared_module`：删条目幂等；**不删固件文件**；无配置根不建空文件。
- [x] **不静默覆盖**：冲突在 service/UI 拦截（`load_shared_modules` 查重）。
- [x] view model register/unregister 可用；目标根不落 `通用/`。
- [x] **B4 隔离**：登记后 `get_scheme_modules` / `get_scheme_module_tree` 不含共享行；回源代码未改。
- [x] 两套 UI（CTk + Qt）右键项 + 冲突对话框，文案一致、禁「回源」；Qt 已完成人验，CTk 随 B3 切默认入口验证。
- [x] **不做 B3 展示**（角标/可烧/缺失灰掉/列表只显共享留 B3）；**无 mode**；共享只存 toml 不进索引。
- [ ] **物理合并延后至 firmware-crud TASK**：本阶段只写引用元数据；本地副本属过渡期磁盘事实，不在 UI 暴露给烧录员——**B3 DoD 必须加「共享有效态模块在普通列表/烧录候选只显共享来源，不并列本地副本」**（移交 B3 写死）。
- [x] 不碰 `平台配置.toml` / `save_platform_config` / `set_module_default_for_model`；不移动/复制/删除任何 bin/hex。
- [x] `.ref` 迁移代码与服务按「回退清单」删除；`pytest -m "not ui"` 通过且 coverage ≥ 80%（359 passed / 86.78%）；未自动启动 UI；未破坏性写入 `D:\按摩器程序`。
- [x] CHANGELOG、审查文档、父任务 B2 状态同步。
- [x] 人验 Qt 3 场景通过已按模板提交；B3 立项时切默认入口并随带 CTk 验证后才解除 B3 阻塞。

## Risks and Trade-offs

1. **不静默覆盖**：`save_shared_module` 数据层是幂等覆盖，冲突判断必须在 service 层先 `load_shared_modules` 查重，否则 UI 覆盖确认形同虚设。
2. **相对路径与 id 归属**：`source_relative_path` 必须相对工作区根且含源型号目录段；`source_model_id` 取**源根盘上 id**（非资产文件名 `model` 字段）。越界拒绝。
3. **取消共享不删文件**（B4b）：只删 toml 条目；保留本地副本恢复为有效资产的**展示**是 B3，B2 只保证文件不动 + 条目已移除。
4. **双轨 UI 一致**：行为落在 view model / service，菜单共用 helpers；两套文案漂移是常见坑，人验场景 4 专门核对。
5. **不越界到 B3 / firmware-crud**：不画角标不改烧录候选、不复制/移动/删文件——超范围即返工。**物理合并延后**：保留本地副本是过渡期磁盘事实，UI 上不暴露给烧录员（B3 落实「只显一份」）。
6. **范围裁剪的回退风险**：`.ref` 迁移代码已写完并过门禁，删除时需同步删测试与 helper，避免残留死代码或假绿门禁（详见「回退清单」）。

## Open Questions

实施前需在本 TASK 记下并（若偏离契约）经用户确认：

1. **来源资产在对话框里怎么列**（B 方向的子问题）：右键目标模块后，对话框要列「工作区内可作来源的真实资产」。是列**全部通用区资产**让用户搜/选，还是**按同模块名预过滤**（如目标是「蓝牙程序」→ 优先列各型号通用的蓝牙）？建议默认预过滤同模块名 + 允许放开看全部；多义时用户在对话框改。实施前定并记下。

> **已裁掉**：原 OQ 1（`.ref`/`-同X` 线索格式与解析规则）、OQ 2（迁移 service 是否并入）随 `.ref` 迁移整建制移至 `TASK-20260723-firmware-ref-migration.md`。

其余（落盘文件、双入口分离、不静默覆盖、幂等、不删文件、无 mode、B4 隔离、双轨文案、人验边界）均已由父任务写死。
