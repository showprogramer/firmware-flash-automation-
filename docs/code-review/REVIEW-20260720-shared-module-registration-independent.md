# REVIEW-20260720: 共享登记入口独立审查（Phase B2）

| 项 | 内容 |
| --- | --- |
| 类型 | 独立代码审查：新服务 + 双轨 UI |
| 模块 | `shared_module_service`、`shared_migration_service`、`firmware_catalog`、`scheme_workbench_model`、`workbench_panel`、`workbench_window` |
| 状态 | 📌 **范围调整（2026-07-23）后整审查议题随迁移后置**；Qt 人验通过（2026-07-23），代码已提交，CTk 待 B3；见下方「范围调整生效说明」 |
| 相关 TASK | `specs/active/TASK-20260720-shared-module-registration.md`（裁剪后）、`specs/active/TASK-20260723-firmware-ref-migration.md`（迁移后置） |
| 审查日期 | 独立审查 2026-07-20；核对+修复 2026-07-20；范围调整 + 人验 2026-07-23 |
| 被审记录 | `REVIEW-20260720-shared-module-registration.md`（实现自检，保留不改） |

## 范围调整生效说明（2026-07-23）

用户讨论后确认 `TASK-20260720` Phase B2 **裁剪 `.ref` 迁移**，迁移代码 + UI 整建制移至 `TASK-20260723-firmware-ref-migration.md`。本独立审查记录的所有议题均针对**迁移服务**或与迁移代码强耦合的边界，处置如下：

| 议题 | 处置 |
| --- | --- |
| Issue 1（单型号根迁移误写 `通用/型号配置.toml`） | 📌 随迁移整迁出 B2；后置 TASK 启动时作为审查起点再开 |
| Issue 2（迁移 UI 未支持候选选择 / 逐条冲突确认） | 📌 同上 |
| Issue 3（`.ref` 解码 / 非法路径不归「无法解析」） | 📌 同上 |
| Issue 4（父任务 B2 过早标记完成） | ✅ 已改父任务 checklist 为 `[ ]` + 注明裁剪 + 待 4 场景验证；此项不随迁移走 |
| R5（迁移 vs 手动键推导路径不一致，`catalog_label_for_dir` 与 `canonical_module_dir` 边界） | 📌 键推导分叉部分仅存于 `catalog_label_for_dir` 处理 `.ref` 父目录名时；如果删 `catalog_label_for_dir` 的 `.ref` 分支后手动路径不再用此函数 → R5 失去载体，一并移后置；否则仍需保留 helper 并补收敛建议 |

> **本独立审查的审查议题主体现已不在 B2 范围内**。主 REVIEW（`REVIEW-20260720-shared-module-registration.md`）保留原审查记录作为 B2 裁剪前的事实存证；裁剪后待人验通过的剩余议题仅：手动登记 set/clear service、CTk/Qt 右键 + 冲突不静默覆盖、B4 隔离。
>
> 后置 TASK `TASK-20260723-firmware-ref-migration.md` 若评估结论是 GO（重启自动化迁移），可从 git 历史捞回裁剪前代码，并把本独立审查的 Issue 1/2/3 连同原主 REVIEW 的 Issue 1 一并作为对其再次审查的输入起点。

## 核对结论（2026-07-20，原始审查阶段）

对独立审查的 4 项逐一独立验证（对照实际代码，未盲信）：**全部属实、诊断准确**。另发现审查**遗漏 1 项**（键推导路径不一致，R5）。P1（Issue 1/2/3）+ 遗漏项已修并补回归测试；Issue 4（流程）已改父任务勾选。

> 📌 上述结论已被 2026-07-23 范围调整覆盖：Issue 1/2/3 + R5 移走，仅 Issue 4 保留（已闭环）。

## 核对结论（2026-07-20）

对独立审查的 4 项逐一独立验证（对照实际代码，未盲信）：**全部属实、诊断准确**。另发现审查**遗漏 1 项**（键推导路径不一致，R5）。P1（Issue 1/2/3）+ 遗漏项已修并补回归测试；Issue 4（流程）已改父任务勾选。

## 问题描述

B2 为共享引用提供手动登记、`.ref` / `-同X` 迁移和 CTk / Qt 入口。实现必须保持 B4 隔离，只写 `型号配置.toml`，并满足单型号/多型号工作区、迁移预览选择、冲突逐条确认和异常线索容错。

## 处理方案

