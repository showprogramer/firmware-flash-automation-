# TASK-20260708: UI 框架迁移 CustomTkinter → PySide6

## 状态（2026-07-14 更新）

| 项                   | 状态                                                              |
| ------------------- | --------------------------------------------------------------- |
| 分支                  | `feature/pyside6-migration`                                     |
| Phase 0–3           | ✅ 完成                                                            |
| 审查阻断项 Issue 1–20 主体 | ✅ 完成并人验（见 `docs/code-review/REVIEW-20260709-branch-pyside6.md`） |
| Phase 4.0–4.2       | ✅ 完成（功能验收与契约；**尚未**切默认入口 / 打包）                              |
| **Phase 4.3–4.7**   | ⏸ **暂停**（进度停在 4.3 之前；收尾切 Qt / 打包延后）                            |
| **当前主线**            | → **`TASK-20260714-config-takeover.md`**（软件接管配置）                 |
| CRUD / 增量写盘         | 📋 配置接管 TASK 之后再立                                              |

**默认入口现状**：`app.py` 仍默认 CTk；`FWASSET_UI=qt` 走 `ui_qt`。Phase 4.3 起目标仍为默认 Qt，但**不再作为当前冲刺**。

**暂停原因**：壳与双轨能力已够支撑业务迭代；产线更急的是「无 toml 可设默认 / 共享引用 / 独立型号」，不宜与迁移收尾绑在同一 TASK。恢复本文件时从 **§4.3 默认入口切换** 继续。

---

## 背景与目标

CTk + ttk.Treeview 的交互天花板（右键菜单靠手拼、无行内编辑、无原生拖拽、单元格无徽章控件）挡住了后续 CRUD 的交互需求，观感也达不到预期。经选型讨论（见 2026-07-08 会话）确定迁移到 **PySide6**：模型/视图原生虚拟化、右键/拖拽/行内编辑委托齐全、原生字体渲染与高 DPI、PyInstaller 打包成熟。

**目标**：UI 壳完整迁移，功能与现状 1:1 对齐（工作台、设默认、多型号、四类操作面板、扫描、日志），迁移期间不夹带新功能。CRUD（增删改、替换程序文件）在新壳落地后再做——避免在旧框架上建一遍再重写。

## 不变的部分（迁移的资产）

- `core/**` 全部：扫描、索引、服务层、平台配置。（迁移期「尽量少动」；审查修复可改 core，不算新业务功能。）
- `ui/view_models/scheme_workbench_model.py`：不依赖 tkinter，双轨共用（`SchemeWorkbenchModel` 是 UI 的大脑）。
- `ui/view_models/scan_state_model.py`：纯 threading，双轨共用。
- 领域约束：用户可见归属 **「定制专属」/「通用」**（禁「回源」）、`STANDARD_MODULE_ORDER`、平台按型号隔离。
- 非 UI 测试覆盖率口径：`pyproject.toml` omit `ui/*` 与 `ui_qt/*`。

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
| `app.py` 入口                    | **默认切 Qt**；可选 `FWASSET_UI=ctk` 回退              | **4 ⏳** |
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

- 依赖：`pyside6` + `pyside6-fluent-widgets`（`uv sync --extra qt`）。
- `scripts/spike_pyside6.py`；启动/体积/中文高 DPI 摸底通过。
- 踩坑：用 `uv run python -m PyInstaller`；exe 旁必须有 `firmware_catalog.toml`；暗色截图不全需人开窗验。

**Phase 1 — 壳与骨架** ✅（与 Phase 2 同批）

- `ui_qt/` 并行；`FWASSET_UI=qt` 开关；coverage omit `ui_qt/*`。

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
- [x] 本机：`uv sync --extra dev --extra qt`。
- [x] 明确交付策略：**内部工具** → 可继续 QFluent（GPLv3）；若计划对外分发 exe → Phase 4 内决策是否换主题（见风险）。

