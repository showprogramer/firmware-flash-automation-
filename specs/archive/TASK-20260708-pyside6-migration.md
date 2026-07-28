# TASK-20260708: UI 框架迁移 CustomTkinter → PySide6

## 状态（2026-07-28 收口）

| 项 | 状态 |
| --- | --- |
| 分支 | `feature/pyside6-migration` |
| Phase 0–3 | ✅ 完成 |
| 审查阻断项 Issue 1–20 | ✅ 完成并人验；分支总审已归档 |
| Phase 4.0–4.7 | ✅ 默认入口、Qt-only 打包、CTk 退役、文档与人工验收均完成 |
| 迁移任务 | ✅ 已完成，归档保留历史与验收总表 |
| 分支合并 | ⏸ 按用户决定暂不合并 `feature/pyside6-migration` → `main`；不影响迁移任务闭环 |
| 后续主线 | 配置接管与 firmware CRUD；不属于本迁移 TASK |

**默认入口现状**：`app.py` 默认进入 `ui_qt`，Qt 是唯一受支持界面；`FWASSET_UI` 不再控制界面选择。

**收口说明**：默认入口、依赖清理、CTk 退役和 Qt-only 打包已由 `TASK-20260724-qt-only-ui-cleanup.md` 实施并验收。本 TASK 已完成，现归档；分支整合另按用户决定处理。

---

## 背景与目标

CTk + ttk.Treeview 的交互天花板（右键菜单靠手拼、无行内编辑、无原生拖拽、单元格无徽章控件）挡住了后续 CRUD 的交互需求，观感也达不到预期。经选型讨论（见 2026-07-08 会话）确定迁移到 **PySide6**：模型/视图原生虚拟化、右键/拖拽/行内编辑委托齐全、原生字体渲染与高 DPI、PyInstaller 打包成熟。

**目标**：UI 壳完整迁移，功能与现状 1:1 对齐（工作台、设默认、多型号、四类操作面板、扫描、日志），迁移期间不夹带新功能。CRUD（增删改、替换程序文件）在新壳落地后再做——避免在旧框架上建一遍再重写。

## 不变的部分（迁移的资产）

- `core/**` 全部：扫描、索引、服务层、平台配置。（迁移期「尽量少动」；审查修复可改 core，不算新业务功能。）
- `ui_common/view_models/scheme_workbench_model.py`：不依赖具体 UI 框架（`SchemeWorkbenchModel` 是 UI 的大脑）。
- `ui_common/view_models/scan_state_model.py`：纯 threading，Qt 工作台使用。
- 领域约束：用户可见归属 **「定制专属」/「通用」**（禁「回源」）、`STANDARD_MODULE_ORDER`、平台按型号隔离。
- 非 UI 测试覆盖率口径：`pyproject.toml` 仅 omit `app.py` 与 `ui_qt/*`，`ui_common` 纳入覆盖率。

## 需要重写的文件清单

| 现文件                            | 去向                                             | Phase   |
| ------------------------------ | ---------------------------------------------- | ------- |
| `ui/shell.py`                  | `ui_qt/workbench_window`（Fluent / QWidget 壳）   | 1–2 ✅   |
| `ui/base_panel.py` 任务/USB      | `WorkbenchInterface._run_task` + Signal        | 3 ✅     |
| `ui/workbench_panel.py`        | `ui_qt/workbench_window.py`                    | 1–3 ✅   |
| `ui/panels/data_grid_panel.py` | `ui_qt/data_grid.py`                           | 2 ✅     |
| `ui/panels/log_panel.py`       | `ui_qt/log_panel.py`                           | 1 ✅     |
| `ui/operation_panels/*`        | `ui_qt/operation_panels/*`（独立 registry）        | 3 ✅     |
| `ui/design_tokens.py`          | Qt 侧布局令牌 `ui_qt/design_tokens.py`（主题暂靠 Fluent） | 1–2 ✅   |
| `app.py` 入口                    | **默认切 Qt**；不保留 CTk 回退              | **4 ✅** |
| `fwasset.spec`                 | PySide6 / Fluent hooks，去掉 customtkinter        | **4 ⏳** |

## 主题决策（迁移第 0 步定案）

| 方案                          | 观感               | 许可                 | 备注                       |
| --------------------------- | ---------------- | ------------------ | ------------------------ |
| QFluentWidgets              | 最好（Fluent，现成组件全） | **GPLv3**（商用需付费授权） | **已采用**；内部工具可用，对外分发前须再决策 |
| PyQtDarkTheme / qt-material | 中等               | MIT / BSD          | 许可顾虑时的降级路径               |
| 纯 QSS 自绘                    | 可控               | -                  | 不推荐                      |

---

## 分阶段计划

**Phase 0 — Spike** ✅（2026-07-08）

- 依赖：`pyside6` + `pyside6-fluent-widgets`（随主依赖安装，`uv sync --extra dev` 即可）。
- `scripts/spike_pyside6.py`；启动/体积/中文高 DPI 摸底通过。
- 踩坑：用 `uv run python -m PyInstaller`；exe 旁必须有 `firmware_catalog.toml`；暗色截图不全需人开窗验。

