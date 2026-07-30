# TASK-20260729：设置页 UI 重做与工作台重复入口清理

## 状态

| 项 | 状态 |
| --- | --- |
| 类型 | UI 布局重做 + 重复入口清理 |
| 当前状态 | ✅ 已完成 |
| 前置 | `TASK-20260728-program-folder-settings-entry.md` 已完成（`a8f3691`），设置页与左侧导航入口已存在 |
| 父任务 | 无（`TASK-20260728-program-folder-settings-entry.md` 的收尾优化） |
| 分支 | `feature/pyside6-migration` |
| 完成 commit | `61d763e`（src）、`318e4ac`（docs 归档） |

---

## 背景与目标

`TASK-20260728-program-folder-settings-entry.md` 落地了设置页与配置闭环，功能可用，但留下两个 UI 问题：

1. **重复入口**：左侧导航已有常驻「设置」，工作台主区顶部的未配置提示条仍带一个「前往设置」按钮。同一目的地两个入口，且提示条占据主区顶部空间。该 TASK 的 Task 3 是在设置页存在**之前**设计的，当时提示条是唯一可达路径；现在前提已变。
2. **设置页布局质量差**：卡片无边框、标签与值之间大片空白、长路径折行错乱。见 `specs/images/`（用户截图 2026-07-29）。

目标是收拾这两处，不扩大到 CRUD 或其他界面。

---

## 关键决策

| # | 决策 |
| --- | --- |
| A | 删除工作台的「前往设置」按钮与其所在提示条；设置入口统一由左侧导航承担。 |
| B | **保留** `settings_requested` 信号。它有第二个发射点（未配置时点「重新读取程序文件夹」），与被删按钮无关。 |
| C | 未配置状态**必须仍然可见**，只是不再带按钮。删提示条不等于删状态提示。 |
| D | 设置页改用 QFluentWidgets 的卡片组件，不再用裸 `QFrame` 手搭。 |
| E | `set_paths()` / `configure_requested` 是对外契约，重构中保持签名不变。 |
| F | 向导已支持两个字段独立编辑（各有独立输入框与「浏览」）。真正的缺陷是**必填校验阻塞单独修改工具根目录**，见 Task 3。 |
| G | 向导从设置页打开时（`allow_skip=False`）应显示「修改」语义的文案，而非首次配置的欢迎语。 |

---

## 范围

### 包含

- 删除 `configuration_notice` 提示条与 `open_settings_button`；
- 以无按钮的形式保留未配置状态提示；
- `settings_interface.py` 布局与视觉重做；
- 向导「修改」场景的校验放宽与文案修正（Task 3）；
- 受影响测试的重写；
- CHANGELOG 同步。

### 不包含

- 任何 CRUD 功能；
- 设置页新增除程序文件夹外的配置项；
- 左侧导航结构调整；
- 向导的整体视觉重做（Task 3 只改校验与文案，不动布局）；
- 主工作台其他区域的布局调整。

---

## 子任务拆解

### Task 1：删除工作台「前往设置」重复入口  `complexity: low`

**复杂度理由：** 单文件、单一 UI 关注点，无 schema/service/数据流变更；唯一需要注意的是不要连带删掉仍在使用的信号。

**Files:**

- Modify `src/fwasset/ui_qt/workbench_window.py`
- Modify `src/fwasset/tests/test_qt_smoke.py`

**实施：**

1. 删除 `:204-216`：`configuration_notice` QFrame、`notice_layout`、`open_settings_button` 及其 `clicked` 连接、`main.addWidget(self.configuration_notice)`。
2. 以无按钮形式保留未配置提示。可选方案（实现时择一）：
   - 主区保留一个纯文本 `CaptionLabel`；
   - 或将状态并入现有 `header_title` / `header_badge` 区域。
   无论哪种，均由 `set_configuration_required()` 控制显隐。
3. `set_configuration_required()`（`:371-373`）改为控制上述新指示。
4. `set_configured_root()`（`:375-378`）保留 —— 它同时维护 `self.root_dir`。

**不要删除：**

- `:120` `settings_requested = Signal()` —— `:399` 仍在用：未配置根目录时点「重新读取程序文件夹」会 `_log` 提示并 emit 跳转设置页。删信号会连带破坏这条路径。
- `:1044` `self.workbench.settings_requested.connect(self._open_settings)` 保持不变。

**测试影响：**

`test_qt_smoke.py:104` `test_workbench_missing_configuration_notice_opens_settings` 直接点击 `open_settings_button`，必然失败。重写为：

- 断言未配置指示可见（替代原 `configuration_notice.isHidden()` 断言）；
- 保留一条覆盖 `:399` 跳转路径的断言。`:186` 附近已有 `settings_requested` 相关测试，**先确认是否已覆盖该路径**，避免重复用例。

**验收：** 未配置时用户仍能看到「尚未配置程序文件夹」的状态；点左侧导航可进设置；点「重新读取程序文件夹」在未配置时仍跳转设置页；主区顶部不再有按钮条。

