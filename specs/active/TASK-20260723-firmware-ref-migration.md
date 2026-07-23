# TASK-20260723: `.ref` / `-同X` 历史线索的一次性迁移（后置）

> **状态：占位骨架，未开工。** 实施前需先 B3 落地、烧录员真正用上共享后，再评估是否仍需自动化迁移——若现场关系个位数、手登记更快，本 TASK 可直接关闭并归档。

## 状态

| 项 | 状态 |
| --- | --- |
| 类型 | 后置迁移 TASK（从父任务 `TASK-20260714` B2 拆出） |
| 当前状态 | 🟡 **占位骨架**，未开工；等待 B3 落地后再评估 |
| 父任务 | `specs/active/TASK-20260714-config-takeover.md`（B2 裁剪残余） |
| 前置（代码） | **B3 落地**（角标 / 可烧 / 缺失灰掉 / 列表只显共享来源）—— 在那之前做迁移属优先级倒置 |
| 分支 | 实施前定 |

## 起源

原本 `TASK-20260720` Phase B2 计划含 `.ref` / `-同X` 一次性迁移入口（读线索 → 预览 → 确认 → 写正规引用；幂等；不静默覆盖）。代码甚至已写完并通过门禁，但 2026-07-23 用户讨论后确认砍掉，理由：

1. `-同X` / `.ref` 现场仍是**占位、未整理完**（父任务约束 4），给不稳定输入喂严格解析器会反复返工。
2. **优先级倒置**：先做完"历史目录整理工具"再让烧录员看不到共享效果，是"设置方式奇怪"的根。
3. 个位数关系手登记比写迁移器更快。

裁剪的代码（`shared_migration_service.py` / `scan_ref_clues` / `apply_ref_migration` / `RefClue` / `preview_ref_migration` view model API / `.ref 导入`UI 按钮 + 预览对话框 / `filter_chosen_for_conflict` helper / 三个 filter 测试 / `catalog_label_for_dir` 的 `.ref` 父目录映射分支）按 `TASK-20260720`「回退清单」删除后，整建制搬到此 TASK 重新评估。

## 待评估的核心问题

实施前必须先回答：**真的需要自动化迁移吗？**

| 评估项 | 判断 |
| --- | --- |
| 现场真实关系条数 | 至 B3 落地后，烧录员已用手动登记多少条共享？若个位数 → 本 TASK 直接归档，手登记比迁移器快 |
| `.ref` / `-同X` 线索格式稳定性 | 父任务约束 4 原文"占位、未整理完"是否仍成立？现场是否已固化样例？ |
| 解析失败率 | 实施前用只读脚本扫一遍现场，统计"可解析 / 无法解析 / 冲突"比例；失败率超 20% → 不值得自动 |
| 反复触发成本 | 一次性迁移本应一次完成；若现场目录会持续重组，迁移需重跑 → 不如纯手动 |

若以上四项评估结论是"自动化收益 < 维护迁移器的成本"，本 TASK 关闭并归档；否则按下方计划实施。

## 范围（若评估通过才实施）

- **只读扫描**：`scan_ref_clues(workspace_root) -> list[RefClue]` 扫描 `.ref` 文件 / `-同L50S` 命名线索 → 候选引用预览（目标型号 / 目标模块 / 拟写 `source_model_id` / `source_relative_path` / 能否解析命中）。**不写盘**。
- **幂等写入**：`apply_ref_migration(clues, overwrite=False)` → 目标模块无引用 → 写；已存在且相同 → 跳过；不同 → 计冲突，由 UI 让用户逐条选。
- **不静默覆盖**：冲突在 UI 拦截。
- **可写未导入源引用**：迁移可生成"源尚未在工作区"的引用 → B1 解析即 `source_not_imported`，直至用户扫入源型号。
- **无法解析线索列入预览**：不静默丢弃，UI 单列"无法解析"区供人工核对。
- **复用 B2 已删除的代码**：若本 TASK 重新启动，可直接从 `TASK-20260720` 裁剪前的 git 历史里捞回 `shared_migration_service.py` / `filter_chosen_for_conflict` / `catalog_label_for_dir` 分支 —— 但必须重新评估解析规则是否仍匹配现场。

