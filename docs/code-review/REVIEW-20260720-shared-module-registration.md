# REVIEW-20260720: 共享登记入口（Phase B2）

| 项 | 内容 |
| --- | --- |
| 类型 | 新服务 + 双轨 UI |
| 模块 | `core/services/shared_module_service`、`core/services/shared_migration_service`、`core/firmware_catalog`、`ui/view_models/scheme_workbench_model`、`ui/workbench_panel`、`ui/workbench_helpers`、`ui_qt/workbench_window` |
| 状态 | ✅ Qt 人验通过（2026-07-23）；代码已提交；CTk 留待 B3 切默认入口时随带验证 |
| 相关 TASK | `specs/active/TASK-20260720-shared-module-registration.md`（裁剪后）、`specs/active/TASK-20260723-firmware-ref-migration.md`（迁移后置） |
| 审查日期 | 2026-07-20（Issue 1 修复并入本 TASK；2026-07-23 范围裁剪 + 人验 + commit） |

## 范围调整（2026-07-23）

用户讨论后确认 `TASK-20260720` Phase B2 **裁剪 `.ref` 迁移**：原计划含 `shared_migration_service.py` + `preview_ref_migration` / `apply_ref_migration` view model API + CTk/Qt「从 .ref 导入共享…」UI + 预览对话框 + `catalog_label_for_dir` 的 `.ref` 父目录映射分支 + `filter_chosen_for_conflict` helper 及其三个回归测试 —— **全部移至 `TASK-20260723-firmware-ref-migration.md`**。理由见裁剪后 TASK 的 Goal 章节。

对本审查记录的影响：

| 处理方案条目 | 处置 |
| --- | --- |
| 处理方案 2 (`shared_migration_service`) | 📌 随迁移移走，B2 不再做 |
| 处理方案 3 (`firmware_catalog::catalog_label_for_dir` `.ref` 映射分支) | 📌 随迁移移走；`catalog_label_for_dir` 若手动登记路径不依赖则一并删除并补回归测试 |
| 处理方案 5 「侧栏加「从 .ref 导入共享」入口与预览对话框」 | 📌 随迁移移走 |
| 自动化门禁记录（377 passed 含迁移测试） | 📌 重跑回退后将下降至 ~350 passed；具体数随删除清单核对后记录 |
| 人工验证场景 4「`.ref` 迁移预览确认」、场景 5「未导入源登记」 | 📌 移至后置 TASK 人验清单 |
| Issue 1（跨型号同名冲突过滤纯函数 `filter_chosen_for_conflict`） | 📌 随迁移移走；若手动登记路径不依赖，连同三个 `test_filter_chosen_for_conflict_*` 一并删除 |

> **未迁移的剩余议题**：手动登记（set/clear service + CTk/Qt 右键 + 冲突不静默覆盖）+ B4 隔离回归仍由 B2 承接，本审查记录「未关闭议题」一节只剩这些；人验 4 场景通过后归档。

## 问题描述

B1 提供 `shared_modules` schema + 解析器，但烧录员没有 UI 入口把共享引用写入 `型号配置.toml`。**裁剪后**只剩一条**手动「设为共享」**入口：仅选工作区内已扫描到的真实来源资产；冲突不静默覆盖；取消共享只删 toml 不删文件。

> 原「`.ref` / `-同X` 一次性迁移」入口已移至后置 TASK，不在本审查范围。

## 处理方案（裁剪后剩余项）

1. `core/services/shared_module_service.py`：`set_shared_module`（资产 + 工作区根 + 目标根 → 四字段 ref + id 校验 + 同键冲突检测）、`clear_shared_module`（幂等删条目不删文件）。错误码：`ok` / `invalid_args` / `source_no_id` / `out_of_workspace` / `conflict` / `write_failed`。
2. 工作台 `register_shared_module` / `unregister_shared_module`；目标根走 `_model_root_path_for_name`，不落 `通用/`。
3. CTk + Qt 双壳右键菜单加「为它登记共享来源…」、「取消共享」。文案共用 `workbench_helpers`，禁「回源」。
4. 不做 B3 展示（角标 / 可烧 / 缺失灰掉 / 列表只显共享）；不碰 `get_scheme_modules` / 回源（B4 隔离）；无 `mode` 字段。

> 原 2（`shared_migration_service`）、3（`catalog_label_for_dir` `.ref` 分支）、5（侧栏「从 .ref 导入」入口）随迁移整迁出，见「范围调整」表。

## 自动化门禁

```text
uv run python -m pytest -m "not ui" -q
→ 377 passed, 52 deselected；coverage 87.35%（裁剪前，含 .ref 迁移测试）
```