1. 手动登记从工作区内真实资产生成共享引用，并做路径、源型号 id、冲突校验。
2. 迁移服务扫描线索，预览后仅将用户选择的候选写入；相同引用跳过，冲突按条目决定覆盖或保留。
3. view model 作为服务与两套 UI 的唯一调用边界；B2 不实现 B3 展示或 B4 回源改动。

## 自动化门禁

```text
uv run python -m pytest src/fwasset/tests/test_shared_module_service.py src/fwasset/tests/test_shared_migration_service.py src/fwasset/tests/test_scheme_workbench_model.py src/fwasset/tests/test_workbench_panel_helpers.py src/fwasset/tests/test_firmware_catalog.py -m "not ui" -q --no-cov
-> 120 passed

uv run python -m pytest -m "not ui" -q
-> 377 passed, 52 deselected; coverage 87.35%
```

自动化门禁通过，但没有覆盖下列阻断路径；未运行 UI 或人工验证。

## 审查议题

### Issue 1（P1·阻断）：单型号根迁移会写入 `通用/型号配置.toml`

**文件：** `core/services/shared_migration_service.py:102-108`

扫描器将工作区相对路径的首段一律视为型号目录。单型号根下首段是 `通用` 或 `定制`，因而目标根被算为 `<workspace>/通用`，`apply_ref_migration` 随后向错误目录写入 `型号配置.toml`。工作台已支持“扫描根本身是一个型号目录”的布局，且 TASK 明确要求目标根不得落入 `通用/`。

**修复要求：** 识别单型号根并将目标根设为工作区根；增加单型号 `.ref` 扫描、写入目标和“不在通用目录建配置”的回归测试。

**核对：** ✅ 属实。`first=rel_parts[0]` 在单型号根下等于 `通用`/`定制`，目标根被算成 `ws/通用`。
**修复：** 新增 `_target_model_root(ws, rel_parts)`（首段为 `通用`/`定制` → 工作区根本身），扫描改用之。回归测试 `test_single_model_root_migration_target_is_workspace`（断言目标根=工作区根、`型号配置.toml` 不落 `通用/`）。
**状态：** ✅ 已修

### Issue 2（P1·阻断）：迁移 UI 未支持选择候选或逐条冲突确认

**文件：** `ui/workbench_panel.py:835-883`、`ui_qt/workbench_window.py:930-969`

两套预览对话框只显示文本，不保存可勾选的候选集合；点击“应用迁移”直接提交全部 `clues`。冲突发生在非冲突项已写入后，且 UI 只提供“是否全部覆盖”。这不符合 TASK 规定的预览分区、用户勾选确认及冲突逐条确认，用户无法保留部分冲突或取消部分非冲突写入。

**修复要求：** 服务/view model 接受选中的候选和每项冲突决策；两套 UI 显示可解析、无法解析、冲突分区，并逐项提供覆盖或跳过；补充非 UI 与双 UI 回归测试。

**核对：** ✅ 属实（UX 完整性缺口；service 层已支持逐条，UI 未暴露）。
**修复：** CTk `Listbox(selectmode=MULTIPLE)`（仅可写入项可勾选、默认全选，无法解析项灰显）；Qt `QListWidgetItem` 可勾选（ok 预勾、无法解析禁用）。`_apply` 只提交勾选候选；冲突**逐条** `askyesno`/`QMessageBox.question`（每模块单独覆盖/保留）。两套文件 `py_compile` 通过；交互行为待人工验证（UI，`@pytest.mark.ui` 不自动跑）。
**状态：** ✅ 已修（待人验交互）

### Issue 3（P1·阻断）：`.ref` 解码异常与非法路径不会成为“无法解析”预览项

**文件：** `core/services/shared_migration_service.py:144-190`

读取 `.ref` 只捕获 `OSError`。非 UTF-8 的历史中文文件会抛出 `UnicodeDecodeError` 并终止扫描，而不是列入“无法解析”。此外，绝对路径、`.`、`..` 路径段未被拒绝，可能被写成无效 `source_relative_path`。

**修复要求：** 把解码异常和非法路径转为 `unparseable` 候选，不写盘；增加非 UTF-8、绝对路径、`.` 与 `..` 的回归测试。

