# 代码审查：feature/pyside6-migration 分支总审

- 日期：2026-07-09
- 类型：分支审查（core 域 + 工作台 + PySide6 双轨）
- 模块：
  - `src/fwasset/core/**`（`asset_index` / `file_scan` / `scheme_config` / `scan_service` 等）
  - `src/fwasset/ui/view_models/scheme_workbench_model.py`
  - `src/fwasset/ui_qt/**`（Phase 0–3 新壳）
  - `src/fwasset/ui/workbench_panel.py`（CTk 对照 / 双轨漂移）
- 范围：`feature/pyside6-migration` vs `origin/main`（merge-base `964aec58`）
- 源码 diff 口径：`src/fwasset/` + `pyproject.toml` + `firmware_catalog.toml` + `scripts/`（84 files, +9662 / -5976）
- 关联：
  - 计划：`specs/active/TASK-20260708-pyside6-migration.md`
  - 同日细审：`docs/code-review/REVIEW-20260709-pyside6-phase3-core.md`（本审查已复核 1.1–1.11 处置）
  - 上轮：`REVIEW-20260708-pyside6-p1-p2.md`、`REVIEW-20260708-platform-default.md`

## 0. 进度与整体评价

### 项目进度

| 阶段 | 状态 |
|------|------|
| 工作台 UI 重写（方案/通用/回源） | ✅ 完成 |
| 设为平台默认 + 多型号根 | ✅ 完成 |
| UI Review Bugfix | ✅ 完成 |
| PySide6 Phase 0–3 | ✅ 完成 |
| **PySide6 Phase 4**（默认切 Qt / CTk 退役 / 打包） | ⏳ 待做 |
| CRUD / 增量重扫 | 📋 规划中 |

**双轨现状**：`app.py` 默认 CTk；`FWASSET_UI=qt` 走 `ui_qt/workbench_window`。Phase 4 前不应默认切 Qt。

### 自动化门禁（本机 2026-07-09）

```
uv run python -m pytest -m "not ui" -q --no-cov
→ 219 passed, 49 deselected in ~11s
```

### 总评

分支在 Phase 0–3 上交付了**扎实**的双轨 Qt 壳：日志经 Signal 回投、`PanelHost` 无 tk 耦合、注册表与 CTk 隔离、`SchemeWorkbenchModel` 多型号/平台隔离正确。默认入口仍 CTk 的选择正确。

**尚不宜直接进入 Phase 4**。阻断风险集中在：扫描与烧录任务无互锁、取消扫描误报「完成 0 项」、任务结束忽略 `ServiceResult.ok`、缓存加载异常契约过窄、索引单表 DELETE 与多行 `scan_meta` 矛盾。同日 Phase3 审查中 1.1–1.6 仍全部 open；本轮新增取消扫描、任务完成文案、方案视图搜索分词等。

**问题统计**：7 bug / 8 suggestion / 3 nit（共 18 项，状态均为 open）。

---

## 1. 发现（按严重度）

### Bug

#### Issue 1 — `save_assets` 全表 DELETE，与多根 `scan_meta` 矛盾
- 文件：`src/fwasset/core/asset_index.py`
- 问题：`DELETE FROM assets` 无条件清空；`assets` 无 `root_dir` 列，而 `scan_meta` 以 `root_dir` 为多行 PK。第二次扫描另一根会静默替换整库，并可能经 `prune_missing_hidden_items` 清掉上一根隐藏项。当前单根使用掩盖风险。
- 建议：**(A)** 加 `root_dir` 并按根 DELETE/query；或 **(B)** 明确单根唯一支持、`scan_meta` 改为单行。补双根连续扫描回归测试。
- 状态：**fixed（选 B）** — 2026-07-09 收口为单工作区：`save_assets` 清空后只写一行 `scan_meta`；模块注释 + `active_workspace_root()`；测试 `test_save_assets_replaces_index_when_workspace_root_changes` / `test_save_assets_clears_stale_scan_meta_rows`；迁移说明 `docs/migrations/MIGRATION-20260709-single-workspace-index.md`。换根 = 切换工作区属 intentional。

