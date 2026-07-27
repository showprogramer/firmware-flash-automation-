# TASK-20260724：Qt 唯一支持界面清理（B3 前置）

## 状态

| 项 | 状态 |
| --- | --- |
| 类型 | B3 前置重构任务 |
| 当前状态 | ✅ 已完成：Qt-only 实现、自动化回归、Qt 人工验收与文档收口完成（2026-07-23） |
| 前置 | B2 已完成：代码 `1a03706`；文档收口 `5e8f5be`；Qt 人工验证 3 场景通过 |
| 目标 | Qt 作为唯一受支持界面，移除 CTk 运行入口、依赖与专属代码 |
| 后续 | 完成后进入 B3 共享展示；B3 不再安排 CTk 人工验证 |

## Goal

将应用从 CTk / Qt 双界面并行状态收敛为 Qt-only：默认启动直接进入 PySide6 界面，Qt 继续复用核心服务和工作台逻辑，CTk 专属代码、依赖、测试和旧入口文档全部移除或改写。

## 范围边界

### 纳入

- `app.py` 默认入口切换到 `ui_qt`。
- 移除 `FWASSET_UI=qt` 作为必要开关；保留该变量的兼容行为或删除，按 Task 1 实施结果统一处理。
- 将 Qt 仍依赖的共用 ViewModel 与纯逻辑助手迁到独立模块位置。
- 移除 `customtkinter` 依赖、CTk 界面、CTk 专属测试和旧启动文档。
- 将 B2/B3 人工验收统一为 Qt。

### 不纳入

- 不修改 `core/` 业务服务契约、数据库 schema、固件目录、TOML 数据格式。
- 不改变 B2 共享关系的四字段语义。
- 不在本任务实现 B3 的共享角标、来源打开、缺失态或烧录候选收敛；这些由独立 B3 任务完成。
- 不删除 Qt 使用的共享 ViewModel、助手函数或核心操作面板逻辑。

## 现状约束

- 当前 `src/fwasset/app.py` 默认导入 `fwasset.ui.shell`，只有 `FWASSET_UI=qt` 才启动 Qt。
- 历史基线：Qt 曾从 `fwasset.ui.view_models.*` 和 `fwasset.ui.workbench_helpers` 导入共用逻辑；现已迁移至 `ui_common/`。
- 历史基线：`pyproject.toml` 曾声明 `customtkinter`；现已移除依赖、旧壳及 CTk 专属测试。
- `src/fwasset/ui/` 不能整体删除，必须先迁出 Qt 依赖的共用部分。

## Definition of Done

- [x] `uv run fwasset` 默认启动 Qt，不依赖环境变量。
- [x] `customtkinter` 不再出现在运行依赖中；安装依赖不拉取 CTk。
- [x] Qt 不再从 CTk 专属模块导入任何内容。
- [x] CTk 专属目录、入口、测试和文档已删除或改写；源码不再导入 CTk。
- [x] 共享 ViewModel、纯逻辑助手和 Qt 所需操作面板仍可正常导入。
- [x] B2 的 Qt 3 个人工场景重新通过：手动登记、冲突覆盖、取消不删本地文件（2026-07-23）。
- [x] B3 后续任务明确只验 Qt，不再要求 CTk 场景。
- [x] `uv run python -m pytest -m "not ui" -q` 通过且 coverage ≥ 80%（canonical gate：350 passed，coverage 93.34%）。
- [x] Qt 相关测试通过（20 passed，1 warning）；canonical gate `scripts/test.ps1` 通过（350 passed，1 warning）。
- [x] `docs/CHANGELOG.md`、迁移说明、配置接管 TASK 和审查记录已同步 Qt-only 结论。
- [x] 人工验证通过后按模板提交；本次人工验证由用户于 2026-07-23 确认通过。

---

### Task 1：Qt 默认入口与依赖切换  `complexity: medium`

**复杂度理由：** 修改应用入口、项目依赖和启动文档；不动核心服务，但属于 UI 入口变更，需要 Qt 启动验证。

**Files:**

