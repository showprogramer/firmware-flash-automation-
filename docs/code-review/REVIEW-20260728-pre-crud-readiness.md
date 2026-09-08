# REVIEW-20260728: CRUD 准入审查（Pre-CRUD Readiness）

> **2026-09-03 状态更新**：4 项基础 gate（R1/R10、R5、R3、R8）已全部完成；
> 「CRUD 写语义 gate」已由 **TASK-20260903-crud-write-semantics** 定稿（D0–D10 共
> 11 项，codex 七轮审查），实现按该任务的子 TASK 拆分依次推进，从「公共事务基础」起。
> 历史初稿（2026-07-28）与 `705fe60` 基线分析见 git 历史。

| 项 | 内容 |
| --- | --- |
| 类型 | 准入审查 / 架构边界 |
| 模块 | `core/asset_index.py`、`core/reference_lookup.py`、`core/services/reference_service.py`、`core/path_guard.py`、`core/file_scan.py`、`core/services/*`、`ui_common/workbench_helpers.py`、`ui_qt/workbench_window.py` |
| 状态 | ✅ 准入审查完成（4 项基础 gate 已关闭；CRUD 写语义 gate 已定稿，转入实现子 TASK） |
| 相关 TASK | ✅ TASK-20260803-r5-path-guard、✅ TASK-20260806-r1-r10-write-gate、✅ TASK-20260806-independent-crud-web-prototype、✅ TASK-20260901-r3-index-write-api、✅ TASK-20260901-r8-reference-integrity、⏳ TASK-20260903-crud-write-semantics（写语义定稿，待开工子 TASK） |
| 基线 | `feature/pyside6-migration`；`uv run python -m pytest -q` → 574 passed，coverage 94.56%（门禁 80%） |

## 审查目标

判断当前 Qt-only、配置、索引、固件目录与测试体系，是否已经可以安全进入「软件直接改真实程序文件」的 CRUD 阶段。

**范围边界**：只审当前 CRUD 准入相关的 gate 项；不重审历史代码、不重审已归档 TASK/REVIEW。已归档结论（Qt-only 收口、共享引用语义、平台默认写回）默认成立，只在 CRUD 会破坏它们时才提出。

## 现行产品规则（以 HTML 原型为准）

CRUD 的交互与产品语义由 `specs/design/prototypes/firmware-crud-prototype.html` 定稿（TASK-20260806-independent-crud-web-prototype，人工验证通过）。**正式 CRUD TASK 立项时以该原型及其任务文件「当前规则」一节为准**，此前 2026-08-07 的产品修正（`handcontrol_ui` 版本唯一来自 `.rom` 文件名、复制手控文件到 U 盘文案、主表隐藏历史版本等）继续有效。与本文关系最密切的规则：

- **CRUD 范围**：型号与定制方案的新建/重命名/删除，程序（变体目录）的新增/更新（含回收站备用副本）/重命名/删除，以及借用登记。复制、移动程序仍不在范围。
- **型号是一等单元**：独立目录 + `型号配置.toml` + 机芯类型（枚举 `单3D`/`单2D`/`双2D`/`上3D下2D`），全部在软件内创建，不靠资源管理器。删除型号/方案 = 其下程序送系统回收站，可撤销。
- **借用（共享）按「型号 → 型号、每程序类型一条」**：两种模式 `static`（固定用这个程序）/ `follow_asset`（跟随来源程序的后续更新）。UI 一律用「借用」等大白话，禁止出现 TOML、引用、共享/共用、配置键、展示层的「平台」等术语。
- **归属厂商**：`VENDORS` 预置 `摩众`/`国瑞`/`亿微`/`明锐`，名单在设置里可添加，不写死在代码里。
- **写操作交互**：立即生效 + 提示条撤销；删除前反查「谁在用」并二次确认，有借用时必须勾选；更新程序放入新文件后才询问旧程序去向（回收站 / `旧版本/` 备用副本）。