**Phase 1 — 壳与骨架** ✅（与 Phase 2 同批）

- `ui_qt/` 为唯一界面；`FWASSET_UI` 不再控制界面；coverage 仅排除 `app.py` 与 Qt 壳目录。

**Phase 2 — 数据面** ✅

- 侧栏 / 型号 / 搜索防抖 / DataGrid / 扫描 Signal / scan_meta 恢复根。
- 后人验与审查中已补：方案树搜索解耦、侧栏高亮、归属「通用」、列序 归属|版本 等。

**Phase 3 — 操作面与任务** ✅

- 四面板 + PanelHost（无 tk 类型）+ 任务 Signal + 日志线程安全。
- 后人验与审查中已补：任务 `task_id` 回调 UI 线程、扫描/任务互锁、取消扫描文案等。

**Phase 4 — 对齐与切换** ⏸ **4.0–4.2 完成；4.3+ 暂停**

见下一节完整清单。恢复后预估约 0.5–1 个工作日（切默认 + 打包 + 人验）。  
**当前业务主线**：`TASK-20260714-config-takeover.md`。

---

## Phase 4 — 可执行清单

### 4.0 前置

- [x] 分支 `feature/pyside6-migration` 工作区干净，最新审查项已合入。
- [x] 本机：`uv sync --extra dev`。
- [x] 明确交付策略：**内部工具** → 可继续 QFluent（GPLv3）；若计划对外分发 exe → Phase 4 内决策是否换主题（见风险）。

### 4.1 功能验收（默认以 Qt 为准勾选）

Qt-only 阶段使用无环境变量的 `uv run fwasset` 验证默认入口；不再安排 CTk 第二套启动验证。

**扫描与索引**

- [x] 扫描弹目录选择；取消扫描提示正确、不空表 rebind。
- [x] 缓存加载：有索引时显示条目数；无 `DEFAULT_ROOT` 时从 `scan_meta` 恢复上次根。
- [x] 多型号根双型号识别；单型号根（含 `通用/定制`）兼容。
- [x] 扫描中无法启动烧录任务；任务中无法开扫（互锁）。

**导航与搜索**

- [x] 侧栏：全部 / 通用模块 / 定制方案；搜索过滤侧栏后点方案会清搜索、侧栏复原且高亮正确方案。
- [x] 全部 / 通用 / 方案三种主表；搜索空格分词（全部/通用）；方案内再搜语义正确。
- [x] 搜索防抖，型号切换即时。

**方案整机表**

- [x] 单变体折叠、多变体展开；归属仅「定制专属」/「通用」；无「回源」。
- [x] 列序：程序类型 | 程序名称 | 程序归属 | 版本 | 程序文件。
- [x] 平台默认 ★默认（含 toml 空默认 + 唯一嵌套变体）；方案回源行可见 ★默认。
- [x] 右键：设为平台默认（单/多平台）、打开目录、复制路径；写 toml 免重扫生效。

**操作与 USB**

- [x] 四类面板按 `flash_mode` 挂载；断码屏为 **tool_launch**（非一键 U 盘）。
- [x] 全局 U 盘选择器 + 启动自动刷新；一键/目录刷机真实 U 盘流程（人验）。
- [x] 任务成功/失败日志正确；忙态提示正确。
- [x] 日志面板可写、可折叠（若有）。

**回归**

- [x] 暗色主题人工开窗可接受（截图自动化不强制暗色）。
- [x] `.\scripts\test.ps1` 或 `uv run python -m pytest -m "not ui" -q` 通过（coverage 门禁）。

### 4.2 自动化（pytest-qt / 契约）

优先补「防回归」静态或轻量 UI 契约（已有部分在 `test_qt_smoke.py` / helpers）：

- [x] 全局 USB：启动路径调度刷新 / 选择器存在（契约测试已有则勾选确认）。
- [x] 设默认菜单出现条件（通用变体右键）。
- [x] 可选：关键路径 pytest-qt 冒烟（需 display 的标 `@pytest.mark.ui`）。
- [x] **不要**强求真实 U 盘自动化。

### 4.3 默认入口切换 ⏸ 暂停起点（恢复迁移时从这里做）

- [x] `app.py`：**默认**启动 Qt（`ui_qt.workbench_window.main`）。
- [x] 不保留 CTk 回退开关；Qt 为唯一受支持界面。
- [x] 更新注释 / `docs/README.md` 启动说明（默认 Qt）。
- [x] `config` 或说明文件不再要求设置界面环境变量。

### 4.4 打包与交付

- [x] `fwasset.spec`：PySide6 + qfluentwidgets 收集；去掉 CTk 隐性依赖。
- [x] 交付策略：exe **仅 Qt**，不保留 CTk 回退。
- [x] 构建：`uv run pyinstaller fwasset.spec --noconfirm` 已成功。
- [x] 交付目录旁放置：`firmware_catalog.toml`、（可选）`config.example.toml`；启动缺 catalog 时有明确日志/提示（若尚未做可本阶段补）。
- [x] 冷启动可接受；主路径功能在冻结 exe 上点验一遍（2026-07-27 通过）。

