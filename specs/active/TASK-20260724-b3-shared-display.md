# TASK-20260724：B3 共享模块展示与烧录候选

## 状态

| 项 | 状态 |
| --- | --- |
| 类型 | Phase B3 UI 任务 |
| 当前状态 | ✅ 已完成：实现、自动化回归与 Qt 人工验证通过（2026-07-24） |
| 前置 | B2 共享登记已完成；Qt-only 清理已完成；CTk 不再支持 |
| 设计状态 | 已在本 TASK 内确认；正式任务文档位于 `specs/active/` |
| 验收界面 | Qt-only |

## Goal

将 B2 已落盘的共享引用接入 Qt 工作台展示和烧录候选：有效共享显示“共享自 …”并使用来源资产；来源缺失显示“共享来源缺失”并禁用打开/烧录；不回落本地副本，不影响 B4 方案回源。

## 范围边界

### 纳入

- ViewModel 统一解析 `local` / `shared_hit` / `shared_missing` 状态；三态只用于内部数据，不创建独立共享 UI。
- Qt 数据网格沿用现有模块行，仅增加共享来源角标；双击该现有模块行打开解析后的来源目录。
- 有效共享来源作为当前选中资产和烧录候选。
- 缺失共享来源禁用打开和烧录，不跨型号搜索、不回落本地副本。
- 目标型号本地副本保留在磁盘，但共享有效时不与来源形成第二个有效候选；取消共享后同一模块行恢复本地资产。
- 不新增共享模块专区、独立共享列表或额外模块名称。
- Qt 自动化测试、B3 人工验证记录和 CHANGELOG/审查文档同步。

### 不纳入

- 不修改 B2 四字段语义、`型号配置.toml` 格式、`平台配置.toml` 或数据库 schema。
- 不实现 `.ref` 导入、自动猜测、`mode`、follow-default 或 pinned。
- 不改变方案回源和 B4/B4b 语义。
- 不恢复或维护 CTk。

## 实施任务

### Task 1：共享展示状态与 ViewModel 行模型 `complexity: high`

**复杂度理由：** 跨 ViewModel、资产解析和 Qt 行选择映射；需要同时处理命中、缺失、本地副本覆盖及 B4 隔离。

**Files:**

- Modify `src/fwasset/ui_common/view_models/scheme_workbench_model.py`
- Modify/add related tests under `src/fwasset/tests/`

**验收：**

- 共享引用统一调用 `resolve_shared_module()`。
- 命中、缺失、本地三态可稳定区分。
- 方案模块树不消费共享展示状态。

### Task 2：Qt 展示与打开来源 `complexity: medium`

**复杂度理由：** 单一 Qt 数据网格交互改动，涉及角标、路径映射和缺失态禁用，不改 core 契约。

**Files:**

- Modify `src/fwasset/ui_qt/data_grid.py`
- Modify `src/fwasset/ui_qt/workbench_window.py`
- Modify `src/fwasset/ui_common/workbench_helpers.py`
- Add Qt smoke tests

**验收：**

- 有效共享显示“共享自 …”。
- 现有模块行双击打开解析后的共享来源目录。
- 现有模块行显示“共享来源缺失”，双击不打开。

### Task 3：烧录候选收敛 `complexity: high`

**复杂度理由：** 影响 PanelHost 当前选中资产和四类操作面板；必须保证共享命中使用来源资产、缺失态不可烧且不改变普通本地资产行为。

**Files:**

- Modify `src/fwasset/ui_qt/operation_panels/host_types.py`
- Modify `src/fwasset/ui_qt/workbench_window.py`
- Modify related operation-panel tests

**验收：**

- `shared_hit` 返回来源资产/变体。
- `shared_missing` 不产生烧录候选并进入禁用路径。
- 普通本地资产和 B4 方案回源行为不变。

### Task 4：Qt-only 回归与人工验收 `complexity: medium`

**复杂度理由：** 自动化覆盖、测试副本三态场景和文档收口；不新增数据契约，但包含 UI 人工验收。

**Files:**

- Modify `docs/CHANGELOG.md`
- Modify B3 review/migration records
- Add/update `docs/code-review/REVIEW-20260724-b3-shared-display.md`

**验收：**

- 自动化测试通过，coverage ≥ 80%。
- Qt 人工验证：有效共享、目标本地副本覆盖、来源缺失、方案隔离。
- 用户确认“验证通过”后才提交。

## Definition of Done

- [x] Task 1–3 测试先行实现并通过。
- [x] Qt 显示、打开来源和烧录候选符合三态语义（自动化覆盖）。
- [x] B4 方案回源隔离测试通过。
- [x] Qt-only 自动化回归通过：353 passed，coverage 93.36%。
- [x] Qt 人工验证通过并记录日期：2026-07-24。
- [x] CHANGELOG、审查记录和本 TASK 已收口。
- [x] 人工验证通过后按 `docs/COMMIT_TEMPLATE.md` 提交。

## 人工验证场景（Qt-only）

1. 有效共享：显示“共享自 …”，双击打开来源目录，一键烧录使用来源资产。
2. 本地副本覆盖：目标型号同模块本地文件存在时，列表/烧录只显示共享来源；取消共享后本地文件恢复。
3. 来源缺失：来源路径无效或 ID 不匹配时，显示“共享来源缺失”，双击和烧录均不可用，不回落同名本地副本。
4. 方案隔离：方案页不出现共享角标或跨型号来源。

## 设计说明

`docs/superpowers/specs/2026-07-24-b3-shared-display-design.md`
