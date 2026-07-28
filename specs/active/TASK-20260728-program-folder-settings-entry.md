# TASK-20260728：程序文件夹设置入口与首次配置闭环（草案）

## 状态

| 项 | 状态 |
| --- | --- |
| 类型 | UI 工作流 + 配置入口完善 |
| 当前状态 | ✅ 已完成；冻结 exe 人工验证于 2026-07-28 通过，待提交 |
| 前置 | `TASK-20260728-config-usb-simplification.md` 的配置迁移已实施；REVIEW Issue 1–6 已关闭，Issue 7 待人工验证后提交 |
| 父任务 | `TASK-20260728-config-usb-simplification.md`（原 Task 2 的“后期统一收入设置”决策落地） |
| 分支 | `feature/pyside6-migration` |

---

## 背景与目标

当前冻结 exe 在 `root_dir` 未配置时会显示 `SetupWizard`。用户点击“跳过”可进入主界面，但：

1. 跳过不写 config，下一次启动仍会显示向导；
2. 向导文档字符串称可在“设置页”继续配置，但应用目前没有设置页或重新打开向导的入口；
3. `root_dir` 被标注为必填，但“完成配置”当前没有阻止空路径写入；
4. 产品方向已明确：未来日常操作是软件内 CRUD，读取外部程序文件夹将退化为首次导入、软件外修改后的低频辅助操作。因此用户界面不能暴露“重建索引 / 修复索引”等开发术语。

本 TASK 的目标是补齐“首次跳过 → 之后能明确配置”的用户闭环，并建立可长期承载程序文件夹配置的应用级“设置”入口。

---

## 关键决策（草案）

| # | 决策 |
| --- | --- |
| A | 在 `FluentWindow` 的应用级导航新增“设置”；现有“程序资产工作台”继续作为资产浏览与操作页面。 |
| B | 设置页首个区块命名为“程序文件夹”，展示并允许修改“固件根目录”和“工具根目录”。 |
| C | 用户从设置页修改路径时复用 `SetupWizard`；向导应预填当前配置值，避免用户重复输入。 |
| D | “完成配置”必须要求固件根目录非空且是已存在目录；“跳过”仍允许不写 config。 |
| E | 用户可见文本使用“重新读取程序文件夹”，不使用“扫描目录”“重建索引”“修复索引”等实现术语。该按钮始终读取当前已配置的固件根目录；切换位置只能通过设置完成。此 TASK 不改变按钮的最终页面位置。 |
| F | 不新增 `setup_dismissed` 或其他向导状态字段；`config.toml` 继续只保留 `[paths]`。 |
| G | 未来“新增程序 / 编辑 / 复制为新版本 / 归档”等 CRUD 及“扫描目录”从主工作台降级为低频入口的重构，单独立项，不纳入本 TASK。 |

---

## 范围

### 包含

- 首次向导的跳过文案、必填校验与路径预填；
- 新增应用级“设置”导航页；
- 设置页中的程序文件夹配置入口；
- 同一会话内完成配置后 reload settings，并自动读取新配置的根目录；
- 未配置根目录时工作台给出可达的“前往设置”提示；
- README、REVIEW 状态与自动化/人工验证记录同步。

### 不包含

- 完整 CRUD 页面、右侧资产详情面板或批量编辑；
- 改变目录树、SQLite 单工作区语义或 schema；
- 为“已跳过”新增配置字段；
- 面向烧录员暴露“重建索引 / 修复索引”等内部概念；
- 立即删除或迁移当前左侧的“扫描目录”按钮。该按钮的产品定位留给后续 CRUD TASK 决定。

---

## 用户流程（验收基线）

### A. 首次启动并完成配置

```text
冻结 exe 无 config
→ 显示初始配置向导
→ 选择存在的固件根目录（工具根目录可留空）
→ 完成配置
→ 写入 %APPDATA%\fwasset\config.toml
→ 进入主界面并自动读取该程序文件夹
```

### B. 首次启动选择跳过

```text
冻结 exe 无 config
→ 显示初始配置向导
→ 跳过
→ 进入主界面
→ 明确看到“尚未配置程序文件夹”与“前往设置”入口
→ 可随时进入设置完成配置
```

### C. 已配置用户修改根目录

```text
设置 → 程序文件夹 → 更改固件根目录
→ 向导预填当前路径
→ 选择另一个存在目录并完成配置
→ 明确提示“将切换到新的程序文件夹并重新读取列表”
→ 写入 config、刷新 settings、自动读取新根目录
```

---

## 子任务拆解

### Task 1：使首次配置向导可复用且语义准确  `complexity: medium` ✅ 已完成

**复杂度理由：** 涉及现有 Qt 向导、配置写入和 UI 校验，多文件但单一工作流；不改 schema、service 返回结构或数据库。

**Files:**

- Modify `src/fwasset/ui_qt/setup_wizard.py`
- Modify/Add `src/fwasset/tests/` 中与向导配置写入、路径校验相关的测试

**实施：**

1. 向导说明补充：
   > 跳过不会保存配置，下次启动仍会显示此向导。也可进入主界面的“设置”完成配置。
2. `SetupWizard` 接受可选初始 `root_dir` / `tool_root`，并在设置页打开时预填。
3. “完成配置”前校验固件根目录：非空、存在且为目录；失败时在字段附近显示中文提示，不写 config、不关闭对话框。
4. “跳过”继续 `reject()`，不创建空 config。
5. 工具根目录仍可选；若填写则同样校验其目录有效性。

**验收：** 空根目录、无效根目录不能完成配置；有效根目录可写入 config；设置页重新打开向导时两个字段与当前配置一致；跳过语义对用户可见且准确。

