# REVIEW-20260728: CRUD 准入审查（Pre-CRUD Readiness）

> **2026-09-01 重构更新**：本文按当前源码（`705fe60`）与 HTML 网页原型（TASK-20260806）整体重写。
> 已关闭项（R1/R10、R5）压缩为现状摘要；已撤销/不适用项（R2、R4、R6b/R6c/R6d/R6e、R7、R12）的历史分析不再保留，需要时查本文件在 `705fe60` 之前的 git 版本。
> 文中所有行号与 API 名以 `feature/pyside6-migration` @ `705fe60` 为准。

| 项 | 内容 |
| --- | --- |
| 类型 | 准入审查 / 架构边界 |
| 模块 | `core/asset_index.py`、`core/path_guard.py`、`core/file_scan.py`、`core/services/*`、`ui_common/workbench_helpers.py`、`ui_qt/workbench_window.py` |
| 状态 | 🔄 进行中（R1/R10、R5 已关闭；R3、R8 未开始；产品交互规则已由 HTML 原型定稿） |
| 相关 TASK | ✅ TASK-20260803-r5-path-guard（已完成）、✅ TASK-20260806-r1-r10-write-gate（已完成）、✅ TASK-20260806-independent-crud-web-prototype（人工验证通过，待提交）、⏳ 正式 CRUD TASK（待立项，本审查为其前置） |
| 基线 | `feature/pyside6-migration` @ `705fe60`；`uv run python -m pytest -m "not ui" -q` → 394 passed, 31 deselected，coverage 88.82%（门禁 80%） |

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

### 🟡 Conditional Go（gate 已关闭 2/4，仍不允许真实目录写入）

**可以立正式 CRUD TASK；但对「新增 CRUD 写入口」仍要求先关闭 R3、R8。** 现有元数据写入口（设为默认、共享登记/取消登记）已被统一门闩和路径守卫覆盖，这是相对 2026-07-28 初稿的主要进展。

理由摘要：

- **写入口已收口（有一处缺口）**：R5 路径守卫（`core/path_guard.py`）+ R1/R10 写入门闩（`ui_common/workbench_helpers.write_gate_check` + `ui_qt/workbench_window._write_gate`）已实现并经 Windows 实机验证；既有交互式 TOML 写入口均已接入，唯一例外是 `ensure_model_ids` 的自动写入（详见「已关闭项」的覆盖缺口）。
- **TOML 写语义成熟**：`model_config._merge_write_model_config()` 读全量 dict → 局部 mutate → 原子写回且解析失败拒绝当空 dict 覆盖；`atomic_write_text()` 同目录临时文件 + `fsync` + `os.replace`。注意 `platform_config.save_platform_config()` 按「应用托管文件」契约整体重写、不承诺保留未知键，不能把 `model_config` 的合并语义泛化到所有 TOML。
- **阻断点仍在索引层与引用层**：`assets` 仍只有全量替换 `save_assets()` 和对账式 `delete_missing_assets()`，没有定点 upsert / replace / delete / 子树重建 API（R3）；文件操作会打断 TOML 引用且无写前反查（R8）。
- **原型扩大了 CRUD 面**：型号/方案成为可新建、删除的一等单元，「更新程序」会产生 `旧版本/` 备用副本与默认/借用迁移问题——这些都落在 R3/R8 的能力范围内，但具体动作语义要在正式 TASK 中按原型逐条定稿。

**不是 No-Go 的原因**：缺口都是可加固的，不是架构性错误。领域模型（通用/定制/共享）对 CRUD 自洽，不需要推倒重来；原型也未推翻「目录树 + TOML 是真源、SQLite 是搜索缓存」的结构派生原则。

---

## 已关闭项（现状摘要）

### R5 ✅ 统一工作区路径守卫（TASK-20260803，Windows 实机验证通过）

