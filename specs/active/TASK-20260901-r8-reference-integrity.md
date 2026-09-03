# TASK-20260901-r8-reference-integrity：R8 TOML 引用反查与级联完整性（借用语义迁移 + 门闩收口）  `complexity: high`

## 状态

| 项 | 状态 |
| --- | --- |
| 类型 | core 引用层 + 服务层（公共 API + TOML 写语义） |
| 当前状态 | ✅ 人工验证通过，记录已更新（codex 七轮实现审查终审「实现合格，无阻断问题」；Windows 全量 574 passed / 覆盖率 94.56%） |
| 前置 | REVIEW-20260728 前置条件清单 **#4**（R8，P1·阻断）——本任务完成 = 引用基础能力 gate 关闭；「CRUD 写语义 gate」（规则 7 + 差异清单 #4）另立且仍阻断真实写入 |
| 依赖 | ✅ TASK-20260901-r3-index-write-api；✅ R5 路径守卫；✅ R1/R10 写入门闩 |
| 分支 | `feature/pyside6-migration` |
| 完成 commit | `5e55c9f` |
| 复杂度 | `high`（见下） |

**复杂度理由：** 新增引用反查与级联改写两条公共能力，触碰 `model_config`、`shared_module_resolver`、`platform_config`、`shared_module_service`、`model_id_service`、`core/types.py`、`path_guard.py`（公开身份判定 helper，`asset_index` 内部复用不改行为）与两个 UI 调用点；借用语义迁移是行为变更；多文件 TOML 改写带 preimage CAS 回滚。不含 schema 迁移、不含「排除目录资产消费链」、不含 UI 新面板与正式 CRUD 编排，维持 `high`；若实施中被迫引入上述排除项，须另拆子 Task 并重新评估。

## 目标

让「重命名 / 移动」不产生 TOML 断链、「更新」有明确可实现的跟随语义、「删除」可确认影响且可撤销、路径身份不被静默复用、自动写 TOML 无门闩缺口：

1. **反查**：给定工作区内目标（型号/方案/模块/程序，显式 `target_kind` 且经验证），找出全部会因此失效或需要改写的 TOML 引用（static 借用、follow 类借用、平台默认），以 TOML 盘上严格读取为真源；无法完整读取时返回结构化 issue，不静默降级为零命中。
2. **跟随语义落地**：`SharedModuleRef` 新增 `follow_asset`（跟随来源程序的后续更新），与 `static`（固定该程序）有明确可观察差异；存量 `follow_default` 按定稿规则迁移。
3. **级联原语**：提供「结构化改写请求 + 改写计划 + preimage CAS 回滚应用」原语，覆盖身份延续操作（重命名/移动）与 update 的 follow/defaults 主路径改写；不可行时返回阻止理由。删除零 TOML 改写（见规则 5）。正式 CRUD 任务负责编排「文件动作 → 级联 → R3 索引写 → 对账兜底」。
4. **门闩收口**：`ensure_model_ids` 自动写 `型号配置.toml` 接入配置根与归属校验，补上 R1/R10 的已知覆盖缺口。

**Files:**
- core（新增）：`src/fwasset/core/reference_lookup.py`、`src/fwasset/core/services/reference_service.py`
- core（修改）：`src/fwasset/core/types.py`（新增 `ReferenceTargetKind` / `ReferenceOperation` / `RewriteRequest` 等类型真源）、`src/fwasset/core/model_config.py`（mode 扩展 + 严格加载入口）、`src/fwasset/core/shared_module_resolver.py`（follow_asset 分支）、`src/fwasset/core/platform_config.py`（defaults 严格读取/改写 helper）、`src/fwasset/core/path_guard.py`（新增公开 `same_path_identity`，无 DB）、`src/fwasset/core/asset_index.py`（`_find_equivalent_asset_path` 内部改为复用 `same_path_identity`，行为不变）、`src/fwasset/core/services/shared_module_service.py`（follow_asset 登记）
- UI 调用点（仅传参改造，不做新界面）：`src/fwasset/ui_common/view_models/scheme_workbench_model.py`、`src/fwasset/ui_qt/workbench_window.py`
- 测试（全部位于 `src/fwasset/tests/`）：`test_reference_lookup.py`、`test_reference_service.py`、`test_shared_module_config.py`（扩展）、`test_shared_module_resolver.py`（扩展）、`test_model_id_service.py`（如无则新建）、`test_path_guard.py`（`same_path_identity` 扩展）、R3 既有 asset_index 测试回归
- 文档：`docs/migrations/MIGRATION-20260901-r8-follow-asset.md`、`docs/code-review/REVIEW-20260728-pre-crud-readiness.md`（gate #4 收窄 + 新增 CRUD 写语义 gate）、本 Task