## 准入结论

### 🟢 Go（4 项基础 gate 已全部关闭；CRUD 写语义 gate 已定稿）

**可以按 TASK-20260903-crud-write-semantics 的子 TASK 拆分开始实现**，从「公共事务基础」起。该任务已冻结用户可观察语义与跨模块不变量；事务基础设施的内部设计（候选区生命周期、日志分阶段恢复、`WorkspaceState` 落盘顺序、R8 部分 apply 恢复算法）按其「下放到实现子 TASK 的不变量」一节在对应子 TASK 定稿，且须在写代码前完成审查。

理由摘要：

- **写入口已收口**：R5 路径守卫 + R1/R10 写入门闩覆盖全部写入口；R3 附带补齐了 `ensure_model_ids` 的门闩缺口（配置根必填、未配置零写盘）。
- **索引层就绪（R3）**：`upsert_asset` / `replace_asset` / `delete_asset` / `bulk_reindex_subtree` 定点写 + `scan_firmware_subtree` 子树扫描 + `reconcile_subtree` 对账兜底，单事务含 hidden_items 同步。
- **引用层就绪（R8）**：`reference_lookup.find_references_to` / `find_dangling_anchors` 反查（严格 TOML 冷读）、`follow_asset` 借用语义与 `follow_default` 存量迁移、`build/apply_rewrite_plan` 级联改写（preimage CAS 回滚）、删除零 TOML 改写（可逆）。
- **剩余阻断**：更新程序改类型/改范围的默认与借用迁移、型号/方案创建删除的事务/撤销编排、路径身份不复用预检、`旧版本/` 备用副本作为借用来源——这些是产品语义决策，不是架构缺口。

**不是 No-Go 的原因**：缺口都是可加固的，不是架构性错误。领域模型（通用/定制/共享）对 CRUD 自洽，不需要推倒重来；原型也未推翻「目录树 + TOML 是真源、SQLite 是搜索缓存」的结构派生原则。

---

## 已关闭项（现状摘要）

### R5 ✅ 统一工作区路径守卫（TASK-20260803，Windows 实机验证通过）

`core/path_guard.py`（67 行）：`PathGuardError` + `assert_within_workspace(path, workspace_root) -> Path`。契约：空根拒绝、必须绝对路径、resolve 前显式拒绝 `..`、resolve 后 `os.path.normcase` + 统一正斜杠比较（先 normcase 再转斜杠——初版顺序在 Windows 上导致误拒，已修并补回归测试）、允许目标等于工作区根。已接入全部写入口：`set_shared_module`（源资产 + 目标根）、`clear_shared_module`、`set_default_variant`、`set_module_default_for_model`；`shared_module_resolver` 的读端词法检查委托守卫。测试见 `tests/test_path_guard.py`（100% 覆盖）。

### R1/R10 ✅ 统一写入门闩（TASK-20260806-r1-r10-write-gate）

- 纯函数 `ui_common/workbench_helpers.write_gate_check(configured_root, scanned_root, target_path) -> ServiceResult`，三检查依次：配置根为空 → `not_configured`；已读工作区根 ≠ 配置根 → `root_changed`；路径守卫拒绝 → `out_of_workspace`。所有路径比较经 `Path.resolve()` + `os.path.normcase`。
- UI 包装 `ui_qt/workbench_window._write_gate()`（`:852-868`）叠加任务态检查：扫描中（`scan_state_model.is_scanning`）与烧录任务中（`_busy`）一律禁写。
- 三层权威来源已落实：配置文件 `root_dir` 是写操作权威；`scan_meta`（`active_workspace_root()`）仅作缓存恢复；配置为空或根不一致时只读浏览 + 前往设置。
- **✅ 覆盖缺口已收口（R8，TASK-20260901）**：`ensure_model_ids()` 增加 `configured_root` 必填门闩——未配置零写盘（model_id 只读降级）、整批先校验归属（越界/非法根整批 `out_of_workspace`/`invalid_root` 零写）、scan_meta 兜底恢复路径不再被当作配置根；既有重复 model_id 计入报告。