#### Issue 2 — `build_cached_scan_result` 异常捕获过窄
- 文件：`src/fwasset/core/services/scan_service.py`
- 问题：仅 `except AssetIndexError`。DB 忙时可裸抛。
- **处置（2026-07-09）**：`except Exception` → `index_unavailable`；测试 `test_build_cached_scan_result_maps_db_errors_to_index_unavailable`。
- 状态：**fixed**

#### Issue 3 — 扫描与操作任务无互锁
- 文件：`src/fwasset/ui_qt/workbench_window.py`、`ui/workbench_panel.py`
- 问题：烧录中可再扫；扫描完成拆除操作面板。
- **处置（2026-07-09）**：`_start_scan` 检查 `_busy`；`_run_task` 检查 `is_scanning`（CTk 覆盖、Qt 内联）。契约测试 `test_workbench_scan_task_mutual_exclusion_contract`。
- 状态：**fixed**

#### Issue 4 — 取消扫描被当成「扫描完成 0 项」
- 文件：`src/fwasset/ui_qt/workbench_window.py`、`ui/workbench_panel.py`
- 问题：`code=cancelled` 仍记完成并 rebind 空结果。
- **处置（2026-07-09）**：`code == "cancelled"` 只打取消消息并 return，不 rebind。测试 `test_workbench_handles_cancelled_scan` + `test_build_scan_result_cancelled`。
- 状态：**fixed**

#### Issue 5 — 任务结束一律打「完成」，忽略 `ServiceResult.ok`
- 文件：`ui_qt/workbench_window.py`、`ui/base_panel.py`
- 问题：`ok=False` 仍显示完成。
- **处置（2026-07-09）**：按 `result["ok"]` 区分完成/失败；失败弹窗。测试 `test_service_result_ok_false_logs_failure_not_done` + 契约测试。
- 状态：**fixed**

#### Issue 6 — `ModuleCardData.source_label` 仍含「回源」
- 文件：`src/fwasset/ui/view_models/scheme_workbench_model.py:614`
- 问题：`get_scheme_modules` 回源卡写 `source_label=f"通用/{src_dir} (回源)"`。域规则禁止用户可见「回源」。`get_scheme_module_tree` / DataGrid 已 remap，主表安全，但卡片 API 文档称可展示，后续消费者会泄漏。
- 建议：中间层即用 `通用默认`；「回源」仅内部注释/变量名。
- 状态：open

#### Issue 7 — 方案/整机视图搜索不做空格分词
- 文件：`src/fwasset/ui/view_models/scheme_workbench_model.py:538-617`
- 问题：全部/通用走 `_filter_assets` 分词 AND；`get_scheme_modules` 对 `label`/`directory_name` 做**整串** substring（543-544、605-606）。「手控 V13」在方案视图会失败。CTk/Qt 方案视图均走 `get_scheme_module_tree(..., search_kw)`。
- 建议：定制资产与回源通用资产统一走 tokenized 过滤（复用 `_filter_assets` 语义）。
- 状态：open（**本轮新增强调**）

---

### Suggestion

#### Issue 8 — `on_done` 经跨线程 Signal 透传 callable
- 文件：`src/fwasset/ui_qt/workbench_window.py:79`（emit 约 227）
- 问题：worker 把 `on_done` 作 `object` 经 queued Signal 传到 UI。当前 PySide6 可用，但脆弱；仅 directory_flash 使用。
- 建议：worker 内直接调 `on_done`；Signal 仅传 `(name, result)`。
- 状态：open（对应 1.6）