## 当前规则（语义定稿）

以 REVIEW-20260728「现行产品规则」与原型 Task「当前规则」为准，本任务内定稿以下各点：

### 规则 1：反查真源、命中结构与严格性

- 反查**冷读盘上 TOML**，不依赖 SQLite 索引（目录树和 TOML 是真源）。
- **型号根识别规则**：存在 `通用/`、`定制/`、`型号配置.toml`、`平台配置.toml` 任一领域标志的目录视为型号候选；工作区根自身带领域标志 → 单型号布局，否则枚举带标志的一级子目录。无任何标志的普通目录**忽略、不产生 issue**；带标志但缺 `型号配置.toml`/id 的目录产生 `missing_model_id` issue。
- 严格读取：反查与计划构建必须使用**严格加载入口**，任何 `parse_error` / `parser_missing` / shared 条目结构非法 / 型号缺 id / 重复 id 都进入 `issues`，不得当空数据处理。
- 公共入口（`core/reference_lookup.py`）：
  - `find_references_to(configured_root, workspace_root, target_path, target_kind: ReferenceTargetKind) -> ServiceResult`：target 为**现存路径**，kind 必须经领域身份验证（型号标志、`通用/定制/方案/模块/程序` 结构与 catalog/资产上下文）——错配返回 `invalid_target`、零副作用；payload 携带 `ReferenceLookupResult`。
  - `find_dangling_anchors(configured_root, workspace_root, path) -> ServiceResult`：专供「路径身份复用检查」（规则 7），**允许 path 不存在**，返回两类路径锚点：① static/follow_asset——由 `source_relative_path` 还原绝对路径；② platform_default——**候选路径驱动匹配**：从待占用候选 `path` 的结构派生 owner 型号、实际 module 路径/名称与 variant（模块叶子则 variant=`""`），再按 owner + `canonical_module_dir(候选 module 名)` + raw value 与各 `平台配置.toml` 的 defaults 逐条比较，命中时以候选路径为还原锚点；模块目录仍存在时可用实际目录交叉验证，但存在性**不是必要条件**（模块已删除、TOML 已规范化为 canonical 名而历史目录是 alias 的场景必须仍能命中）。兼容期 `follow_default` 不作为固定路径身份锚点（按默认语义处理）。同样受统一 gate 与严格加载约束，issue 仍阻止。
  - 返回锚点保留来源类别（`shared_static` / `shared_follow_asset` / `platform_default`）与 `ReferenceHit` 同款定位字段。