---

## 已关闭项（R3/R8 现状摘要）

### R3 ✅ 索引行级写 API + 子树扫描/对账（TASK-20260901-r3-index-write-api）

- `asset_index` 新增 `upsert_asset` / `replace_asset` / `delete_asset` / `bulk_reindex_subtree` 四个行级写接口：单事务含 `hidden_items` 同步、整批原子校验、单工作区根一致性校验、normcase 身份匹配；顺带修复 `prune_missing_hidden_items` 的 `startswith` A/AB 前缀混淆缺陷。
- `file_scan` 重构共享扫描核心并新增 `scan_firmware_subtree(workspace_root, subtree_root)`；`asset_reconcile.reconcile_subtree` 提供失败后按磁盘真相重扫的冷接口。
- 「路径变化不能只改 path、须重扫生成完整新行」与「先动文件、再动库、失败重扫子树」策略已在接口契约与测试中固化。验证：Windows 477 passed / 95.18%（当时基线），codex 两轮实现审查通过，`scripts/verify_r3_write_api.py` 四类场景人工验证通过。

### R8 ✅ 引用反查与级联完整性（TASK-20260901-r8-reference-integrity，实现审查与人工验证通过）

- **反查**：`core/reference_lookup.py` 的 `find_references_to`（static/follow 类借用 + 平台默认，四种 target_kind，owner 限定与联合身份）与 `find_dangling_anchors`（路径身份复用预检）；严格 TOML 冷读，损坏/非法条目进 issues 不静默。
- **借用语义**：`SharedModuleRef.mode` 扩为 `static` / `follow_default`（兼容读）/ `follow_asset`（跟随来源具体程序）；`migrate_follow_default_refs` 幂等迁移存量数据（详见 `docs/migrations/MIGRATION-20260901-r8-follow-asset.md`）。
- **级联**：`core/services/reference_service.py` 的 `build_rewrite_plan` / `apply_rewrite_plan`——结构化 `RewriteRequest`、preimage 双 SHA-256、统一配置根 gate、`stale_plan`/`invalid_operation`/`unsupported_semantic_change` 等阻止码、CAS 回滚（恢复到当前物理位置）；删除**零 TOML 改写**（借用条目保留、解析自然 missing、回收站撤销即恢复）。
- **门闩收口**：`ensure_model_ids` 见上。
- **CRUD 写语义 gate 已定稿**（TASK-20260903）：改类型/改范围不再走 update 级联而是独立复合操作（`unsupported_semantic_change` 保持不变）、型号/方案/程序创建删除事务语义、路径身份不复用预检（`path_identity_conflict`）、`旧版本/` 副本不得作借用来源（`retired_anchor`）。

---

## 原型与当前 core 的差异清单（正式 TASK 立项前逐项定稿）

| # | 差异点 | 现状 | 待定稿 |
| --- | --- | --- | --- |
| 1 | 借用 `follow_asset`（跟随指定程序） | ✅ 已实现（R8）：锚定 `source_relative_path` + 操作矩阵级联保证跟随；`follow_default` 存量提供幂等迁移 | 无（稳定标识采用「路径 + 级联 + 身份不复用约束」方案，不引入 UUID） |
| 2 | 机芯类型枚举（`单3D`/`单2D`/`双2D`/`上3D下2D`） | `platform` 是方案/平台 TOML 里的自由文本块 | 枚举与 `[[platform]]` 块的映射；多个平台块并存时默认写哪一块 |
| 3 | 归属厂商名单（设置内可添加） | 生产源码无 vendor 配置或资产字段 | 名单存放位置（`config.toml` 或独立 TOML）；程序资产上厂商字段的落盘与派生 |
| 4 | 新建/删除型号、新建/删除方案 | 只有扫描发现；无型号/方案的创建、重命名、删除服务（删除的引用侧级联已由 R8 零改写语义覆盖） | 目录与 TOML 的创建/删除事务语义；删除型号的级联范围（CRUD 写语义 gate） |
| 5 | 更新程序 → `旧版本/` 备用副本 | 无此概念 | `旧版本/` 的落点；扫描器排除确认；`usb_ops.copy_directory_to_usb` 整目录 copytree（无 ignore），副本目录若在变体内会被拷进 U 盘 |
| 6 | UI 术语（借用、程序文件、机芯类型…） | Qt 界面仍是「共享模块/登记共享来源」等旧术语 | 术语映射表，含右键菜单改造（原型：右键只保留上下文相关操作） |