**核对：** ✅ 属实。`UnicodeDecodeError`（属 `ValueError`，非 `OSError`）会**崩掉整个扫描**。非法路径这半个：B1 解析器 resolve 时会拦 `..` 返回缺失（非安全洞），但会写出无效 ref，仍应拒。
**修复：** `read_text` catch 扩到 `(OSError, UnicodeDecodeError)` → 产出 `unparseable` 候选不崩；新增 `_clean_source_rel` 拒绝绝对路径 / `.` / `..` 段（`_parse_ref_content` 调用）。回归测试 `test_scan_non_utf8_ref_is_unparseable`、`test_scan_dotdot_ref_is_unparseable`。
**状态：** ✅ 已修

### Issue 4（P2·流程）：父任务 B2 过早标记完成

**文件：** `specs/active/TASK-20260714-config-takeover.md:378`

父任务已将 B2 标为 `[x]`，但当前任务仍有未关闭阻断项，且尚未人工验证。项目规则要求 UI 和核心流程改动在人工验证通过后才能标记完成和提交。

**修复要求：** 在阻断项关闭并完成人工验证前，B2 保持未完成或明确“待验收”；验收后再勾选。

**核对：** ✅ 属实（原为 `[x]` 带「待人工验证」注，仍违反人验前不标完成）。
**修复：** 父任务 B2 checklist 改回 `[ ]`，注「代码 + 二轮审查修复完成；**待人工验证 6 场景**后勾选并提交」。
**状态：** ✅ 已改（人验后再勾选）

### R5（审查遗漏·低）：迁移与手动登记的模块键推导路径不一致

**文件：** `core/services/shared_migration_service.py`（`catalog_label_for_dir`）vs `core/services/shared_module_service.py:140`（`canonical_module_dir(firmware_label)`）

独立审查**未发现**：迁移用 `catalog_label_for_dir(目录名)`（关键词子串）推 `target_module_key`，手动用 `canonical_module_dir(firmware_label)`。对 catalog 可识别模块两者收敛（如 `3D机芯板上` → `3D机芯板程序`，与 `firmware_label` 一致，测试 `test_manual_and_migration_key_converge` 已验）；仅当**资产 `firmware_label` ≠ 目录名映射标签**（catalog 未识别模块）时可能分叉，导致同物理模块经两路径写成两条 `shared_modules` 键，B4b「同模块单引用」失守。

**处置：** 已加收敛断言测试固定 catalog 模块行为；分叉仅存于 catalog 未识别的边界模块，属**低风险已记录**——B3/后续若引入更多非标模块再统一键推导。
**状态：** ✅ 记录 + 收敛测试（低风险边界留后续）

## 契约合规检查

| 契约项 | 结果 |
| --- | --- |
| 手动入口仅使用工作区内真实资产 | 通过：来源来自 `_all_assets`，服务再做路径校验 |
| 手动登记冲突不静默覆盖 | 通过：service 返回 `conflict`，UI 可覆盖或取消 |
| 取消共享不删除固件文件 | 通过：复用 B1 删除 TOML 条目，测试已覆盖 |
| B4 隔离，不修改回源逻辑 | 通过：方案模块逻辑未改，回归测试通过 |
| 共享仅写 `型号配置.toml`，不进索引或平台配置 | 通过 |
| 迁移目标根不落 `通用/` | ✅ 已修（Issue 1；`_target_model_root`） |
| 迁移候选选择与逐条冲突确认 | ✅ 已修（Issue 2；待人验交互） |
| 无法解析线索不抛且不写无效路径 | ✅ 已修（Issue 3；解码/`..`/绝对路径） |
| 人验前不标记 B2 完成 | ✅ 已改（Issue 4；父任务改回 `[ ]`） |
| 迁移/手动键推导一致（B4b 单引用） | ⚠️ catalog 模块收敛（R5 测试）；非标模块边界留后续 |

## 复审条件

1. ✅ 关闭 Issue 1-4 并补齐回归测试（+ R5 收敛测试）。
2. ✅ 重跑 `uv run python -m pytest -m "not ui" -q` → **381 passed, coverage 87.45%**；两套 UI 文件 `py_compile` 通过。
3. ⏳ 在测试副本完成 TASK 列出的 6 个 CTk / Qt 人工验证场景（**含新增迁移逐条选/逐条冲突交互**）——**待用户执行**。
4. ⏳ 通过后更新本审查记录、CHANGELOG、父任务状态，并按模板提交。

## 相关 Commit

| 哈希 | 描述 |
| --- | --- |
| 1a03706 | feat(core,ui): 共享手动登记入口（Phase B2） |