---

### Task 2：设置页 UI 与布局重做  `complexity: medium`

**复杂度理由：** 单文件重构但涉及组件替换与多状态视觉验证（未配置 / 已配置 / 超长路径）；需保持对外契约不变并通过既有测试。

**Files:**

- Modify `src/fwasset/ui_qt/settings_interface.py`
- Modify `src/fwasset/ui_qt/design_tokens.py`（仅当需要新增间距常量）
- Modify `src/fwasset/tests/test_qt_smoke.py`（仅当契约变更）

**现存问题（对照用户截图逐条）：**

| # | 问题 | 位置 |
| --- | --- | --- |
| 1 | `card` 是裸 `QFrame`，无边框/背景/圆角，视觉上不成卡片，只是一堆浮空文字，与 QFluentWidgets 其余界面不一致 | `:26-27` |
| 2 | `_path_row()` 用 `addStretch(1)` 把标签与值推向两端，导致「固件根目录」与其值之间大片空白，且两行的值左边缘不对齐 | `:54-62` |
| 3 | 长路径折行难看：截图中工具根目录第二行「—按摩椅刷程序工具」缩进错乱 | `:60` `setWordWrap(True)` |
| 4 | 「更改…」按钮位于卡片左下紧贴路径行，层级不清 | `:44-49` |
| 5 | 标题与副标题、卡片之间间距失衡；整页顶部留白过多而卡片过于贴上 | `:19-24` |
| 6 | `setMaximumWidth(760)` 在宽窗口下整体左对齐，右侧大片空白 | `:27` |

**已定决策（2026-07-29）：**

| 项 | 决策 |
| --- | --- |
| 页面结构 | **`PushSettingCard` 组件化**：固件根目录、工具根目录各一张卡，每张自带标题、当前值（`content`）、右侧「更改」按钮。用 `SettingCardGroup("程序文件夹")` 承载。 |
| 宽度 | **保持左对齐 + `setMaximumWidth(760)`**。右侧留白是刻意的，不是缺陷；长路径不被拉伸过长更易读。 |

**实施：**

1. 问题 1、2、4、5 由组件化**结构性解决** —— `PushSettingCard(text, icon, title, content, parent)` 自带边框、内边距与「标题 / 说明 / 右侧按钮」三段式布局，不再需要手搭 `QFrame` + `addStretch(1)` 两端对齐，也就不会有截图里那片中间空白。
   - 每张卡需一个 `FluentIcon`（如 `FluentIcon.FOLDER` / `FluentIcon.DEVELOPER_TOOLS`）。
2. 问题 3（长路径）：**`ElidedLabel` 在当前 QFluentWidgets 版本中不存在**（已实测 `ImportError`）。可用方案：
   - `PushSettingCard` 的 `content` 自身有省略行为，先实测是否已足够；
   - 若不够，用 `QFontMetrics.elidedText()` 手动截断；
   - 无论哪种，都要 `setToolTip()` 显示完整路径。
3. 问题 6：按上表保持左对齐与 760 上限，无需改动。
4. 卡片的当前值通过 `setContent()` 更新 —— `set_paths()` 的实现随之改写，但**签名不变**。

**约束：**

- 仅用 PySide6 + QFluentWidgets，**不得引入 CTk/tkinter**；
- 间距一律走 `design_tokens.py` 的 `SPACE_*` 常量，不写魔法数字；
- `set_paths(root_dir, tool_root)` 与 `configure_requested` 信号保持不变 —— `workbench_window.py` 与 `test_qt_smoke.py:100` 依赖它们。若必须变更，同步改调用方与测试。

**⚠️ 与 Task 3 的耦合（组件化决策的直接后果）：**

`PushSettingCard` 让每个路径**各有一个「更改」按钮**。这使 Task 3 的问题 1 从「体验不佳」升级为**功能性缺陷**：

- 用户点工具根目录卡上的「更改」，意图明确就是只改这一项；
- 但 `validate_paths()` 仍会因固件根目录为空/失效而拒绝保存；
- 界面承诺了单项修改，行为却做不到 —— 比现在只有一个按钮时更容易让人困惑。

因此：**Task 2 若采用组件化，Task 3 必须一并完成**，否则会交付一个按钮点了不生效的界面。

两种收口方式（实施时择一）：
- 两张卡的「更改」都打开同一个向导（改动小），但 Task 3 必须放宽校验；
- 或向导支持单字段模式（改动大，需重新评估复杂度）。

若暂不做 Task 3，则 Task 2 应退回单卡 + 单「更改」按钮的形态。

**验收：** 三种状态（未配置 / 已配置短路径 / 已配置超长路径）下布局均不错乱；标签与值对齐；长路径不溢出且可查看完整值；视觉风格与工作台一致。

---

### Task 3：修复向导的「修改」场景  `complexity: medium`

**复杂度理由：** 涉及校验逻辑与配置写入两处行为变更，会影响首次配置与后续修改两条路径，需双路径测试覆盖。