- Modify `src/fwasset/app.py`
- Modify `pyproject.toml`
- Modify `src/fwasset/tests/test_ui_reactor_entry.py`
- Modify startup instructions in `docs/README.md` and related active task docs

**验收：**

- `uv run fwasset` 直接进入 Qt。
- `FWASSET_UI=qt uv run fwasset` 不产生第二套行为分支；若保留变量，只作为兼容别名。
- `customtkinter` 从项目运行依赖与依赖锁定结果中移除。

### Task 2：迁移 Qt 共用逻辑  `complexity: high`

**复杂度理由：** Qt 当前依赖 `ui/view_models` 与 `ui/workbench_helpers`；需要跨包移动公共模块、同步多处导入和测试，涉及 UI 与 ViewModel 边界。

**Files:**

- Move or split `src/fwasset/ui/view_models/scan_state_model.py`
- Move or split `src/fwasset/ui/view_models/scheme_workbench_model.py`
- Move or split `src/fwasset/ui/workbench_helpers.py`
- Modify imports in `src/fwasset/ui_qt/`
- Modify related tests under `src/fwasset/tests/`

**验收：**

- Qt 不再依赖 CTk 包名或 CTk UI 模块。
- ViewModel 的公开方法和 B2 共享登记行为不变。
- B4 隔离测试、Qt smoke 测试与共享登记 service 测试继续通过。

### Task 3：移除 CTk 专属实现  `complexity: high`

**复杂度理由：** 涉及旧 UI 壳、面板、设计令牌、CTk 测试和文档的批量清理；需确保没有 Qt 依赖被误删，属于跨目录 UI 重构。

**Files:**

- Delete CTk-only files under `src/fwasset/ui/` after Task 2 完成
- Delete or rewrite CTk-only tests, including CTk app smoke tests and CTk source-structure assertions
- Remove CTk-specific documentation and migration wording

**验收：**

- 旧 CTk shell、panel、operation panel 和设计令牌不再被打包或导入。
- `rg -n "customtkinter|ctk\." src/fwasset` 只返回允许保留的历史说明；若无兼容代码则应无结果。
- Qt 应用、Qt 操作面板、工作台和共享登记入口均可导入。

### Task 4：Qt-only 回归与任务收口  `complexity: medium`

**复杂度理由：** 以 Qt 自动化、3 个 B2 人工场景和文档收口为主；不新增业务逻辑，但包含 UI 入口验收与发布记录。

**Files:**

- Verify `src/fwasset/tests/test_qt_smoke.py`
- Verify B2 shared registration tests
- Modify `docs/CHANGELOG.md`
- Modify `specs/active/TASK-20260714-config-takeover.md`
- Create or update B3 task to state Qt-only acceptance

**验收步骤：**

1. 运行非 UI 全套测试与 Qt smoke 测试。
2. 使用 Qt 测试副本完成 B2 三个场景。
3. 验证默认启动、扫描、工作台、操作面板、共享登记和取消共享。
4. 用户已于 2026-07-23 回复验证通过；已勾选本任务、更新 CHANGELOG 和审查记录，现按模板提交。

## 人工验证记录\n\n- 日期：2026-07-23\n- 界面：Qt-only 工作台\n- 结果：B2 三场景全部通过——首次登记、冲突选择“否/是”、取消共享不删除本地文件且文件大小/修改时间不变。\n\n## 回滚

- Task 1–3 分别提交，任何一步失败可回退到上一个 Qt 可启动提交。
- 不修改固件目录与用户配置；回滚只涉及代码、依赖和文档。
- 若发现 Qt 仍依赖 CTk 共用模块，停止删除，先补完 Task 2 的迁移。

## 相关文件

- `specs/active/TASK-20260720-shared-module-registration.md`
- `specs/active/TASK-20260714-config-takeover.md`
- `specs/archive/TASK-20260723-firmware-ref-migration.md`（`.ref` 迁移已 NO-GO 关闭）
- `docs/code-review/archive/REVIEW-20260720-shared-module-registration.md`