### 4.1 功能验收（默认以 Qt 为准勾选）

在 **Phase 4.3 切默认之前**，用 `FWASSET_UI=qt uv run fwasset`（或等价）过一遍；切默认后用无环境变量再过一遍。

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

- [ ] `app.py`：**默认**启动 Qt（`ui_qt.workbench_window.main`）。
- [ ] 回退开关：`FWASSET_UI=ctk`（或 `tk`）仍可开 CTk，便于一周期应急。
- [ ] 更新注释 / `docs/README.md` / `CLAUDE.md` 启动说明（默认 Qt、如何回退）。
- [ ] 可选：`config` 或说明文件写清环境变量，避免产线不知。

### 4.4 打包与交付

- [ ] `fwasset.spec`：PySide6 + qfluentwidgets 收集；**去掉** customtkinter 隐性依赖（若仍保留 CTk 回退则双轨 hooks 都要，或 Phase 4 明确「exe 只带 Qt」）。
- [ ] 推荐 Phase 4 交付策略（二选一，勾选时写死）：
  - **A（推荐）**：exe **仅 Qt**；CTk 仅源码 `FWASSET_UI=ctk` 开发回退。
  - **B**：exe 仍双轨（体积更大，一般不必要）。
- [ ] 构建：`uv run python -m PyInstaller fwasset.spec`（勿用坏掉的 shim）。
- [ ] 交付目录旁放置：`firmware_catalog.toml`、（可选）`config.example.toml`；启动缺 catalog 时有明确日志/提示（若尚未做可本阶段补）。
- [ ] 冷启动可接受；主路径功能在冻结 exe 上点验一遍。

### 4.5 CTk 退役节奏

- [ ] **本版本**：`ui/` 保留，冻结功能性开发，只修阻断 bug。
- [ ] 文档写明：下一版本或「一个版本周期后」删除 `ui/` 与 customtkinter 依赖。
- [ ] 删除前再开小 TASK/PR：去依赖、去 omit 以外的死代码、更新 spec。

### 4.6 文档与收尾

- [ ] 本 TASK Phase 4 与验收清单全部勾选。
- [ ] `docs/CHANGELOG.md` Unreleased：默认 Qt、打包、回退方式。
- [ ] `docs/code-review/REVIEW-20260709-branch-pyside6.md`：Phase 4 完成后可归档到 `archive/` 或标完成。
- [ ] 合并 `feature/pyside6-migration` → `main`（PR 或本地约定流程）。
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

- [ ] 扫描/取消/缓存加载；多型号根双型号识别；单型号根兼容
- [ ] 侧边树、全部/通用/方案三种视图、搜索空格分词、防抖；点方案清搜索且高亮正确
- [ ] 方案视图整机层级：单变体折叠、多变体展开、定制专属/通用、无「回源」
- [ ] 右键设默认（单/多平台）、★默认徽章（含空默认唯一变体）、toml 写回、免重扫生效
- [ ] 四类操作面板 + 一键烧录 + 全局 U 盘选择器 + 日志
- [ ] 默认入口 Qt；`FWASSET_UI=ctk` 可回退（若保留）
- [ ] PyInstaller exe 可运行；`.\scripts\test.ps1` 通过

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
| **当前** | [`TASK-20260714-config-takeover.md`](./TASK-20260714-config-takeover.md) | 软件接管配置 → 共享引用（见 `specs/prompts/task-exchange.md` 1–4） |
| 其后 | `TASK-YYYYMMDD-firmware-crud` | 程序 CRUD + 增量索引 / 对账（exchange 5–6） |
| 迁移恢复 | 本文 §4.3–4.7 | 默认 Qt + 打包 + 合 main |
| 更后 | `TASK-YYYYMMDD-remove-ctk` | 物理删除 `ui/` 与 customtkinter |

命名建议：`TASK-YYYYMMDD-firmware-crud.md` / `TASK-YYYYMMDD-remove-ctk.md`。