`core/path_guard.py`（67 行）：`PathGuardError` + `assert_within_workspace(path, workspace_root) -> Path`。契约：空根拒绝、必须绝对路径、resolve 前显式拒绝 `..`、resolve 后 `os.path.normcase` + 统一正斜杠比较（先 normcase 再转斜杠——初版顺序在 Windows 上导致误拒，已修并补回归测试）、允许目标等于工作区根。已接入全部写入口：`set_shared_module`（源资产 + 目标根）、`clear_shared_module`、`set_default_variant`、`set_module_default_for_model`；`shared_module_resolver` 的读端词法检查委托守卫。测试见 `tests/test_path_guard.py`（100% 覆盖）。

### R1/R10 ✅ 统一写入门闩（TASK-20260806-r1-r10-write-gate）

- 纯函数 `ui_common/workbench_helpers.write_gate_check(configured_root, scanned_root, target_path) -> ServiceResult`，三检查依次：配置根为空 → `not_configured`；已读工作区根 ≠ 配置根 → `root_changed`；路径守卫拒绝 → `out_of_workspace`。所有路径比较经 `Path.resolve()` + `os.path.normcase`。
- UI 包装 `ui_qt/workbench_window._write_gate()`（`:852-868`）叠加任务态检查：扫描中（`scan_state_model.is_scanning`）与烧录任务中（`_busy`）一律禁写。
- 三层权威来源已落实：配置文件 `root_dir` 是写操作权威；`scan_meta`（`active_workspace_root()`）仅作缓存恢复；配置为空或根不一致时只读浏览 + 前往设置。
- **⚠️ 已知覆盖缺口（2026-09-01 codex 复核发现）**：`core/services/model_id_service.ensure_model_ids()` → `save_model_id()` 会为缺 id 的型号根直接写 `型号配置.toml`（`model_id_service.py:60-64`），未接门闩也未接守卫；它由工作台 `_load_model_ids` / `ensure_model_id` 自动触发（`scheme_workbench_model.py:251,275`），且 scan_meta 兜底恢复路径（`workbench_window.py:463-469`）也会走到。该自动写入须在正式 CRUD 前接入 #1/#2，或改为受控的显式迁移动作。

---

## 未关闭 gate

### R3（P1·阻断）：`assets` 以 `path` 为主键且缺少 CRUD 定点写接口  `complexity: high`

**文件：** `src/fwasset/core/asset_index.py:75-98`（schema v3）、`:184-228`（`save_assets`）、`:308-323`（`delete_missing_assets`）

当前公开函数列表（`705fe60` 实测；另有公开常量/类型 `AssetIndexError`、`SCHEMA_VERSION`、`HiddenItemType`）：

```text
active_workspace_root  connect_asset_index  count_assets  default_index_path
delete_missing_assets  hide_item  init_asset_index  load_assets  load_hidden_items
load_scan_meta  prune_missing_hidden_items  query_assets  save_assets  schema_version
unhide_item
```

`delete_missing_assets(existing_paths)` 是全库对账式删除（keep 集合之外全删），不能替代 CRUD 所需的定点写；`save_assets` 仍是 `DELETE FROM assets` + `executemany` 的全量冷路径。`upsert_asset` / `replace_asset` / `delete_asset` / `bulk_reindex_subtree` 均不存在。

后果：

1. **重命名/更新/删除缺少可直接复用的 CRUD 表达**。原型中的「更新程序」（换文件夹）与「重命名」会连带改变多个从路径推导的字段，需要「删旧行 + 插入重扫生成的完整新行 + 同步 `hidden_items`」在同一 SQLite 事务内完成。
2. **`hidden_items` 以 `path` 为键**，路径变化会让隐藏状态静默失效（`prune_missing_hidden_items` 当作悬空项删掉）。
3. **没有文件系统动作与索引提交之间的一致性编排**。SQLite 事务包不住文件系统操作；必须显式实现「文件成功 → 提交索引事务；任一步失败 → 按磁盘真相重扫受影响子树」的恢复策略。

#### 建议方案（供 TASK 立项时定夺）