- 返回 `ReferenceLookupResult`（dataclass）：`hits: list[ReferenceHit]`、`issues: list[LookupIssue]`。`LookupIssue` 类别：`model_config_parse_error` / `platform_parse_error` / `parser_missing` / `invalid_shared_entry` / `missing_model_id` / `duplicate_model_id` / `canonical_conflict`（仅异值）；每条至少含配置文件路径、owner 型号根。
- `ReferenceHit` 至少含：引用方型号根、引用方 model_id、来源类别（`shared_static` / `shared_follow_default` / `shared_follow_asset` / `platform_default`）、引用方配置文件路径、shared 的 raw module_key、defaults 的 platform 块身份（name + 块序号）、raw key、canonical key、raw value、mode、当前指向。
- 命中判定用路径边界关系（`path_guard.is_same_or_under` / `contained_subpath` / `same_path_identity`），禁止裸 `startswith`：
  - **程序（asset）**：static 与 follow_asset 命中「锚定路径等于该程序或位于其后代」的引用；兼容期 `follow_default` **仅当**该条目 `resolved_path` 与目标程序物理/词法身份相同（或位于目标程序子树）时命中——默认解析到 A 时查询同模块 B 不得命中（交叉测试必备）；模块子树聚合只用于 `target_kind=module|scheme|model`。
  - **模块（module）**：命中锚定路径位于该模块子树的 static / follow_asset；全部「来源型号 + canonical 模块匹配」的 follow_default；defaults 中 canonical key 匹配的条目（跨全部 platform 块）。
  - **方案（scheme）/ 型号（model）**：按祖先聚合命中其子树内全部上述引用（方案级借用不存在，但方案子树内程序的既有引用必须命中）；型号级另命中 `source_model_id` 指向该型号的跨型号借用。型号身份用「目标型号根 + `source_relative_path` 首段归属 + model_id」**联合判定**。
- **悬空 defaults 的真实行为**（删除零改写的已知代价）：defaults 键存在但对应程序不存在时，现有读端**不回退**本地程序 → 依赖该默认的定制方案该模块**不可用**，直至撤销恢复或另设默认。反查如实列出；正式 CRUD 删除确认须展示该影响。
- 存在重复 model_id 时返回 `duplicate_model_id` issue；进入计划构建时按阻止处理。

### 规则 2：`follow_asset` 借用语义与操作矩阵

- `mode` 扩为 `"static" | "follow_default" | "follow_asset"`。落盘沿用现有四字段（`source_model_id` + `source_relative_path` 锚定来源具体程序）；**不引入 UUID 或额外落盘标识**（稳定身份由操作矩阵级联契约 + 路径身份不复用约束共同保证，见规则 7）。
- 两种模式的差异由**操作类型**决定；级联请求为结构化 `RewriteRequest`（见规则 4），**不使用裸 `new_path` 两套描述**：

  | 操作（身份判定） | static | follow_asset | 平台默认（指向该程序的条目） |
  | --- | --- | --- | --- |
  | 重命名/移动程序目录（同一程序，`new_path`） | 级联改写到新路径 | 级联改写到新路径 | 改写 value（派生规则见规则 4） |
  | 重命名模块/方案/型号（子树内程序不变身份） | 级联改写相对路径 | 同左 | 改写命中块的 key（canonical）/value |
  | **更新程序**（旧程序退位、replacement 上岗，`replacement_path` + 新旧语义快照） | **不改写**，保留旧锚点 → 旧路径移除后解析 `missing` =「用不了」（「备用副本作为可用借用来源」留 CRUD 写语义 gate，见规则 7） | **改写**到 `replacement_path` | **改写** value 指向 replacement（更新不改默认角色；retired 永不成为默认） |
  | 应用外修改（资源管理器直接改名/换内容/复用路径） | 不受 R8 保证：解析按磁盘真相降级 missing 或命中 | 同左 | 同左 |

  「同路径原位换内容」**不是 R8 支持的操作**（正式 CRUD 的 update 一律禁止 replacement 与旧锚点物理/词法身份等价 → `invalid_operation`）；上表末行列出的是应用外修改的已知限制，不构成验收分支。
- 解析端：`follow_asset` 解析 = 锚定路径存在性检查（含 workspace 守卫与 id 校验，复用 static 分支守卫链），命中时 `resolved_path` = 锚定程序目录、`variants` 不展开。`missing` 即原型「用不了」。
- 写入端：`set_shared_module` 接受 `mode="follow_asset"`；新登记不再产生 `follow_default`。
- 存量 `follow_default` 读端按既有 Phase C 语义兼容解析，直至迁移完成。

### 规则 3：`follow_default` 存量迁移