---

## 仍然有效的约束（非阻断）

- **R9 `_默认` 后缀**：默认变体只由 `平台配置.toml` 定义，`_默认` 后缀是 legacy 显示、永不作为写目标。重命名不得因名字带上/去掉 `_默认` 改变默认归属；改名后同步更新 `defaults` 值（属 R8 级联）。
- **版本规则**：版本号只对 `handcontrol_ui` 有业务意义，唯一来源是该目录内 `.rom` 文件名解析（`file_scan._extract_model_version` + `parse_rom_filename`，要求目录同时含 `.rom` 与 `.pkg`）。不得从 `.pkg` 文件名、目录名或独立 TOML 覆写；其他程序类型的版本不作为搜索/排序/分组/CRUD 字段。
- **扫描器排除规则**：认准 `file_scan._is_excluded_dir(dirpath)`（匹配整个路径，关键词 `settings.SCAN_EXCLUDE_DIR_KEYWORDS = ["CH341SER","接线图","旧","新建文件夹","照片"]`，硬编码不再读用户配置）；`scheme_config._is_excluded_dir(name)` 只服务方案发现。原型要求的排除 `旧版本/` 目前靠「旧」关键词子串匹配覆盖——若未来收紧关键词需显式验证。
- **删除落盘**：删除语义 = 系统回收站。Windows 自带 `shell32.SHFileOperationW` + `FOF_ALLOWUNDO` 经 `ctypes` 调用可行且零新依赖（先前本机实测，见 git 历史验证记录）；应用侧统一确认需加 `FOF_NOCONFIRMATION`，调用前探测目标卷是否支持回收站（`rc=0` 不保证进回收站，网络盘可能退化永久删）。
- **测试分层**（原 R11 收敛）：纯单测（守卫/反查/行级写 SQL）+ `tmp_path` 完整树集成测（**必须同时断言磁盘与库**：操作后 `query_assets()` 的 path 集合 == 磁盘实际扫描结果）+ 每个 CRUD 子 TASK 一轮冻结 exe 人验 + 改动影响 USB 复制时回归「复制手控文件到 U 盘」。
- **`schema_version` 不匹配**直接抛 `AssetIndexError` 要求重扫的行为保留；错误文案可区分「版本旧需升级」与「库损坏」，体验改进不阻断。

---

## 前置条件清单（已全部满足）

在当前范围 CRUD 开放写操作前必须完成下列项。任何真实目录写入先满足 #2；涉及删除或改变被引用路径的操作再叠加 #4：

