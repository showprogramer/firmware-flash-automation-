# TASK-20260724：B4 共享 / 方案边界硬化收口

## 状态

| 项 | 状态 |
| --- | --- |
| 类型 | Phase B4 / B4b / B6 硬化收口 |
| 当前状态 | ✅ 已完成：实现、自动化与 Qt 人工验证通过（2026-07-24，场景 4/6/7/8） |
| 前置 | B3（`TASK-20260724-b3-shared-display`）已完成并人验；Qt-only |
| 父任务 | `specs/archive/TASK-20260714-config-takeover.md`（B4 / B4b / B6 专节已写死） |
| 分支 | `feature/pyside6-migration` |
| 验收界面 | Qt-only |

## Goal

硬化父任务 **B4 / B4b / B6** 契约，补齐 B3 未封死的缺口：方案回源路径在已登记 `shared_modules` 键时，**不得**把本型号保留本地副本当「通用」回源行；共享缺失不回落本地；人验场景 4 / 6 / 7 / 8 通过后勾掉父任务 Phase B 未勾项。

不新开产品能力：无 `mode`、无 `.ref`、无独立共享列表、不改四字段 schema。

## 范围边界

### 纳入

- `get_scheme_modules`：defaults 回源与 A4 唯一变体回源两处，若该 `module_key` 已有共享条目（hit **或** missing），则跳过 `_append_fallback`。
- 定制专属行不受共享压制。
- B4 / B4b / B6 自动化回归（含取消共享后方案可再回源本地）。
- Qt 冒烟必要时补断言；CHANGELOG / REVIEW / 父任务清单收口。
- Qt 人验：父任务场景 4、6、7、8。

### 不纳入

- Phase C `follow_default` / `pinned` / `mode`。
- `.ref` 迁移（已 NO-GO：`specs/archive/TASK-20260723-firmware-ref-migration.md`）。
- 共享且无本地副本时注入「幽灵模块行」（B3 已定：只装饰现有行）。
- 改 `型号配置.toml` / `平台配置.toml` 格式、`types.py`、DB schema、firmware CRUD。

## 契约来源（父任务已写死，本 TASK 不改语义）

1. **B4**：方案回源不读 `shared_modules`；显式共享不参与 `get_scheme_modules` 补洞；共享只在模块浏览/烧录路径可见。
2. **B4b**：有共享键 ⇒ 该模块 shared 有效；保留本地副本不删；方案页不得绕过共享状态把本地副本当回源；取消共享只删 toml。
3. **B6**：源未导入 / 路径无 / id 不符 →「共享来源缺失」；禁止静默补、禁止回落本地副本。

## 已确认缺口

`get_scheme_modules` 回源循环在 `_append_fallback` 前未检查共享键。结果：共享有效 + 本型号 `通用/` 仍有文件 + 方案无定制专属时，方案树仍会补出「通用」本地副本行——违反 B4b。

## 实施任务

### Task 1：方案回源跳过已共享模块键 `complexity: medium`

**复杂度理由：** 单关注点改 ViewModel 回源路径 + 若干回归；不动 schema / service 契约；含 UI 语义但改在 `ui_common`。

**Files:**

- Modify `src/fwasset/ui_common/view_models/scheme_workbench_model.py`

**验收：**

- defaults 回源与 A4 回源：`resolve_shared_module(...) is not None`（有条目，不论 hit/missing）→ 不 `_append_fallback`。
- 方案有定制专属时仍显示定制专属。
- 方案树不出现「共享自 …」角标行。

### Task 2：B4 / B4b / B6 回归测试 `complexity: medium`

**复杂度理由：** 多场景边界（共享+本地、missing、取消恢复、定制优先）；单测文件、无 schema。

**Files:**

- Create `src/fwasset/tests/test_b4_shared_scheme_boundary.py`（或扩 `test_scheme_workbench_model.py`）
- 必要时扩 `src/fwasset/tests/test_b3_shared_display.py`

**必盖用例：**

- 有共享 + 有本地副本 + 方案无定制 → 方案树**无**该模块行。
- 有共享 + 无本地 + 方案无定制 → 方案树仍无该模块。
- 有共享 + 方案有定制专属 → 仍显示定制专属。
- 共享 missing + 有本地副本 → 模块列表 `shared_missing`、`effective_asset is None`；方案树亦不回落本地。
- 取消共享后 → 方案可再回源本地通用；列表恢复 `local`。

### Task 3：Qt 文案/禁用路径冒烟（仅必要时） `complexity: low`

**复杂度理由：** 确认既有 smoke 即可；最多补断言，不新增 UI。

**Files:**

- Modify `src/fwasset/tests/test_qt_smoke.py`（仅缺口时）

**验收：**

- 方案树选中/展示不含共享角标误导；不新增独立 UI。

### Task 4：文档收口与人验 `complexity: low`

**复杂度理由：** CHANGELOG / REVIEW / 父任务勾选 + 人验记录；无核心 API 变更。

**Files:**

- Modify `docs/CHANGELOG.md`
- Create `docs/code-review/REVIEW-20260724-b4-shared-scheme-boundary.md`
- Modify `specs/archive/TASK-20260714-config-takeover.md`（勾选 B4 行，人验通过后）

**验收：**

- 自动化门禁通过（coverage ≥ 80%）。
- Qt 人验 4/6/7/8 通过并记录日期。
- 用户确认「验证通过」后才 commit。

## Definition of Done

- [x] Task 1–2 测试先行实现并通过。
- [x] 方案回源对已共享键压制本地副本（自动化覆盖）。
- [x] B6 缺失不回落、取消共享恢复本地（自动化覆盖）。
- [x] Qt-only 自动化回归通过：358 passed，coverage 93.47%。
- [x] Qt 人工验证通过并记录日期：2026-07-24（场景 4 / 6 / 7 / 8）。
- [x] CHANGELOG、审查记录、本 TASK、父任务清单已收口。
- [x] 人工验证通过后按 `docs/COMMIT_TEMPLATE.md` 提交。

## 人工验证场景（Qt-only，对应父任务 4 / 6 / 7 / 8）

1. **共享可见（场景 4）**：有效共享显示「共享自 …」，可打开来源（B3 不回退）。
2. **来源缺失（场景 6）**：显示「共享来源缺失」，不静默用本地副本。
3. **方案不吃共享（场景 7）**：已登记共享、方案无定制、本型号通用因共享被压制 → 方案上该模块**缺失**；无「共享自 …」回源行。
4. **本地副本（场景 8）**：设共享后本地文件仍在盘；列表/烧录只显共享源；取消共享后本地恢复且文件未删；取消后方案可再回源该本地通用。

## 相关文档

- 父任务：`specs/archive/TASK-20260714-config-takeover.md`
- B3：`specs/archive/TASK-20260724-b3-shared-display.md`
- `.ref` 后置：**已关闭** → `specs/archive/TASK-20260723-firmware-ref-migration.md`