- 显式迁移入口 `migrate_follow_default_refs(configured_root, workspace_root, log_fn=print) -> ServiceResult`：
  - 先过统一 gate（规则 4）；逐条解析当前默认指向，把 ref 改写为 `follow_asset`（锚定迁移时刻的默认程序），`source_platform` 清空。
  - 严格加载：借入方/来源任一阻断级 issue → 该文件整体记 `failed`，不写该文件。
  - **按借入方配置文件聚合，一个文件只做一次 `_merge_write_model_config`**。
  - 单条解析失败（`missing` / `no_source_default` / `path_not_found` / `id_mismatch`）的条目保持原样并列入报告，不静默丢数据。
  - 跨文件失败策略：某文件写失败即停止后续文件；payload 分列 `changed` / `unchanged` / `failed`；迁移可重入（幂等收敛）。
- 无 `follow_default` 时返回零改动报告（幂等）。正式 CRUD 任务在进入写操作前调用一次；迁移说明落 `docs/migrations/MIGRATION-20260901-r8-follow-asset.md`。

### 规则 4：级联改写、统一 gate 与阻止

- **统一配置根 gate**（四个公共入口共用）：`configured_root` 为空 → `not_configured`；resolve+normcase 后 ≠ `workspace_root` → `root_changed`；通过后所有读写路径同受该配置根守卫。**apply 必须再次接收当前 `configured_root` 重验**，build/apply 之间切根 → `root_changed` 零写。
- **`RewriteRequest`**（`core/types.py` 真源，单一请求类型）：
  - rename/move：`operation="rename"`、`target_kind`、`old_path`、`new_path`。
  - update：`operation="update"`、`target_kind="asset"`、`old_path`、`replacement_path`、`old_semantics` / `new_semantics`（各含 model_id、canonical module_key、source_group、scheme_name 或 None 的语义快照）。
  - build 校验（顺序执行，任一不过即零写）：
    - **语义快照真实性**：build 从现存 `old_path` 的目录上下文、`型号配置.toml` 与 catalog 派生 authoritative old semantics，与 `request.old_semantics` 交叉校验，不一致 → `invalid_request`（防调用方两份相同但错误的快照绕过规则 7）；`new_semantics` 与 `replacement_path` 可从路径确定的 model/group/scheme 归属交叉校验，canonical module 以正式 CRUD 明确选择的类型为权威；authoritative old 与 validated new 比较，任一不同 → `unsupported_semantic_change`（改类型/改范围不在 R8，见规则 7）。
    - **身份等价与父子重叠**：update 场景对每个被命中的 static 锚点，`replacement_path` 与之 `same_path_identity` 等价、位于其下、或包含它（双向边界重叠）→ `invalid_operation`（否则旧锚点目录仍存在时 static 解析会展开子目录静默命中新程序）；rename 的 `new_path` 与 `old_path` 身份等价 → `invalid_operation`。
    - **目标 kind 验证**：对现存路径按型号领域标志与目录结构验证 `target_kind`，错配 → `invalid_target`。
- `core/services/reference_service.py` 提供：
  - `build_rewrite_plan(configured_root, workspace_root, request: RewriteRequest, log_fn=print) -> ServiceResult`：纯函数不改盘。对相关路径执行 `assert_within_workspace`。按规则 2 操作矩阵产出 `RewritePlan`；空 plan（无命中）返回 ok。
  - `RewritePlan`（dataclass）固化：resolved workspace root、`configured_root`、request、逐文件条目：**pre-operation 路径、post-operation 路径（型号自身配置随目录移动时两者不同）、原文件完整字节（preimage，absent 则记标志）、原文件 SHA-256、新文件完整字节、新文件 SHA-256**、改动清单（platform 块身份 + raw/canonical key + 新值；shared 条目 raw key + 新四字段）。
  - `apply_rewrite_plan(plan, configured_root, log_fn=print) -> ServiceResult`：先重验统一 gate、目标路径守卫与原文件 hash（不一致 → `stale_plan` 零写），再逐文件原子替换；**任一文件替换失败时对已完成文件执行 CAS 回滚**——当前文件字节必须仍等于本 plan 写入的新字节（比对 new SHA-256）才恢复 preimage，否则标 `rollback_conflict` 保留现状并输出恢复信息；原 absent 文件同样先比对再删除。payload 分列 `applied` / `rolled_back` / `rollback_conflict` / `failed`；回滚失败时 payload 给出 preimage 字节/恢复副本位置——**R3 `reconcile_subtree` 只修 SQLite 索引不修 TOML，不得声称其对账可恢复引用真源**。