---

### Task 2：新增应用级“设置 → 程序文件夹”入口  `complexity: high` ✅ 已完成

**复杂度理由：** 跨 `FluentWindow` 应用导航、设置界面、向导复用、settings reload 与自动读取流程；涉及 UI 与配置即时生效，必须双路径人验。

**Files:**

- Create `src/fwasset/ui_qt/settings_interface.py`（或与现有 UI 命名一致的设置页面模块）
- Modify `src/fwasset/ui_qt/workbench_window.py`
- Modify `src/fwasset/core/settings.py`（仅当需要抽取安全的 reload/读取帮助函数时）
- Modify/Add `src/fwasset/tests/` 中与 settings reload、路径切换相关的测试

**实施：**

1. 在 `QtWorkbenchWindow` 添加第二个 `addSubInterface(...)`：图标使用现有 QFluentWidgets 的设置图标，标题为“设置”。
2. 设置页新增“程序文件夹”区块：
   - 固件根目录、工具根目录：分别显示当前路径；
   - 共用“更改…”按钮打开预填路径的向导，一次编辑两项；
   - 路径未配置时显示明确空状态，而不是技术错误。
3. 点击“更改…”复用 Task 1 的向导；用户保存后：
   - 写入 `CONFIG_PATH`；
   - reload settings；
   - 刷新设置页显示；
   - 自动读取新的固件根目录。
4. 切换根目录前提示：
   > 将切换到新的程序文件夹并重新读取程序列表。当前列表会更新为新位置的内容。
5. 用户界面不显示“索引”“数据库”“重建”“修复”等实现术语。

**验收：** 已配置用户不再需要重启或等待首次向导，也能在设置页修改根目录；保存后资产列表切换到新根；工具根目录可单独修改；配置失败时旧配置与当前资产列表不被破坏。

---

### Task 3：为跳过用户提供工作台内的可达提示  `complexity: medium` ✅ 已完成

**复杂度理由：** 修改工作台空状态/提示区与导航跳转，单一 UI 关注点；需确保不遮挡已有缓存资产或扫描状态。

**Files:**

- Modify `src/fwasset/ui_qt/workbench_window.py`
- Modify/Add `src/fwasset/tests/` 中相关 ViewModel 或 UI 行为测试（如可测试）

**实施：**

1. 当当前 settings 没有 `root_dir` 时，在工作台显示非阻断提示：
   > 尚未配置程序文件夹。请前往“设置”完成配置。
2. 提供“前往设置”按钮，跳转到 Task 2 新增的设置页。
3. 不阻止用户查看已有缓存资产、日志或其他只读界面；不自动清空缓存。
4. 配置保存成功并开始读取后，移除该提示并显示正常读取/加载状态。
5. 工作台“重新读取程序文件夹”只读取当前已配置的根目录；未配置时跳转设置，不再允许临时选择其他目录造成下次启动根目录不一致。

**验收：** 用户首次跳过后无需退出应用，即能找到并完成配置；提示不会在已有有效配置时出现，也不会遮挡现有资产列表和烧录操作。

---

## 自动化验证与人工验证

### 自动化

```powershell
uv run python -m pytest src/fwasset/tests/test_qt_smoke.py::test_setup_wizard_prefills_validates_and_writes_config src/fwasset/tests/test_qt_smoke.py::test_settings_interface_shows_paths_and_emits_configure_request src/fwasset/tests/test_qt_smoke.py::test_workbench_missing_configuration_notice_opens_settings src/fwasset/tests/test_qt_smoke.py::test_settings_completion_reloads_and_reads_new_root src/fwasset/tests/test_qt_smoke.py::test_re_read_uses_configured_root_without_folder_picker src/fwasset/tests/test_qt_smoke.py::test_re_read_without_config_opens_settings -q --no-cov
# 6 passed

uv run python -m pytest -m "not ui" -q --no-cov
# 357 passed, 22 deselected

.\scripts\test.ps1
# 381 passed，coverage 94.33%
```

新增/调整的测试至少覆盖：

- 空根目录、无效根目录不能写 config；
- 有效根目录可写 config；
- 设置页打开向导时路径预填；
- 设置页变更根目录后 settings reload 与自动读取的调用路径；
- 跳过不写 config；
- 无 root 时显示“前往设置”提示；
- “重新读取程序文件夹”只使用已配置根目录，未配置时进入设置。

### 人工验证结果

- 2026-07-28：用户确认冻结 exe 场景验证通过；包含首次配置、跳过后前往设置、设置中切换根目录，以及“重新读取程序文件夹”只读取已配置根目录的行为。

### 人工验证（冻结 exe，必须）

1. 无 AppData config：完成配置 → 进入工作台 → 自动读取程序文件夹；
2. 无 AppData config：跳过 → 进入工作台 → 前往设置 → 完成配置 → 自动读取；
3. 已有 config：启动不弹向导；设置页显示当前路径；
4. 设置页切换到另一测试程序文件夹：确认提示 → 列表更新为新根内容；
5. 填空路径、无效路径、无权限路径：不写 config，界面给出中文提示；
6. 检查所有用户可见文字，不出现“重建索引”“修复索引”“数据库”等术语。

---

## 文档与收口

- Modify `docs/README.md`：补“设置 → 程序文件夹”重新配置入口说明；
- Modify `docs/CHANGELOG.md`：在 `Unreleased` 记录首次配置与设置入口改进；
- Modify `docs/code-review/REVIEW-20260728-config-usb-simplification.md`：Issue 8 在 TASK 开工后改为“已转入本 TASK”；
- 三个子任务、自动化验证与冻结 exe 人工验证均已完成；可按 `AGENTS.md` 提交。
