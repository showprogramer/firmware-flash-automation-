# 代码审查：feature/pyside6-migration 分支总审

- 日期：2026-07-09（文档修订：同日，纳入人验反馈与 `task-exchange`）
- 类型：分支审查（core 域 + 工作台 + PySide6 双轨）
- 模块：
  - `src/fwasset/core/**`（`asset_index` / `file_scan` / `scheme_config` / `scan_service` 等）
  - `src/fwasset/ui/view_models/scheme_workbench_model.py`
  - `src/fwasset/ui_qt/**`（Phase 0–3 新壳）
  - `src/fwasset/ui/workbench_panel.py`（CTk 对照 / 双轨漂移）
- 范围：`feature/pyside6-migration` vs `origin/main`（merge-base `964aec58`）
- 源码 diff 口径：`src/fwasset/` + `pyproject.toml` + `firmware_catalog.toml` + `scripts/`（审查时 84 files）
- 关联：
  - 计划：`specs/active/TASK-20260708-pyside6-migration.md`
  - 同日细审（已归档）：`archive/REVIEW-20260709-pyside6-phase3-core.md`
  - 上轮（已归档）：`archive/REVIEW-20260708-pyside6-p1-p2.md`、`archive/REVIEW-20260708-platform-default.md`
  - 已合入：`7156dc4`（Issue 1）、`b180292`（Issue 2–5）、`2e745fa`（Issue 6/7/19/20 + 侧栏高亮）
  - 目录约定：见 `docs/code-review/README.md`（根目录仅活文档；历史在 `archive/`）

---

## 0. 进度与整体评价

### 项目进度

| 阶段 | 状态 |
|------|------|
| 工作台 UI 重写（方案/通用/回源） | ✅ 完成 |
| 设为平台默认 + 多型号根 | ✅ 完成 |
| UI Review Bugfix | ✅ 完成 |
| PySide6 Phase 0–3 | ✅ 完成 |
| 审查 Bug Issue 1–5 | ✅ 已修并人验合入 |
| 工作台搜索/方案树（Issue 19–20） | ✅ 已修并人验（`2e745fa`） |
| **PySide6 Phase 4**（默认切 Qt / CTk 退役 / 打包） | ⏳ 待做（建议先收敛工作台可辨认/方案树正确性） |
| CRUD / 增量重扫 | 📋 规划中 |

**双轨现状**：`app.py` 默认 CTk；`FWASSET_UI=qt` 走 `ui_qt/workbench_window`。Phase 4 前不应默认切 Qt。

### 自动化门禁

- Issue 1 合入时：`test_asset_index` + `test_scan_service` 等通过  
- Issue 2–5 合入时：`test_scan_service` + `workbench_panel_helpers` + `base_panel_poll` + `qt_smoke` → **45 passed**  
- 全量非 UI 门禁以分支最新 `.\scripts\test.ps1` / `pytest -m "not ui"` 为准（改下一轮前重跑）

### 总评

- 双轨 Qt 壳（日志 Signal、`PanelHost` 无 tk、注册表隔离、多型号/平台隔离）方向正确。  
- **核心契约类** Issue 1–5 已按单工作区语义 + 扫描/任务互锁 + 结果文案收口并人验通过。  
- **当前人验痛点已转向工作台「找得见、看得懂」**：  
  - 全部视图搜索结果程序名称同质化（难辨认）；  
  - 点定制方案主表空白或只剩个别模块（与全局搜索词/过滤语义纠缠）。  
- 原审查 **Issue 6 / 7 与上述痛点关系有限**（见 §1.B）：6 几乎无关；7 只是方案内 keyword 管线的一小段，**不能单独当 task-exchange 的主修复**。

**问题统计（文档修订后）**

| 类别 | 数量 | 说明 |
|------|------|------|
| Bug fixed | 9 | Issue 1–7、19–20 |
| Suggestion open | 8 | Issue 8–15 |
| Nit open | 3 | Issue 16–18 |

---

## 1. 发现

### 1.A 已修复（Issue 1–5）