- **defaults value 派生规则**（与既有默认服务派生一致）：replacement 位于模块目录叶子（唯一程序）→ value = `""`；replacement 为模块下变体目录 → value = 变体目录名；其它层级 → `invalid_operation`。rename 场景同规则（新路径叶子 → `""`，变体 → 新变体名）。
- **型号改名的配置路径移动**：型号自身 `型号配置.toml` 在文件动作后位于新根下——plan 记录 pre/post 双路径，apply 对目标型号自身配置到 **post-operation 新根**校验并写入，外部引用方仍用原路径。
- **单型号根布局**：`target_kind=model` 且目标为工作区根本身的改名/移动**不由 R8 支持**，返回 `root_rename_unsupported`。
- 改写字段矩阵：
  - 程序/方案/模块路径变化：只改 `source_relative_path`（及其首段）与命中 defaults 的 raw key/value。
  - 型号目录改名：`source_relative_path` 首段改写；`source_model_id` / `source_group` **保持不变**。
  - 模块目录别名改名：`source_module` 保持 canonical 值不变（改类型场景见规则 7）。
  - **canonical 碰撞**：同一 table 内 canonical 相同且**值/引用不同** → `canonical_conflict` 阻止、零写入；**值完全相同**（shared 比较规范化后全部字段含 mode/source_platform）→ 非阻断。**去重合并只作用于本次命中的 table/key**：命中处的同值重复可合并进计划；未命中 TOML 里的同值重复只作 warning 报告、不产生任何改动（无「顺手全库规范化」）。
- **阻止条件**：阻断级 issue；`stale_plan`；`not_configured` / `root_changed`；`invalid_request`；`invalid_operation`；`invalid_target`；`unsupported_semantic_change`；`root_rename_unsupported`；`canonical_conflict`。
- 多 platform 块：只改命中块（按块身份定位）；同名/不同名多块、同模块跨块不同默认值须有测试；一个 TOML 含多处改动时该文件只读写一次。

### 规则 5：删除语义（零 TOML 改写，可逆）

- 删除程序/模块/方案/型号时**不改写、不移除任何 TOML 引用与 defaults**：借用条目保留，删除后解析自然 `missing`（原型「用不了」）；回收站撤销后路径恢复，解析自动恢复命中。即将进入回收站的型号自身 TOML 原样保留。
- 删除前调用 `find_references_to` 取命中清单，交调用方做二次确认（原型规则：有借用时必须勾选）；确认对话框与回收站落盘属正式 CRUD 任务。
- **删除预检阻止**：命中结果含任一阻断级 issue 时删除预检失败，正式 CRUD 不得执行文件动作，返回 issue 明细供修复。
- 已知代价（规则 1）：删除默认程序后、撤销前，依赖该默认的定制方案该模块不可用（读端不回退）。
- 「解除借用」仍走既有 `clear_shared_module`（幂等），与删除动作彻底解耦。

### 规则 6：`ensure_model_ids` 门闩收口（R1/R10 缺口闭合）

- `ensure_model_ids` 增加必填 `configured_root: str | None` 参数：
  - `None`/空 → `not_configured` 结构化结果，**不写任何盘**（用户已确认「配置为空时 model_id 映射为空、相关功能降级」的形态）。
  - **先校验整批再动作，禁止校验前静默过滤**：保留原输入顺序，逐个验证非空、绝对路径、`assert_within_workspace`、存在且为目录；任一不通过（含不存在/是文件）→ 整批失败（`out_of_workspace` / `invalid_root`）、**零写盘**，payload 分列 `valid_roots` / `rejected_roots`（含原因），不给「部分成功」结果。
  - 正常分配行为（slug、占用避开）与现状一致；对既有重复 model_id 给出报告条目（不阻断扫描）。