**Files:**

- Modify `src/fwasset/ui_qt/setup_wizard.py`
- Modify `src/fwasset/tests/test_qt_smoke.py`

**背景更正：** 向导**已经**支持两个字段独立编辑 —— `_make_path_row()`（`:88-107`）为每个字段各建了 `QLineEdit` + 独立「浏览」按钮，且从设置页打开时会预填当前值。因此不需要拆分入口。实际缺陷是下面两条。

**问题 1：必填校验阻塞单独修改工具根目录**

`validate_paths()`（`:132-136`）无条件要求固件根目录非空且存在。后果：用户想只改工具根目录时，若固件根目录当前未配置（或已失效，如移动硬盘未插），「完成配置」会被拒绝，无法单独保存工具路径。

用户截图（2026-07-29）正是此状态：标题为「程序文件夹设置」（从设置页打开），工具根目录已有值，固件根目录为空 —— 此时点「完成配置」必然报错。

`write_config()`（`:151-157`）同时无条件重写两个键，没有部分保存路径。

**问题 2：修改场景仍显示首次配置文案**

`_build_ui()`（`:52-56`）无条件加入「欢迎使用固件资产管理工具。」等首次配置说明，只有「跳过」那一行受 `allow_skip` 控制。从设置页打开（`allow_skip=False`，标题已正确显示为「程序文件夹设置」）时，正文仍是欢迎语，语义错位。

**实施：**

1. 问题 2 直接修：`allow_skip=False` 时改用修改语义的文案（如「修改程序文件夹路径。留空的项将保持当前配置。」），首次配置文案仅在 `allow_skip=True` 时显示。
2. 问题 1 采用 **方案 A（放宽校验）**（2026-07-29 决策）：`allow_skip=False`（修改场景）时，允许固件根目录为空并保留原配置值，仅校验「填了的项必须是有效目录」。「必填」标签需相应调整为仅在首次配置时出现。
3. 无论哪种，都必须保证：首次配置路径（`allow_skip=True`）**仍然强制要求固件根目录有效**，不能因放宽而允许写入空配置。

**验收：** 已配置固件根目录的用户可单独修改工具根目录并保存；固件根目录失效时不阻塞工具路径的修改；首次配置仍强制固件根目录有效；修改场景不再显示欢迎语。

---

## 决策记录

| 日期 | 决策 |
| --- | --- |
| 2026-07-29 | Task 2 页面结构采用 `PushSettingCard` 组件化；宽度保持左对齐 + 760 上限。 |
| 2026-07-29 | Task 3 问题 1 采用**方案 A（放宽校验）**，不做部分保存。理由：改动面小，不引入 config 读-改-写的合并逻辑。 |
| 2026-07-29 | 因组件化使每路径各有「更改」按钮，Task 2 与 Task 3 **合并实施**，一次人工验证覆盖。 |

---

## 自动化验证与人工验证

### 自动化

```powershell
uv run python -m pytest src/fwasset/tests/test_qt_smoke.py -q --no-cov

uv run python -m pytest -m "not ui" -q --no-cov

.\scripts\test.ps1
```

调整后的测试至少覆盖：

- 未配置时状态指示可见、已配置时不可见；
- 未配置时「重新读取程序文件夹」仍跳转设置页（`:399` 路径）；
- 设置页仍能显示路径并发出 `configure_requested`；
- 已配置固件根目录时，仅修改工具根目录可通过校验并保存；
- 首次配置（`allow_skip=True`）空固件根目录**仍被拒绝**（防止 Task 3 放宽校验时误伤首次配置）。

既有测试 `test_setup_wizard_prefills_validates_and_writes_config` 覆盖了向导校验，Task 3 会影响它，需同步调整。

### 人工验证（必须）

1. 未配置状态：主区能看到未配置提示，且**没有**「前往设置」按钮；
2. 未配置状态：左侧导航进入设置 → 完成配置 → 提示消失、列表更新；
3. 未配置状态：点「重新读取程序文件夹」→ 跳转设置页；
4. 设置页三种状态截图对比：未配置 / 短路径 / 超长路径（用截图中的「D:\按摩椅相关文件汇总\摩众—按摩椅刷程序工具」这类长路径）；
5. 窗口拉宽 / 缩窄，确认卡片布局不错乱；
6. 已配置固件根目录 → 设置页「更改…」→ 只改工具根目录 → 完成配置，确认能保存且固件根目录不丢失；
7. 从设置页打开向导，确认正文不再是「欢迎使用固件资产管理工具」；
8. 首次配置场景（无 config）：确认固件根目录留空仍**无法**完成配置；
9. 检查所有用户可见文字，不出现「回源」「索引」「数据库」等内部术语。

---

## 文档与收口

- Modify `docs/CHANGELOG.md`：在 `Unreleased` 记录设置页重做与重复入口清理；
- 两个子任务、自动化验证与人工验证均完成后，按 `AGENTS.md` 的人工验证前置流程提交。