#### Issue 1 — 索引单工作区语义（原「全表 DELETE vs 多行 scan_meta」）
- 状态：**fixed（选 B）** · commit `7156dc4`
- 产品定案：一次一个工作区；目录 + TOML 为真相；全量扫描整库替换；换根 = 切换工作区。  
- 实现：`save_assets` 清空后只写一行 `scan_meta`；`active_workspace_root()`；迁移说明 `MIGRATION-20260709-single-workspace-index.md`。  
- 附带 UX：扫描**每次**弹选目录（当前根仅 initialdir）。

#### Issue 2 — `build_cached_scan_result` 宽捕获
- 状态：**fixed** · commit `b180292`
- `except Exception` → `index_unavailable`，禁止裸抛。

#### Issue 3 — 扫描 ↔ 任务互锁
- 状态：**fixed** · commit `b180292`
- 忙时不扫；扫描中不跑操作任务（CTk + Qt）。

#### Issue 4 — 取消扫描文案 / rebind
- 状态：**fixed** · commit `b180292`
- `code=cancelled` 只提示取消，不 rebind 空结果。

#### Issue 5 — 任务结果看 `ServiceResult.ok`
- 状态：**fixed** · commit `b180292`
- `ok=False` 记失败并弹窗，不再一律「完成」。

---

### 1.B 人验新增（主线）— 来源 `specs/prompts/task-exchange.md`

> 与原 Issue 6/7 **不是同一问题**。下一轮改代码以本节为准；6/7 并入子项或顺手做。

#### Issue 19 — Severity: bug · **点定制方案主表空白 / 只剩个别模块**
- 文件（实现落点）：
  - `ui/view_models/scheme_workbench_model.py` · `get_scheme_modules` / `get_scheme_module_tree`
  - `ui_qt/workbench_window.py` / `ui/workbench_panel.py` · `_refresh_main_grid`（把 **全局** `search_kw` 传给方案树）
- 现象（人验）：
  - 侧栏点「马来西亚」等方案 → 主表**空白**；
  - 点「以色列」→ **只剩手控 UI**（因手控路径/名含「以色列」），其它模块像被滤掉。
- 根因分析（代码层，待修时验证）：
  1. **导航与搜索职责缠在一起**：选中 `custom_scheme` 时仍把顶部搜索框全文当作 `keyword` 传入 `get_scheme_module_tree`。若搜索框残留「以色列」/任意词，方案树被二次过滤。  
  2. **方案内 keyword 过滤过窄且与全部视图不一致**：`get_scheme_modules` 在 `keyword` 非空时对定制与回源资产只做 `label` / `directory_name` 的**整串** substring（约 543–544、605–606 行），**不**走 `_filter_assets` 的 10 字段空格分词。  
  3. （待数据核对）回源失败：平台 `defaults` 与 catalog 标签/目录字差、`scheme_name` 与侧栏 key 不完全一致时，无专属 + 无回源 → 真空白。
- 与 Issue 6/7 关系：
  - **Issue 6**：无关（文案卫生）。  
  - **Issue 7**：同一条 keyword 管线的「分词缺口」；**修 19 时应一并对齐分词**，但 7 不是空白主因。主因更可能是 **(1) 残留搜索仍过滤方案树** + **(2) 字段过窄**。
- 建议修复方向（**待用户审本文档后实施**；产品二选一或组合）：
  - **A（推荐）**：进入「定制方案」节点时，主表默认展示**完整整机树**（定制专属 + 通用默认回源）；顶部搜索仅在用户有意过滤时生效；或切换方案时 **清空搜索框** / 明确「当前在方案内过滤」提示。  
  - **B**：保留全局搜索作用于方案树，但过滤语义与 `_filter_assets` **完全一致**（分词 + 多字段），且不得把「方案名点选」误当成「用方案名当 keyword 扫文件名」。  
  - 补测：搜索框有残留词时点方案；空搜索点方案应出满树；「手控 V13」类多词；马来西亚/以色列类真实方案（若有 fixture 则 mock 方案名与目录）。
- 状态：**fixed（A）** — 进方案清搜索；`get_scheme_modules` 统一分词过滤 + 覆盖集不按 keyword 缩水；卡片禁「回源」