#### Issue 9 — `file_scan` 加载平台配置后未使用
- 文件：`src/fwasset/core/file_scan.py:177`
- 问题：`platform_defaults = load_platform_config(root_path)` 死代码；多型号父根时路径也不对。通用资产 `platform` 仅双机芯硬编码段有值。
- 建议：删除死调用，或按型号 TOML 真正解析（若产品需要）。回源默认应继续在 workbench model，不在 scanner。
- 状态：open（对应 1.3）

#### Issue 10 — `scheme_for_path` 非最长前缀
- 文件：`src/fwasset/core/scheme_config.py:102-107`
- 问题：按列表顺序第一个前缀匹配即返回；嵌套/重叠方案目录会绑错。`discover_schemes` 只走 `定制` 与 `*/定制`。
- 建议：按路径深度降序匹配；必要时 `rglob("方案配置.toml")`。
- 状态：open（对应 1.4）

#### Issue 11 — 扫描双遍目录树
- 文件：`src/fwasset/core/services/scan_service.py:27`
- 问题：`find_handcontrol_folders` 再次 `scan_firmware_assets`，I/O 翻倍；第二遍不响应 cancel。
- 建议：从已扫 `assets` 派生 handcontrol folders。
- 状态：open（对应 1.7）

#### Issue 12 — 增量扫描未剪枝子树（潜伏）
- 文件：`src/fwasset/core/file_scan.py:194-200`
- 问题：`dir_mtime < last_scan_at` 时 `continue` 未 `dirs[:] = []`。当前 `build_scan_result` 全量扫，潜伏。
- 建议：跳过时清空子目录列表，或删掉未完成的增量路径。
- 状态：open（对应 1.10）

#### Issue 13 — 方案视图无 ★默认 徽章
- 文件：`src/fwasset/ui/view_models/scheme_workbench_model.py:642-648`
- 问题：`get_scheme_module_tree` 未传 `default_badge`；`get_scheme_modules` 也不设。整机视图无 ★默认，全部/通用有。
- 建议：回源/通用卡设置 `default_badge=self.default_badge(a)` 并贯穿 tree。
- 状态：open

#### Issue 14 — CTk 未从 scan_meta 恢复 root（双轨漂移）
- 文件：`src/fwasset/ui/workbench_panel.py:772-776`
- 问题：Qt 在 `DEFAULT_ROOT` 空时从 `scan_meta` 恢复根；CTk 仍绑 `Path(".")`，可产生假型号噪声。
- 建议：Phase 4 前 port 到 CTk，或确认 CTk 不再交付后只修 Qt。
- 状态：open

#### Issue 15 — `segmented_screen` flash_mode 变更是否 intentional
- 文件：`firmware_catalog.toml:12-21`
- 问题：断码屏由 `auto_usb`+`paired_files` 改为 `tool_launch`+`tool_dir`。迁移分支上的产品行为变更。
- 建议：与业务确认；有意则写 CHANGELOG，无意则回退。
- 状态：open

---

### Nit

#### Issue 16 — 方案头徽章文案双轨不一致
- 文件：`src/fwasset/ui_qt/workbench_window.py:535` vs CTk `workbench_panel.py:513`
- 问题：Qt `整机模块` / CTk `整机七程序`；`STANDARD_MODULE_ORDER` 已 8 项，「七」过时。
- 建议：统一为 `整机模块` 或共享常量。
- 状态：open

#### Issue 17 — DataGrid `clear` 未 blockSignals
- 文件：`src/fwasset/ui_qt/data_grid.py:62-63`
- 问题：`tree.clear()` 可触发 `itemSelectionChanged` 重入。
- 建议：clear/populate 包 `blockSignals`。
- 状态：open

#### Issue 18 — SQLite 默认 timeout / 线程亲和
- 文件：`src/fwasset/core/asset_index.py:30-38`
- 问题：默认 ~5s busy timeout；长事务阻塞读路径时 `OperationalError` 可能裸出。
- 建议：提高 timeout；文档声明单写者；只读辅助可选宽捕获。
- 状态：open（对应 1.8）