- 调用点改造：
  - `scheme_workbench_model.SchemeWorkbenchModel.bind` 同时接收 `scanned_root` 与 `configured_root`，`_load_model_ids` / `ensure_model_id` 传 `configured_root`。
  - **仅 scan_meta 兜底恢复出的根不得当作 configured_root**（`workbench_window.py:463-469` 路径）：此时传 `None`，只读已有 id，不自动创建——「配置空 + scan_meta 有旧根仍零写盘」必须有集成测试。
  - 调用方检查 `not_configured` / `out_of_workspace` / `invalid_root` 结果，不得按成功路径继续；「配置根已切换但缓存仍是旧根」（root_changed 形态）只读不写。

### 规则 7：本任务不处理，另立「CRUD 写语义 gate」（仍阻断真实写入）

- **路径身份不复用约束**（无 asset_id 方案的必要前提）：正式 CRUD 对任何「新身份将占用某路径」的操作（新建程序到已有悬空锚点的路径、移动无关程序到该路径、更新复用旧路径），必须先调用 `find_dangling_anchors` 检查该路径上的现存/悬空锚点；有锚点 → `path_identity_conflict`，除非用户执行明确的引用迁移/解除借用。该约束与下列各项同属新 gate：
- 「更新程序」**改类型 / 改通用↔定制范围**引发的旧类型默认失效、新类型默认继承、借入方 `module_key` 迁移（R8 的 build 以 `unsupported_semantic_change` 阻止）。
- 差异清单 **#4**：新建/删除型号、方案的目录与 TOML 事务/撤销编排语义。
- 「备用副本（`旧版本/`）作为可用借用来源」的非索引消费链（涉及差异清单 #5 与 USB 复制边界）。
- REVIEW-20260728 收口时：gate #4 完成定义收窄为「R8 引用基础能力完成」，上述项组成**新的、仍阻断真实写入的「CRUD 写语义 gate」**；定稿前正式 CRUD 对这些场景按阻止语义处理。本 Task DoD 明确「R8 实现完成 ≠ 规则 7 gate 关闭」。

## 非目标

- 不做 UI（反查确认对话框、借用登记界面、术语改造）——正式 CRUD TASK。
- 不做回收站删除、新增/更新程序的落盘流程编排、`旧版本/` 备用副本的产生逻辑与消费链（差异清单 #5，见规则 7）。
- 不做「更新程序」改类型/改范围的默认与借用迁移（规则 7）。
- 不做复制/移动程序、方案级借用、多根。
- 不做差异清单 #2（机芯类型枚举）、#3（厂商名单）、#6（UI 术语）。
- 不迁移 SQLite 索引 schema；反查不读写索引库（`asset_index` 仅内部复用 `path_guard.same_path_identity`，不反向依赖）；不引入 asset_id 落盘。

## Task 分解