**不引入 UUID 型 asset ID**（真相源是目录树 + TOML，UUID 必须落盘才能跨扫描存活，成本高于收益）。保留 `path` 主键，补齐行级写 API：

| 新接口 | 语义 |
| --- | --- |
| `upsert_asset(asset)` | 新增/覆盖单行（新建、编辑后重扫单目录） |
| `replace_asset(old_path, new_asset)` | 单事务内：按 `old_path` 删旧行 → 写入**重新扫描生成的完整** `new_asset` → 同步 `hidden_items` 旧路径。不是只 UPDATE path |
| `delete_asset(path)` | 删单行 + 关联 hidden |
| `bulk_reindex_subtree(workspace_root, subtree_root, assets)` | 子树重扫后替换该子树的行；必须同时保留「工作区根」和「遍历子树」两个参数，路径归属用 `Path.relative_to()` 判断，不能用裸 `startswith` |

**⚠️ 路径变化时不能只更新 `path`**（2026-07-28 实测，见 git 历史）：同模块重命名会变 `path`/`directory_name`/`version`/`label`；跨归属移动会变 `category`/`platform`/`scheme_name`/`scheme_path`/`model_directory_path`。正确流程四步：① 动真实目录 → ② **保留工作区上下文的局部扫描**生成完整新 `FirmwareAsset` → ③ 事务内删旧行 + 插完整新行 → ④ 同事务同步 `hidden_items`。第 2 步必须复用扫描器推导，不得在 CRUD 里手写字段映射。

**扫描器现状（`705fe60`）**：入口已扩为 `scan_firmware_assets(root, catalog_path=None, last_scan_at=None, cancel_event=None)`（`file_scan.py:172-177`）——新增了扫描器级的增量跳过（`last_scan_at`，仅扫描器内跳过旧目录，`scan_service` 目前并未传该参数、结果仍整库覆盖）与取消（`cancel_event`）支持，但 `root` 仍是唯一遍历起点兼工作区根，**仍无保留上下文的局部子树扫描入口**。R3 实现时应新增 `scan_firmware_subtree(workspace_root, subtree_root)` 类入口，或先全根扫描再筛选受影响子树；不能直接 `scan_firmware_assets(new_variant_dir)` 写库。

**一致性策略**：先动文件、再动库、失败则重扫子树（文件系统不可回滚，库可从磁盘重建）。配套 `reconcile_subtree(path)` 冷接口兜底。v3 schema 无需迁移即可承载上述全部接口（schema 升级仅在有扫描不可推导的持久化字段需求时按需触发）。

### R8（P1·阻断）：文件操作会使 TOML 引用失效，但无级联校验  `complexity: high`

**文件：** `core/model_config.py:52-66`（`SharedModuleRef`）、`core/shared_module_resolver.py:118-209`、`core/platform_config.py`

两类 TOML 引用会被文件操作打断，现状没有写前反查：

1. **`平台配置.toml` 的 `[platform.defaults]`**：`module_dir → variant_name`。删除/重命名/更新一个通用变体目录会让平台默认指向不存在的变体，依赖回源的定制方案该模块变空。
2. **`型号配置.toml` 的 `shared_modules`**：`source_relative_path` 指向另一型号的具体路径。移动/删除/更新源型号目录会让引用方解析成 `missing`。解析器会优雅降级（`status="missing"` + `reason`），但用户在源型号侧操作时得不到任何警告。

当前 `SharedModuleRef.mode` 只有 `static` / `follow_default`（后者经显式或自动检测的 `source_platform` 跟随源型号的平台默认，`shared_module_resolver.py:181-209`）。**原型要求的 `follow_asset`（跟随指定程序）尚不存在**——正式落地需给来源程序一个跨重命名/更新的稳定标识并迁移语义（原型任务已标注此点），这会直接影响 R8 反查的实现方式。

**建议**（CRUD 前置）：