---

## 2. 与同日 Phase3 审查对照

| 先前 ID | HEAD 处置 |
|---------|-----------|
| 1.1 save_assets full DELETE | **仍 open** → Issue 1 |
| 1.2 cached_scan 窄 except | **仍 open** → Issue 2 |
| 1.3 platform_defaults 未用 | **仍 open** → Issue 9 |
| 1.4 scheme_for_path 顺序 | **仍 open** → Issue 10 |
| 1.5 scan vs `_busy` | **仍 open** → Issue 3 |
| 1.6 on_done Signal | **仍 open** → Issue 8 |
| 1.7 双遍 walk | **仍 open** → Issue 11 |
| 1.8 connect timeout | **仍 open** → Issue 18 |
| 1.9 handcontrol_ui 短路 | 仍成立；特殊规则/低优，本轮不升优先级 |
| 1.10 增量无剪枝 | **仍 open**（潜伏）→ Issue 12 |
| 1.11 typeddict ignore | 仍成立；nit，本轮不单列 |
| 型号 Combo 常驻 | 确认 intentional（用户需求 + smoke 测试） |
| 搜索空格分词 | 部分：全部/通用 OK；**方案视图坏** → Issue 7 |

---

## 3. 优点（非问题）

- Qt 日志线程安全：`log_message` Signal → `_append_log`
- 注册表隔离：`ui_qt/operation_panels/registry.py` 与 CTk 互不踩 key
- `SchemeWorkbenchModel` 多型号、平台隔离、树标签 `定制专属`/`通用默认` 正确
- `app.py` 默认 CTk；coverage omit `ui_qt/*`
- 型号 EditableComboBox 防抖与前缀碰撞处理合理且有测

---

## 4. 建议修复顺序（Phase 4 前）

| 序 | Issue | 动作 | 性质 |
|----|-------|------|------|
| 1 | 3 | 扫描 ↔ 任务互锁 | 并发 |
| 2 | 4 | 取消扫描正确分支 | UX / 正确性 |
| 3 | 5 | 任务结果看 `ok` | UX / 正确性 |
| 4 | 2 | `build_cached_scan_result` 宽捕获 | 契约 / 启动 |
| 5 | 7 + 6 | 方案搜索分词 + 去掉「回源」卡片文案 | 验收 / 域规则 |
| 6 | 1 | 索引单根语义落地 + 测试 | 设计债 |
| 7 | 8–15 | polish / 产品确认 | 中低优 |

---

## 5. 状态

- [x] Bug Issue 1 已修（单工作区语义 B）
- [x] Bug Issue 2–5 已修（缓存契约 / 互锁 / 取消文案 / 任务 ok）
- [ ] Bug Issue 6–7 待修（回源文案 / 方案视图分词）
- [ ] Suggestion Issue 8–15 待定
- [ ] Nit Issue 16–18 可选
- [x] 自动化门禁：`219 passed, 49 deselected`（`-m "not ui"`）
- [ ] 人验：真 U 盘烧录、暗色主题、设默认全流程、扫描与任务互锁
- [ ] Phase 4 默认切 Qt：**阻塞于上述 bug 收敛**
- [ ] Commit：审查归档本身；代码修复另开轮次，人验通过后再按 `docs/COMMIT_TEMPLATE.md` 提交

## 6. 关联 Commit / 计划

- `72f8a70` feat(qt): 型号可搜索下拉改常驻 + 切换防抖
- `b091730` feat(qt): 操作面板与后台任务迁移（Phase 3）
- `1e0e4ef` fix(qt): 落实 P1-P2 代码审查整改
- `9dddc41` feat(qt): Qt 工作台壳与数据面（Phase 1+2）
- `f12b0ed` chore(qt): Phase 0 spike
- 计划：`specs/active/TASK-20260708-pyside6-migration.md`（Phase 3 完成，Phase 4 待启动）