> **回退后重跑（已完成）**：按「回退清单」删除 `shared_migration_service` / `test_shared_migration_service` / view model 的 `preview_ref_migration` / `apply_ref_migration` / CTk + Qt「从 .ref 导入共享」按钮与预览对话框 / `catalog_label_for_dir` / `filter_chosen_for_conflict` + `shared_migration_button_label` / `shared_migration_dialog_title` 及对应测试（共 18 项）后：
>
> ```text
> uv run python -m pytest -m "not ui" -q
> → 359 passed, 52 deselected；coverage 86.78%
> ```
> 门禁仍绿色，coverage 仍 ≥ 80%。`shared_module_service` / `shared_module_resolver` / B1 schema / `register_shared_module` / `shared_source_picker_caption` 全部保留不动。

## 契约合规检查（裁剪后剩余）

| 契约项 | 结果 |
| --- | --- |
| 手动入口只选工作区内真实资产 | ✅ 选择源来自 `model._all_assets`；排除目标型号自身 |
| 不静默覆盖（service/UI 拦截） | ✅ `load_shared_modules` 查重；`conflict` 走 UI 弹窗确认 |
| 键 = 目标型号规范模块键 | ✅ `canonical_module_dir`；catalog label 优先 |
| 落盘只碰 `型号配置.toml` | ✅ 复用 B1 `save_shared_module` / `remove_shared_module` |
| 取消共享不删固件文件 | ✅ `test_clear_does_not_delete_firmware_files` |
| 双轨 UI 文案一致、禁「回源」 | ✅ 共用 `workbench_helpers`；UI 标项测过 |
| B4 隔离（回源不吃共享） | ✅ `test_register_does_not_break_scheme_isolation` |
| 不引入 `mode` | ✅ 无 follow_default / pinned |
| 不改 types / 数据库 schema | ✅ 共享只存 toml |
| 不移动 / 复制 / 删除 bin/hex | ✅ 只写引用元数据 |

> 随迁移删的契约行：「迁移可写『源未导入』引用」「幂等迁移」 → 见「范围调整」表。

## 风险与权衡（裁剪后剩余）

1. **source_model_id 推断**：源未导入时 slugify 源根目录名作为占位 id（对齐 B0 写入规则）；源导入后以盘上为准。手动入口不依赖未导入源，本风险保持。
2. **取消共享不删文件**（B4b）：只删 toml 条目；保留本地副本属过渡期磁盘事实，UI 不暴露给烧录员 —— **物理合并延后至 firmware-crud TASK**；B3 DoD 必须加「共享有效态模块在普通列表/烧录候选只显共享来源」。
3. **双壳 UI**：行为落在 view model / service，菜单共用 helpers；人验场景 4 专门核对文案一致。

> 原 `.ref` 一次性线索非协议、冲突逐条确认风险随迁移移走，见后置 TASK `TASK-20260723`。

## 人工验证

✅ **Qt 4 场景通过（2026-07-23）**：手动设共享 / 冲突不静默覆盖 / 取消不删文件 / 双轨一致（Qt 独验；CTk 共用 `workbench_helpers` 纯函数保证文案一致，留待 B3 切默认入口时随带验证）。

## 相关 Commit

| 哈希 | 描述 |
| --- | --- |
| 1a03706 | feat(core,ui): 共享手动登记入口（Phase B2） |

## 审查议题

### Issue 1（P1·已修；📌 范围调整后随迁移移走）：UI 批量确认只按 module_key 过滤，跨目标型号同名模块被同时覆盖  `complexity: medium`

**复杂度理由：** 修复动作 = 抽 `filter_chosen_for_conflict` 纯函数 + 3 个回归测试；双壳共用纯函数，不动 schema / service 签名。裁剪后整议题随迁移移走，本审查只保留记录、不实施修复，故实际修复量级仍为 medium（在后置 TASK 复活时承担）。
**文件：** `ui/workbench_panel.py:891`、`ui_qt/workbench_window.py:977`

`屏蔽层以 (target_model_root, module_key)` 定位一条引用；service payload 的 `conflicts` 每条也都含 `target_model_root`。但 CTk / Qt 的批量确认循环只按 `module_key` 过滤 `chosen` 候选，若迁移跨多个目标型号 × 同名模块出现冲突，一次弹窗「是」会被翻译成「同时覆盖两个目标型号」。

**📌 范围调整（2026-07-23）处置**：`filter_chosen_for_conflict` 仅为迁移批量确认服务于跨型号同名冲突场景。B2 裁剪后：
- 手动「设为共享」的冲突是单条覆盖确认（右键行只对应单一目标型号 + 单一模块），无跨型号批量仓的问题，不需 `filter_chosen_for_conflict`。
- Issue 1 连同 `filter_chosen_for_conflict` helper、三个 `test_filter_chosen_for_conflict_*` 回归测试，以及原「修复」段落，**整建制移至后置 TASK `TASK-20260723-firmware-ref-migration.md` 的审查记录起点**——重新评估自动化迁移时再开。
- 若回退时确认手动登记路径完全没引用 `filter_chosen_for_conflict`，本审查项可直接删除并归档至 `docs/code-review/archive/`；否则保留 helper、按手动路径补回归测试。

**状态：** 📌 随迁移移走（裁剪后不归 B2 处理）