### 4.5 CTk 退役节奏

- [x] **本版本**：删除 `ui/` CTk 壳、面板、专属测试与 `customtkinter` 依赖。
- [x] 文档写明 Qt-only 结论；后续 B3 不再安排 CTk 人工验收。
- [x] 清理工作由 `TASK-20260724-qt-only-ui-cleanup.md` 追踪并保留独立提交边界。

### 4.6 文档与收尾

- [x] 本 TASK Phase 4 与验收清单全部勾选（2026-07-27）。
- [x] `docs/CHANGELOG.md` Unreleased：默认 Qt、打包与 CTk 退役结论。
- [x] `docs/code-review/REVIEW-20260709-branch-pyside6.md`：归档到 `archive/`（2026-07-27）。
- [ ] 分支合并 `feature/pyside6-migration` → `main`：按用户决定暂不执行；这是分支整合决策，不属于迁移实现验收。
- [ ] **不要**在本 PR 夹带 CRUD。

### 4.7 完成定义（Definition of Done）

同时满足即可关闭本 TASK：

1. 默认无环境变量启动即为 Qt 工作台。  
2. §4.1 验收清单全部勾选（含真实 U 盘人验）。  
3. `.\scripts\test.ps1`（或等价 coverage 门禁）通过。  
4. PyInstaller exe 可运行且 catalog 就位。  
5. CHANGELOG / 启动文档已更新；CTk 退役节奏已写明。

---

## 验收清单（总表，与 4.1 对应）

> 文案以现行产品为准：归属 **定制专属 / 通用**（非「通用默认」）。

- [x] 扫描/取消/缓存加载；多型号根双型号识别；单型号根兼容
- [x] 侧边树、全部/通用/方案三种视图、搜索空格分词、防抖；点方案清搜索且高亮正确
- [x] 方案视图整机层级：单变体折叠、多变体展开、定制专属/通用、无「回源」
- [x] 右键设默认（单/多平台）、★默认徽章（含空默认唯一变体）、toml 写回、免重扫生效
- [x] 四类操作面板 + 一键烧录 + 全局 U 盘选择器 + 日志
- [x] 默认入口 Qt；不保留 `FWASSET_UI=ctk` 回退
- [x] PyInstaller exe 可运行；`.\scripts\test.ps1` 通过

---

## 最终验证记录（2026-07-28）

### 自动化验证

```powershell
.\scripts\test.ps1
```

结果：381 passed，coverage 94.33%。

### 人工验证

- 2026-07-23：Qt-only 人工验收通过；默认入口进入 Qt，B2 三个场景通过，CTk 不再作为支持界面。
- 2026-07-27：PyInstaller 冻结 exe 冷启动与 Qt 工作台主路径点验通过。
- 2026-07-28：首次配置、跳过后前往设置、设置中切换程序文件夹及重新读取根目录等后续 Qt 工作流验证通过。

### 结论

- Phase 0–4.7、迁移审查阻断项和 Qt-only 收口均已完成。
- CustomTkinter 运行入口、依赖、专属源码与测试已退役。
- CRUD、资产行级写入和分支合并均为迁移完成后的独立事项；其中 `feature/pyside6-migration` → `main` 按用户决定暂不执行。
- 本 TASK 可归档，不代表合并分支。

---

## 风险

- QFluentWidgets GPLv3：内部使用无碍，**对外分发前必须决策**（换主题或购 license）。
- exe 体积增加约 30~50MB（Qt 运行库）：spike 已确认可接受。
- 双轨维护窗口要短：Phase 4 切默认后尽快冻结 CTk。
- 打包漏收 Qt/Fluent 插件或漏 `firmware_catalog.toml` → 白屏/0 资产（按踩坑清单防）。

---

## 后续（迁移暂停期间 / 关闭后）

| 优先级 | TASK | 说明 |
| --- | --- | --- |
| **当前** | [`TASK-20260714-config-takeover.md`](../active/TASK-20260714-config-takeover.md) | 软件接管配置 → 共享引用（见 `specs/prompts/task-exchange.md` 1–4） |
| 其后 | `TASK-YYYYMMDD-firmware-crud` | 程序 CRUD + 增量索引 / 对账（exchange 5–6） |
| 分支整合 | `feature/pyside6-migration` → `main` | 按用户决定暂不执行；不属于本 TASK 的实现收口 |
| 迁移收口 | [`TASK-20260724-qt-only-ui-cleanup.md`](../active/TASK-20260724-qt-only-ui-cleanup.md) | Qt-only 入口、依赖、旧壳清理与 B3 前置（已完成） |

命名建议：`TASK-YYYYMMDD-firmware-crud.md`。CTk 退役已由 `TASK-20260724-qt-only-ui-cleanup.md` 完成。