- **Task 1：`reference_lookup` 反查模块** —— `find_references_to` + `find_dangling_anchors`（含 platform_default 锚点还原、follow_default 不作固定锚点）+ 结果类型 + 严格加载入口 + 型号根识别规则；命中矩阵测试：三类引用 × 四种 target_kind、方案/型号祖先聚合、单/多型号根、canonical 别名（同值命中处合并/未命中处只 warning、异值阻止）、A/B 同模块交叉不命中（asset 级按 resolved 身份）、多 platform 块、重复 model_id 联合身份、损坏文件进 issues、`invalid_target` 四种 kind 错配零副作用、不存在路径的悬空锚点查询（shared 与 platform_default 两类）。
- **Task 2：`follow_asset` 语义 + 存量迁移** —— `types.py` 类型真源、`model_config` mode 扩展与严格加载、`set_shared_module` 扩参、resolver `follow_asset` 分支、`migrate_follow_default_refs`（统一 gate、按文件聚合单次写、可重入幂等、失败分类 payload）；`follow_default` 读端兼容回归；迁移说明文档。
- **Task 3：级联改写原语** —— `RewriteRequest`（authoritative 语义快照交叉校验 `invalid_request`/`unsupported_semantic_change`、身份等价与父子重叠 `invalid_operation`、`invalid_target`）、`build_rewrite_plan` / `apply_rewrite_plan` + `RewritePlan`（pre/post 双路径、preimage 字节、双 SHA-256、块身份、raw key）；操作矩阵（rename/update × static/follow_asset/defaults，defaults value 派生含唯一叶子 `""` 分支）；型号自引用配置随根移动；单型号根改名 `root_rename_unsupported`；统一 gate（apply 重验）；`stale_plan`；preimage CAS 回滚（成功 / `rollback_conflict`——首文件写后被第三方修改再失败，断言并发内容保留）；多块/同文件多处改动只写一次；无关型号同值 duplicate 不产生改动；删除零 TOML 变更 + 撤销恢复解析。
- **Task 4：`ensure_model_ids` 收口 + `path_guard.same_path_identity`** —— `configured_root` 参数 + 整批先校验（混合合法/越界/不存在/是文件输入均整批零写）+ `not_configured` 降级；`bind` 双根传参；scan_meta 兜底路径零写盘；root_changed 形态只读；正常分配行为回归；既有重复 id 报告；`same_path_identity` 公开 helper（大小写/分隔符/junction/A-AB）及 `asset_index` 复用回归。

## 验收标准

1. `find_references_to` 命中/不命中矩阵全部通过：三类引用 × {asset, module, scheme, model}、方案与型号祖先聚合、型号根识别（普通目录零 issue / 无 id 型号报 issue / 单多布局）、canonical 同值（命中处合并、未命中处零改动）与异值阻止、A/B 交叉不命中、多 platform 块精确定位、重复 model_id 联合身份、损坏配置进 `issues`、四种 kind 错配 `invalid_target`；配置文件缺失与合法零命中分别有测试。
2. 操作矩阵：重命名/移动时 static 与 follow_asset 均改写且解析命中（同时断言 TOML 精确内容与解析结果）；update 时 follow_asset 与 defaults 改写指向 replacement（唯一叶子 value=`""` 与多变体两个分支）、static 保留旧锚点且解析 missing；`replacement_path` 与 static 锚点身份等价或双向父子重叠（旧模块叶子 → replacement 子变体、replacement 为旧锚点祖先）→ `invalid_operation`；伪造 `old_semantics` 与盘上真相不符 → `invalid_request`；语义快照不一致 → `unsupported_semantic_change`；A/AB、大小写/分隔符、junction 边界回归。
3. `follow_default` 存量：读端兼容；迁移后变 `follow_asset` 且解析命中；同文件多条一次写；单条失败保留 + 报告分类；借入/来源损坏文件整文件 failed；跨文件第 N 次失败后重入收敛；二次运行零改动。
4. 级联：统一 gate（not_configured / root_changed，apply 重验）零写入；`stale_plan` 零写入；伪造/越界 plan 被守卫拦截；全部阻止码零写入；preimage CAS 回滚成功（首文件 bytes 完全恢复）与 `rollback_conflict`（并发修改内容保留 + 恢复信息）均断言；删除操作零 TOML 变更、模拟撤销后解析恢复；型号自引用经 post-operation 路径写入；`find_dangling_anchors` 命中 shared 与 platform_default 两类锚点（支撑规则 7 `path_identity_conflict`），platform_default 覆盖两支：删除变体后模块目录仍在复用变体路径前命中；删除 value=`""` 的模块叶子（模块目录已不存在、历史目录名为 alias）后复用历史路径仍按 canonical key 命中。
5. `ensure_model_ids`：未配置零写盘；配置空 + scan_meta 有旧根零写盘；配置根已切换只读；混合合法/越界/不存在/是文件输入整批零写并分列 roots；正常分配与现状一致。
6. 全量 `uv run python -m pytest -q` 绿（含既有 477 例零回归）、`uv run ruff check src scripts` + `uv run mypy` 通过；service 层公共入口显式标注 `-> ServiceResult`，code/message/payload schema 稳定、message 中文；`ReferenceTargetKind` / `ReferenceOperation` / `RewriteRequest` 定义于 `core/types.py` 单一真源。