- 新增 `find_references_to(path, workspace_root) -> list[Reference]`：反查平台默认 + 跨型号共享（借用）引用。区分 static 引用的具体变体路径与 follow 类引用的模块/来源语义，正确处理祖先/后代路径关系。
- **删除**前调用：命中则二次确认，列出受影响的型号与模块（原型规则：有借用时必须勾选确认）。
- **重命名/更新**前调用：命中时级联改写平台默认变体名与引用路径，或阻止操作；不能只警告后留断链。TOML 写入失败时按磁盘真相对账并报告未完成项。
- **原型扩面带来的新级联场景**（正式 TASK 定稿）：删除型号/方案 = 级联删除其下全部程序（逐个走反查）；「更新程序」改类型时原类型默认失效、借用来源失效的提示与迁移；新建型号 = 新建目录 + `型号配置.toml`（写入口同样接入门闩 + 守卫）。
- 「复制为本型号私有」不在当前范围；`clear_shared_module()`（`shared_module_service.py:339-350`）已存在且幂等，将来可直接复用。

---

## 原型与当前 core 的差异清单（正式 TASK 立项前逐项定稿）

原型交互已人工验证，但以下各点在 core 层尚无对应实现，立项时必须写死：

| # | 差异点 | 现状 | 待定稿 |
| --- | --- | --- | --- |
| 1 | 借用 `follow_asset`（跟随指定程序） | `SharedModuleRef` 只有 `static`/`follow_default` | 来源程序的稳定标识与持久化方式；`follow_default` 存量数据的迁移 |
| 2 | 机芯类型枚举（`单3D`/`单2D`/`双2D`/`上3D下2D`） | `platform` 是方案/平台 TOML 里的自由文本块 | 枚举与 `[[platform]]` 块的映射；多个平台块并存时默认写哪一块 |
| 3 | 归属厂商名单（设置内可添加） | 生产源码无 vendor 配置或资产字段（`types.py`/schema 均无；原型 HTML 已有 `VENDORS` 演示逻辑） | 名单存放位置（`config.toml` 或独立 TOML）；程序资产上厂商字段的落盘与派生 |
| 4 | 新建/删除型号、新建/删除方案 | 只有扫描发现；无型号/方案的创建、重命名、删除服务。`型号配置.toml` 可由 `ensure_model_ids()` 自动创建（见 R1/R10 覆盖缺口），型号目录本身仍由外部产生 | 目录与 TOML 的创建/删除事务语义；删除型号的级联范围 |
| 5 | 更新程序 → `旧版本/` 备用副本 | 无此概念 | `旧版本/` 的落点（型号内还是变体内）；扫描器排除确认；`usb_ops.copy_directory_to_usb` 目前整目录 `copytree`（`usb_ops.py:83-93`，无 ignore），副本目录若在变体内会被拷进 U 盘 |
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

## 前置条件清单（Conditional Go 的「Condition」）

在当前范围 CRUD 开放写操作前必须完成下列项。任何真实目录写入先满足 #2；涉及删除或改变被引用路径的操作再叠加 #4：

| # | 前置项 | 对应 Issue | 复杂度 | 状态 |
| --- | --- | --- | --- | --- |
| 1 | 配置根作为写操作权威 + scan_meta 一致性校验 + 未配置时禁用写入口 | R1、R10 | medium | ✅ 已完成（TASK-20260806-r1-r10-write-gate）；⚠️ 覆盖缺口：`ensure_model_ids` 自动写入未接入，须补 |
| 2 | 统一路径守卫 `assert_within_workspace` | R5 | medium | ✅ 已完成（TASK-20260803-r5-path-guard，Windows 实机验证通过）；⚠️ 同上覆盖缺口 |
| 3 | CRUD 定点写 API + 保留工作区上下文的局部扫描/子树对账 + SQLite 事务 + 文件/索引失败恢复策略（不含 schema 迁移；SQLite 事务不包含文件系统动作） | R3 | high | ✅ 已完成（TASK-20260901-r3-index-write-api：4 行级写 API + `scan_firmware_subtree` + `asset_reconcile.reconcile_subtree`；Windows 全量 477 passed / 95.18%；经 codex 两轮实现审查「实现合格，无阻断问题」；人工验证按无 UI 等效规则以 `scripts/verify_r3_write_api.py` 四类场景通过 + 用户确认；含 `hidden_items` A/AB 前缀缺陷修复） |
| 4 | TOML 引用反查 + 删除二次确认 + 重命名/更新时级联改写或阻止断链（含原型差异清单 #1、#4 的语义定稿） | R8 | high | ⏳ 未开始 |