#### Issue 20 — Severity: bug（体验 / 可辨认性）· **全部视图搜索结果程序名称同质化**
- 文件：
  - `scheme_workbench_model` · `get_all_modules` 及卡片字段
  - `ui_qt/data_grid.py` / `ui/panels/data_grid_panel.py` · 程序名称列渲染（`directory_name` / 「默认」折叠规则）
- 现象（人验）：在「全部程序与模块」搜「主板」等类型词 → 多行「程序类型=主板程序、程序名称=主板程序」，**看不出是哪一变体/哪一方案/通用还是定制**。  
- 根因：信息密度不足——类型与目录同名时名称列无区分度；方案上下文、变体目录、归属在「全部」场景下不够一眼可读。  
- 与 Issue 6/7 关系：**无关**（展示策略，非 keyword 分词、非回源文案）。  
- 建议修复方向（待审后实施）：
  - 程序名称优先展示**可区分的变体目录名**；同名时附加方案名 / `定制专属|通用默认` / 平台等短后缀；  
  - 或增加/强化「程序归属」列在全部视图的可见性（已有列则检查是否未填/被折叠掩盖）；  
  - 单变体「默认」折叠规则勿导致全部视图信息回退到与类型相同的空壳名。  
- 状态：**fixed（示例 A）** — `get_all_modules` 归属 `通用默认` / `定制专属 · {scheme}`；DataGrid 名称始终 `directory_name`，保留 model 归属文案

---

### 1.C 原审查仍 open 的 Bug（重标优先级）

#### Issue 6 — `ModuleCardData.source_label` 仍含「回源」
- 状态：**fixed**（与 19 同批：回源卡 `source_label="通用默认"`）

#### Issue 7 — 方案视图 keyword 不做空格分词 / 字段过窄
- 状态：**fixed**（并入 19：`_filter_assets` / `_asset_matches_keyword`）

---

### 1.D Suggestion（未改优先级说明）

#### Issue 8 — `on_done` 经跨线程 Signal 透传 callable
- 文件：`ui_qt/workbench_window.py`  
- 状态：open（对应 phase3 1.6）

#### Issue 9 — `file_scan` 加载平台配置后未使用
- 文件：`file_scan.py`  
- 状态：open（对应 1.3）

#### Issue 10 — `scheme_for_path` 非最长前缀
- 文件：`scheme_config.py`  
- 状态：open（对应 1.4）

#### Issue 11 — 扫描双遍目录树
- 文件：`scan_service.py`  
- 状态：open（对应 1.7）

#### Issue 12 — 增量扫描未剪枝子树（潜伏）
- 文件：`file_scan.py`  
- 状态：open（对应 1.10）

#### Issue 13 — 方案视图无 ★默认 徽章
- 文件：`get_scheme_module_tree`  
- 状态：open（可与 19/20 同域顺手）

#### Issue 14 — CTk 未从 scan_meta 恢复 root（双轨漂移）
- 文件：`workbench_panel.py`  
- 状态：open（Phase 4 前决策）

#### Issue 15 — `segmented_screen` flash_mode 变更是否 intentional
- 文件：`firmware_catalog.toml`  
- 状态：open（产品确认）

---

### 1.E Nit

#### Issue 16 — 方案头徽章「整机模块」vs「整机七程序」
- 状态：open

#### Issue 17 — DataGrid `clear` 未 blockSignals
- 状态：open

#### Issue 18 — SQLite 默认 timeout
- 状态：open（对应 1.8）

---

## 2. 与同日 Phase3 审查 / 人验对照