| # | 前置项 | 对应 Issue | 复杂度 | 状态 |
| --- | --- | --- | --- | --- |
| 1 | 配置根作为写操作权威 + scan_meta 一致性校验 + 未配置时禁用写入口 | R1、R10 | medium | ✅ 已完成（TASK-20260806-r1-r10-write-gate）；✅ `ensure_model_ids` 覆盖缺口已由 R8 收口（配置根必填门闩） |
| 2 | 统一路径守卫 `assert_within_workspace` | R5 | medium | ✅ 已完成（TASK-20260803-r5-path-guard，Windows 实机验证通过） |
| 3 | CRUD 定点写 API + 保留工作区上下文的局部扫描/子树对账 + SQLite 事务 + 文件/索引失败恢复策略（不含 schema 迁移；SQLite 事务不包含文件系统动作） | R3 | high | ✅ 已完成（TASK-20260901-r3-index-write-api：4 行级写 API + `scan_firmware_subtree` + `asset_reconcile.reconcile_subtree`；经 codex 两轮实现审查「实现合格，无阻断问题」；人工验证按无 UI 等效规则以 `scripts/verify_r3_write_api.py` 四类场景通过 + 用户确认；含 `hidden_items` A/AB 前缀缺陷修复） |
| 4 | TOML 引用反查 + 删除二次确认 + 重命名/更新时级联改写或阻止断链（含原型差异清单 #1、#4 的语义定稿） | R8 | high | ✅ 引用基础能力完成（TASK-20260901-r8-reference-integrity：`reference_lookup` 反查 + `follow_asset` 语义与存量迁移 + `build/apply_rewrite_plan` preimage CAS 回滚级联 + `ensure_model_ids` 门闩收口；Windows 574 passed / 94.56%）。✅ **CRUD 写语义 gate 已定稿**（TASK-20260903-crud-write-semantics）：改类型/改范围拆为独立复合操作、型号/方案/程序创建删除事务语义、路径身份不复用预检、备用副本不得作借用来源 |

**基础 gate 4 项已全部关闭；「CRUD 写语义 gate」已由 TASK-20260903-crud-write-semantics 定稿**（D0–D10）——含改类型/改范围复合操作、型号/方案/程序创建删除事务、路径身份不复用预检、`旧版本/` 备用副本、机芯类型映射、厂商元数据、导入成形、工作区读写锁、单根布局边界与撤销范围。差异清单 #2/#3 已在该任务定稿；#6（UI 术语映射）留待 UI 子 TASK。

**实施顺序**：~~R3 → R8~~ → ~~CRUD 写语义定稿~~（已完成）→ 按该任务的子 TASK 拆分依次实现：公共事务基础 → 元数据与 schema → 准入与导入原语 → 型号/方案 CRUD → 程序新增/删除/待补齐 → 默认/元数据/借用编辑 → 布局归一与程序更新 → 存量 platform 归一 → UI 编排。

---

## 验证记录

### 自动化验证（2026-09-01，R8 实现完成）

```text
uv run python -m pytest -q
→ 574 passed；coverage 94.56%（门禁 80%）
uv run ruff check src scripts / uv run mypy → 通过
uv run python scripts\verify_r8_reference_integrity.py → 四类场景全部通过
```

- R3 验证（历史基线）：477 passed / 95.18%；`scripts/verify_r3_write_api.py` 四类场景通过 + 用户确认。
- codex 实现审查（七轮）最终结论：「实现合格，无阻断问题」；历轮发现的 P0/P1/P2 全部修复并补回归测试。
- 历史初稿验证（394 passed / 88.82% 基线、静态枚举、codex 初次复核）见 git 历史 @705fe60 时的本文版本。

### 历史实测证据（详见 git 历史 @705fe60 之前的本文版本）

- v3 schema 单事务行级写能力验证；路径变化的连带字段实测（重命名 4 字段 / 跨归属移动 5 字段）；回收站删除实测（`SHFileOperationW` + `FOF_ALLOWUNDO`）；切根面板残留判定更正（R2，已结案为 UX 清理项）；版本解析放宽实测（R6e，已撤销）。

### 人工验证

- ✅ R8：人工验证已完成——`uv run python scripts\verify_r8_reference_integrity.py` 四类场景通过 + 用户确认（2026-09-01）。

## 相关 Commit

- `77cbbd0` feat(core,ui): R5 统一工作区路径守卫（TASK-20260803-r5-path-guard）
- `4d4d3c8` feat(core,ui): R1/R10 统一写入门闩（TASK-20260806-r1-r10-write-gate）
- R3 / R8 实现 commit 见对应 TASK 的「完成 commit」字段。