**以上 4 项即本审查的完整 gate。** 未列入的一律不阻断当前范围 CRUD 立项。「原型差异清单」不单独构成 gate，但其中影响写语义的条目（#1、#4）必须并入 #3/#4 的 TASK；其余条目在对应 CRUD 子 TASK 中定稿。R1/R10 与 R5 的 `ensure_model_ids` 覆盖缺口不改变其「已关闭」判定（缺口是既有自动迁移行为，非 CRUD 入口），但正式 CRUD 开放写操作前必须收口。

**建议实施顺序**：R3（索引行级写 + 局部扫描能力，含失败恢复子树重扫）→ R8（引用反查与级联，含借用语义迁移）→ 按原型范围实现新增、更新、重命名、删除、型号/方案管理。

---

## 验证记录

### 自动化验证（2026-09-01，HEAD `705fe60`）

```text
uv run python -m pytest -m "not ui" -q
→ 394 passed, 31 deselected；coverage 88.82%（门禁 80%）
```

- 静态枚举确认 gate 现状：`asset_index` 无 `upsert_asset` / `replace_asset` / `delete_asset` / `bulk_reindex_subtree`；`file_scan.scan_firmware_assets` 已扩为 4 参但仍无局部子树扫描入口；生产源码无 vendor 配置。
- `path_guard.py` 契约逐条复核通过（空根拒绝、`..` 拒绝、normcase + 斜杠归一比较、允许等于根），测试覆盖 100%。
- 写入门闩复核：`write_gate_check` 三检查（`not_configured` / `root_changed` / `out_of_workspace`）+ UI 层扫描/烧录任务态检查；service 层既有交互式写入口均接入路径守卫（`ensure_model_ids` 缺口见上）。
- `SharedModuleRef.mode` 当前为 `static` / `follow_default`（+ 可选 `source_platform`），无 `follow_asset`。
- 原型自动化验证：`node specs\design\prototypes\firmware-crud-prototype.test.js` → 122 项断言通过（TASK-20260806 记录）。
- **codex 独立复核（2026-09-01，read-only）**：逐项判定 R3/R8 未实现、`follow_asset` 缺失、差异清单 #1/#2/#5/#6 正确；发现 `ensure_model_ids()` 自动写 `型号配置.toml` 绕过门闩与守卫（已核实并补入 R1/R10 与 gate 表），并指出 API 列表范围、`last_scan_at` 未接线、vendor 表述、`型号配置.toml` 可内部创建四处措辞偏差（均已修正）。总体判定：Conditional Go 方向成立，条件清单已补全。

### 历史实测证据（不再重复执行，详见 git 历史 @705fe60 之前的本文版本）

- v3 schema 单事务行级写能力验证；路径变化的连带字段实测（重命名 4 字段 / 跨归属移动 5 字段）；回收站删除实测（`SHFileOperationW` + `FOF_ALLOWUNDO`）；切根面板残留判定更正（R2，已结案为 UX 清理项）；版本解析放宽实测（R6e，已撤销）。

### 人工验证

- ⏳ 待用户复核本审查结论与前置条件清单。

## 相关 Commit

- `77cbbd0` feat(core,ui): R5 统一工作区路径守卫（TASK-20260803-r5-path-guard）
- `4d4d3c8` feat(core,ui): R1/R10 统一写入门闩（TASK-20260806-r1-r10-write-gate）
- 基线：`a4c6fdc` docs: 归档 PySide6 迁移总 TASK；本审查初稿：`b4250f0`