| 来源 | 项 | HEAD 处置 |
|------|----|-----------|
| phase3 1.1 | save_assets full DELETE | **fixed** → Issue 1（单工作区 B）· `7156dc4` |
| phase3 1.2 | cached_scan 窄 except | **fixed** → Issue 2 · `b180292` |
| phase3 1.5 | scan vs `_busy` | **fixed** → Issue 3 · `b180292` |
| 本审 Issue 4–5 | 取消扫描 / 任务 ok | **fixed** · `b180292` |
| phase3 1.3 | platform_defaults 未用 | open → Issue 9 |
| phase3 1.4 | scheme_for_path | open → Issue 10 |
| phase3 1.6 | on_done Signal | open → Issue 8 |
| phase3 1.7–1.10 | 双遍 walk / 增量剪枝等 | open → Issue 11–12 |
| 原 Issue 6 | 回源文案 | open · P3 顺手 |
| 原 Issue 7 | 方案分词 | open · **并入 Issue 19** |
| task-exchange | 点方案空白/只剩手控 | **Issue 19 · 下一轮 P0** |
| task-exchange | 全部视图名称同质化 | **Issue 20 · 下一轮 P1** |
| 型号 Combo 常驻 | — | intentional |

---

## 3. 优点（非问题）

- Qt 日志线程安全：`log_message` Signal → `_append_log`  
- 注册表隔离：`ui_qt/operation_panels/registry.py` 与 CTk 互不踩 key  
- `SchemeWorkbenchModel` 多型号、平台隔离、树标签对外 `定制专属`/`通用默认` 设计正确  
- `app.py` 默认 CTk；coverage omit `ui_qt/*`  
- 型号 EditableComboBox 防抖与前缀碰撞处理合理且有测  
- 单工作区索引语义与扫描弹目录已人验  

---

## 4. 建议修复顺序（修订）

| 序 | 项 | 动作 | 性质 | 状态 |
|----|----|------|------|------|
| — | 1–5 | 已合入 | — | ✅ |
| — | 19 / 20 / 6 / 7 | 方案树 + 全部可辨认 + 回源文案 | — | ✅ `2e745fa` |
| 1 | 13 | 方案树 ★默认徽章 | 中优 | open |
| 2 | 8–12, 14–15 | polish / 产品确认 | 低–中 | open |
| 3 | 16–18 | nit | 低 | open |
| 4 | Phase 4 | 默认切 Qt | 迁移 | 建议遗留 suggestion 视情况处理 |

---

## 5. 状态总表

- [x] Bug Issue 1–5（`7156dc4` / `b180292`）  
- [x] Bug Issue 6 / 7 / 19 / 20 + 侧栏高亮（`2e745fa`，人验通过）  
- [ ] Suggestion 8–15 / Nit 13、16–18  
- [ ] 人验仍开放：真 U 盘烧录、暗色主题、设默认全流程  
- [ ] Phase 4 默认切 Qt  
- [x] 历史审查已迁入 `docs/code-review/archive/`（见 `archive/INDEX.md`）  

---

## 6. 关联 Commit / 计划

| 类型 | 引用 |
|------|------|
| Commit | `7156dc4` 单工作区 + 扫描弹目录 |
| Commit | `b180292` 互锁与结果契约 Issue 2–5 |
| Commit | `2e745fa` 方案树/全部可辨认 + 侧栏高亮 |
| 计划 | `specs/active/TASK-20260708-pyside6-migration.md` |
| 迁移 | `docs/migrations/MIGRATION-20260709-single-workspace-index.md` |
| 审查归档 | `docs/code-review/archive/INDEX.md` |

---

## 7. 修订说明（给审阅者）

本次**仅改本文档，未改业务代码**，目的：

1. 同步 Issue 1–5 已修状态与 commit；  
2. 把 `task-exchange.md` 上升为 **Issue 19 / 20**，避免继续按「只修 6、7」排期；  
3. 写清 6/7 与人验缺陷的关系与合并策略；  
4. 下一轮实现以 §4 顺序为准，**等你审过本文件后再动代码**。  

产品决策（用户 2026-07-09 已确认）：

- [x] Issue 19：**A** — 进入定制方案时默认满树；切换方案时清空顶部搜索，避免残留词过滤整机树；方案内若用户之后再搜，过滤语义对齐 `_filter_assets`（含原 Issue 7）  
- [x] Issue 20：**示例 A** — 程序名称 = 变体 `directory_name`（不再压成与类型同名的「默认」空壳）；程序归属 = `通用默认` 或 `定制专属 · {scheme_name}`  
- [x] Issue 7 并入 19；Issue 6 顺手（卡片层禁「回源」）