## 不可变约束（从父任务继承）

1. `.ref` 是一次性线索**非协议**，仅迁移读；之后业务**只认** `型号配置.toml` 正规引用（父任务约束 4）。
2. 落盘只碰 `型号配置.toml`；不碰 `平台配置.toml` / `save_platform_config`；不写 `通用/`。
3. 不移动 / 不复制 / 不删除任何 bin/hex（属 firmware-crud TASK）。
4. 不静默覆盖；幂等。
5. 不碰方案回源 / B4；不引入 `mode`。
6. 不修改 `types.py` / 数据库 schema。
7. 不自动启动 UI、不自动跑 `@pytest.mark.ui`；不在 `D:\按摩器程序` 上做破坏性写入。

## Files Likely to Change（若实施）

| 操作 | 路径 | 目的 |
| --- | --- | --- |
| Create | `src/fwasset/core/services/shared_migration_service.py` | `scan_ref_clues` / `apply_ref_migration` |
| Modify | `src/fwasset/ui/view_models/scheme_workbench_model.py` | `preview_ref_migration` / `apply_ref_migration` API |
| Modify | `src/fwasset/ui/workbench_panel.py` | CTk侧栏「从 .ref 导入共享…」按钮 + 预览对话框 |
| Modify | `src/fwasset/ui_qt/workbench_window.py` | Qt 对称 |
| Modify | `src/fwasset/ui/workbench_helpers.py` | `filter_chosen_for_conflict`（跨型号同名模块冲突过滤纯函数） |
| Modify | `src/fwasset/core/firmware_catalog.py` | `catalog_label_for_dir`（`.ref` 父目录名 → catalog label 映射） |
| Create | `src/fwasset/tests/test_shared_migration_service.py` | 迁移服务测试 |
| Modify | `src/fwasset/tests/test_workbench_panel_helpers.py` | 三个 `test_filter_chosen_for_conflict_*` |
| Modify | `src/fwasset/tests/test_firmware_catalog.py` | `catalog_label_for_dir` 测试 |

> 以上代码在 `TASK-20260720` 裁剪前已实现并过门禁；若本 TASK 启动，可从裁剪前的 git 状态捞回（裁剪动作本身会形成一次可追溯的删除 commit）。

## 前置：实施前必做

1. **重新读现场样例**：B3 落地后扫一遍 `D:\按摩器程序`，更新对 `.ref` / `-同X` 格式的认知，确定解析规则。
2. **只读预扫描**：写一个独立脚本统计真实关系条数与失败率（不集成进应用）。
3. **评估结论记录**：在本 TASK 顶部加一节「评估结论」写明 GO / NO-GO；若 NO-GO 则关闭归档。

## Open Questions（待评估后再回答）

1. `.ref` / `-同X` 线索的确切格式与解析规则（现场样例已稳定？格式扩展了几次？）。
2. 跨型号同名模块冲突是否还需"逐条确认"（B2 原计划是全量「是」覆盖；若现场关系数小，逐条人工点更直观）。
3. `catalog_label_for_dir` 是否仍按 `机芯版→机芯板` 归一规则？

---

## Definition of Done

- [ ] 实施前评估 "是否仍需自动化迁移" 写明结论；NO-GO 则关闭归档，不动代码。
- [ ] 若 GO：`scan` 只读；`apply` 幂等；冲突逐条确认；无法解析不丢；可写未导入源引用。
- [ ] 不碰 B4 / 不引入 `mode` / 不删文件 / 不碰 `平台配置.toml`。
- [ ] UI 双壳（CTk + Qt）迁移预览对话框文案一致。
- [ ] `pytest -m "not ui"` 通过且 coverage ≥ 80%；人验通过后提交。