## 验证记录

### 自动化验证（2026-09-01，实现完成）

| 平台 | 环境 | 命令 | 结果 |
| --- | --- | --- | --- |
| Windows | `.venv` | `uv run python -m pytest -q` | 通过（574 passed，含 R8 新增 126 例） |
| Windows | `.venv` | `uv run python -m pytest -q`（覆盖率） | 通过（94.56%，门禁 80%） |
| Windows | `.venv` | `uv run ruff check src scripts` | 通过 |
| Windows | `.venv` | `uv run mypy` | 通过（38 文件） |

- codex 实现审查（七轮，read-only）最终结论：「实现合格，无阻断问题」；历轮发现的 P0/P1/P2 全部修复并补回归测试（`test_r8_review_fixes.py` 31 例，含 plan token 防伪造、post-path 回滚、catalog 语义对齐 scanner、casefold 一致性等）。
- 已知平台差异：无（纯 Windows，WSL 不再使用）。
- 提交：`5e55c9f`

### 人工验证（待执行）

- 平台：Windows（按「无 UI 的人工验证等效规则」，以一次性隔离脚本驱动）。
- 方式：`uv run python scripts\verify_r8_reference_integrity.py`（隔离现场 `.scenario/r8/`，四类场景：反查 / 迁移 / 级联 / 收口）。
- 结论：四类场景全部通过（脚本 exit 0），用户已确认「验证通过」。

## 文档与收口

- Review：REVIEW-20260728 已同步——gate #4 已关闭（收窄为「引用基础能力完成」），新增仍阻断真实写入的「CRUD 写语义 gate」（规则 7 + 差异 #4）；codex 七轮实现审查终审「实现合格，无阻断问题」。
- CHANGELOG：已同步（Unreleased：follow_asset 借用语义 + 型号 id 门闩收口），非「不适用」。
- 迁移说明：已完成（`docs/migrations/MIGRATION-20260901-r8-follow-asset.md`）。

## Task DoD

- [x] Task 1：`reference_lookup` 反查模块（严格加载 + 型号根识别 + kind 验证 + 悬空锚点查询 + 命中矩阵 + issues）
- [x] Task 2：`follow_asset` 语义 + `follow_default` 存量迁移（统一 gate、按文件聚合、可重入幂等、失败分类）+ 迁移说明
- [x] Task 3：级联改写原语（RewriteRequest + 操作矩阵 + preimage CAS 回滚 + 统一 gate + 全阻止码 + 删除零改写）
- [x] Task 4：`ensure_model_ids` 门闩收口 + `path_guard.same_path_identity`（整批先校验 + scan_meta 兜底零写 + 调用点改造 + asset_index 复用回归）
- [x] 自动化验证已记录
- [x] 人工验证已记录（脚本场景四类通过 + 用户确认）
- [x] Review 已更新（REVIEW-20260728：gate #4 收窄为「引用基础能力完成」，新增仍阻断真实写入的「CRUD 写语义 gate」（规则 7 + 差异 #4）——R8 实现完成 ≠ 规则 7 gate 关闭；codex 七轮实现审查终审「实现合格，无阻断问题」）
- [x] CHANGELOG 已同步 / 明确标记不适用：已完成（Unreleased：follow_asset 借用语义 + 型号 id 门闩收口）
- [x] 迁移说明已同步 / 已完成（`docs/migrations/MIGRATION-20260901-r8-follow-asset.md`）
