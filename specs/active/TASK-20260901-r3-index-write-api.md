# TASK-20260901-r3-index-write-api：索引行级写 API + 保留上下文的子树扫描

## 状态

| 项 | 状态 |
| --- | --- |
| 类型 | core 索引层 + 扫描器公共能力（公共 API） |
| 当前状态 | ✅ 人工验证通过，记录已更新 |
| 前置 | REVIEW-20260728 前置条件清单 **#3**（R3，P1·阻断） |
| 父任务 | CRUD 前置（REVIEW-20260728-pre-crud-readiness） |
| 分支 | `feature/pyside6-migration` |
| 完成 commit | `7a00879` |
| 复杂度 | `high`（见下） |

**复杂度理由：** 触碰 `asset_index`（扫描索引真源缓存）、`file_scan`（扫描器）与 `path_guard`（路径守卫）三条公共路径，新增公开 API 属索引契约改动，需跨平台回归（Windows 路径归一）与 Windows 实机人验；但不涉及 schema 迁移、UI 与 TOML 写，故不到 `xhigh`。

---

## 目标

实现 REVIEW-20260728 前置条件清单 **#3**（R3）：为后续 CRUD 动作任务（新增/更新/重命名/删除程序、型号/方案管理）提供索引层地基——

1. `asset_index` 补齐**行级定点写 API**（现只有全量替换 `save_assets()` 和对账式 `delete_missing_assets()`）；
2. 扫描器新增**保留工作区上下文的局部子树扫描入口**（现 `root` 既是遍历起点兼工作区根，无子树能力）；
3. 定义并实现「文件先行、库可重建」的**失败恢复策略**（子树重扫 + 冷对账兜底）。

## 关键决策

- **不引入 UUID 型 asset ID**（真相源是目录树 + TOML，UUID 必须落盘才能跨扫描存活，成本高于收益）。保留 `path` 主键。
- **行级写接口**：`asset_index.py` 承载四个写接口，对账接口独立成 `core/asset_reconcile.py`（签名均含既有约定的数据库 `path` 与写入时间参数，`*` 后强制关键字传参）：

  ```python
  upsert_asset(asset, *, path=None, scanned_at=None) -> None
  replace_asset(old_asset_path, new_asset, *, path=None, scanned_at=None) -> None
  delete_asset(asset_path, *, path=None) -> bool          # 删不存在行返回 False（幂等）
  bulk_reindex_subtree(workspace_root, subtree_root, assets, *, path=None, scanned_at=None) -> None
  reconcile_subtree(workspace_root, subtree_root, *, catalog_path=None, path=None, cancel_event=None) -> None
  ```

  - `scanned_at` 缺省取「当前时间」（与 `save_assets` 现行为一致）。
- **语义约束（全部写接口）**：
  - **单工作区一致性**：`bulk_reindex_subtree` / `reconcile_subtree` 必须把规范化（`path_guard` 同款归一）后的 `workspace_root` 与库内 `active_workspace_root(path)` 比较；无扫描元数据或根不一致 → 抛 `AssetIndexError` 且**不改库**（防止用工作区 B 的参数改工作区 A 的数据库）。
  - **单行语义**：`replace_asset` 旧行不存在、或新 `path` 已被另一行占用 → 抛 `AssetIndexError`；不做无条件 upsert 覆盖第三方行。`upsert_asset` 允许覆盖同 `path` 行。
  - **整批原子校验**：`bulk_reindex_subtree` 写入前一次性校验每个 `asset["path"]` 都位于 `subtree_root` 之下、路径无重复、必需字段齐全；任一失败整批拒绝，不改库。
  - **入参运行时校验**：新行级 API 共用校验 helper——`FirmwareAsset` 全键存在、`path` 非空且为绝对路径；允许语义上合法的空值（不要求所有字段非空，因 `_asset_to_row` 现在会把缺失字段静默填空值，必须在入口拦住）。
  - **scan_meta 不受影响**：行级写 / bulk / reconcile 只更新资产行的 `scanned_at`，不得改变 `scan_meta.root_dir` 或全量扫描时间戳——否则未来增量扫描会把未扫描的其他子树误判为已检查。
- **路径变化时不能只更新 `path`**（2026-07-28 实测教训）：同模块重命名会变 `path`/`directory_name`/`version`/`label`；跨归属移动会变 `category`/`platform`/`scheme_name`/`scheme_path`/`model_directory_path`。`replace_asset` 的调用方必须传入完整重扫结果，实现按整行替换处理。
- **`hidden_items` 同步语义（逐类定义，禁止裸 `startswith` 前缀判断——现清理逻辑会把 `...\A` 与 `...\AB` 混淆，`asset_index.py` 既有代码需一并修正为路径边界判断）**：
  - `replace_asset`：只迁移与旧资产 `path` **精确匹配**的 `hide_type="asset"` 行到新路径；
  - `delete_asset`：删除该资产的 `hide_type="asset"` 隐藏行；`model_directory` 隐藏行在该型号目录下已无任何资产时清理；`firmware_type` 隐藏行在该类型路径边界内已无同类资产时清理；
  - `bulk_reindex_subtree` / `reconcile_subtree`：按上述同一规则处理与该子树有路径边界关联的隐藏项；子树外的隐藏项一律保留，不做全局陈旧清理；
  - 路径边界判断复用 `path_guard` 的规范化语义（resolve + normcase + 边界比较），不新写第二套前缀匹配。
- **归属判定分工（沿用 REVIEW R3 的 `Path.relative_to()` 要求）**：`assert_within_workspace()`（`path_guard`）负责入参守卫与拿到 resolved 路径；resolved 路径上的**子树归属判定用 `Path.relative_to()`**（失败即越界），业务代码禁止直接做字符串前缀判断。不维护第二套实现。
- **子树扫描入口**：新增 `scan_firmware_subtree(workspace_root, subtree_root, catalog_path=None, cancel_event=None)`（`file_scan.py`）。**只遍历 `subtree_root`**（`os.walk` 起点即子树根，不进入兄弟目录），归属推导（`category`/`platform`/`scheme_name`/`scheme_path`/`model_directory_path`）按 `workspace_root` 计算——**必须复用 `scan_firmware_assets` 的既有推导逻辑，不得在 CRUD 里手写字段映射**。排除规则沿用 `file_scan._is_excluded_dir`（关键词含「旧」，覆盖 `旧版本/`）。`subtree_root` 不在 `workspace_root` 之下 → 报错。
- **对账的扫描结果策略（防误删）**：`reconcile_subtree` 内部先扫描后写库——
  - 扫描返回 `errors` 非空或被取消 → **禁止写库**，抛 `AssetIndexError`（「不完整扫描」不得当作权威快照，否则会删掉未扫到的索引行）；
  - `subtree_root` 已不存在（工作区内被删除的子树）→ 视为空快照，允许清空其旧索引行（支撑删除恢复）；
  - `workspace_root` 不存在、或 `subtree_root` 存在但不是目录 → 报错不改库。
- **一致性策略**：先动文件、再动库、失败则重扫子树（文件系统不可回滚，库可从磁盘重建）。`reconcile_subtree` 是冷接口兜底。
- **事务边界**：SQLite 事务不包含文件系统动作；主行写与 `hidden_items` 同步在同一事务内，中途失败整体回滚。底层 `sqlite3.DatabaseError` 链式转换（`raise ... from`）为 `AssetIndexError`。
- **schema v3 不迁移**：现 schema 可承载上述全部接口。schema 升级仅在有「扫描不可推导的持久化字段」需求时按需另立 TASK。
- **失败恢复策略**：行级 API 抛 `AssetIndexError` 由上层 CRUD 动作任务决定提示；`reconcile_subtree` 用于失败后恢复。R3 本身不引入重试编排。

## 文件变更

### Task 1：`asset_index` 行级写 API  `complexity: high`

**复杂度理由：** 扫描索引公共路径的公开 API + 事务/幂等语义 + 跨平台路径归一回归。

**Files:** `src/fwasset/core/asset_index.py`、`src/fwasset/core/path_guard.py`（如需新增无异常的 containment helper）、`src/fwasset/tests/test_asset_index*.py`、`src/fwasset/tests/test_path_guard.py`

- 按上文签名实现 4 个写接口（`reconcile_subtree` 归 Task 3 的 `asset_reconcile.py`，不在本 Task 范围）。
- 归属与边界判定统一走 `path_guard`：先 `assert_within_workspace()` 校验并取 resolved 路径，再做子树归属判断；不维护第二套 `startswith` 判断。
- 单测覆盖：
  - 新增/覆盖/删除（含幂等）/子树替换；`hidden_items` 三类同步语义（精确匹配迁移、A/AB 边界、子树外隐藏项保留、最后一项删除清理）；
  - 路径变化时完整字段替换（重命名导致 `directory_name`/`version`/`label` 变化的用例；断言不是只 UPDATE `path`）；
  - 事务回滚注入：`replace_asset` 在「DELETE 已执行、INSERT 前失败」、`bulk` 在「子树行已删、新行未写完」时断言旧行与旧 hidden 完整保留；
  - 单工作区一致性：错误库根 / 空 `scan_meta` 拒绝，断言 assets、hidden_items、scan_meta 均未变化；
  - 入参校验：缺键、空路径、相对路径拒绝；批量路径越界/重复整批拒绝；
  - `load_scan_meta()` 前后不变的断言；
  - 归属判定：等于根、兄弟前缀（`A` vs `AB`）、`..`、混合分隔符、Windows 大小写。

### Task 2：扫描器子树入口  `complexity: high`

**复杂度理由：** 扫描器公共路径改动，遍历范围与归属推导复用正确性直接影响索引真源。

**Files:** `src/fwasset/core/file_scan.py`、`src/fwasset/tests/test_file_scan*.py`

- 新增 `scan_firmware_subtree(workspace_root, subtree_root, catalog_path=None, cancel_event=None)`，行为见关键决策。
- 测试：
  - **遍历范围 spy**：`os.walk` 打桩断言起点为 `subtree_root` 且未访问兄弟目录（防止「全根扫描后过滤」的假实现通过对拍）；
  - 字段级对拍：完整树 fixture 上 `scan_firmware_subtree(root, sub)` == `scan_firmware_assets(root)` 中位于 `sub` 之下的子集（字段级相等，不只是 path 集合）；
  - 自定义 `catalog_path` 透传、`cancel_event` 取消、扫描错误返回、排除目录、`subtree_root == workspace_root` 退化情形；
  - 越界拒绝；不改变 `scan_firmware_assets` 现有行为。

### Task 3：子树对账冷接口与恢复策略  `complexity: high`

**复杂度理由：** 编排扫描器、数据库事务、路径安全与失败恢复，同属扫描索引公共路径。

**Files:** `src/fwasset/core/asset_reconcile.py`（新建，编排 `file_scan` 与 `asset_index`）、`src/fwasset/tests/test_asset_reconcile.py`

- 实现 `reconcile_subtree(workspace_root, subtree_root, *, catalog_path=None, path=None, cancel_event=None)`：先扫描（含错误/取消/删除子树分支策略）→ 事务内重建该子树行集（替换 + 删多余 + 补缺失，含 hidden）。
- 集成测试（`tmp_path` 多子树完整树）：**同时断言磁盘与库，且分层断言**——
  - 目标子树的库记录 == 子树扫描结果（字段级）；
  - **兄弟子树逐行不变**；
  - 整库 `query_assets()` == 全工作区扫描结果（字段级）；
  - 失败恢复用例：模拟行级写中途失败 → `reconcile_subtree` 恢复 → 索引与磁盘一致。

## 非目标

- 不做 R8（TOML 引用反查与级联）——后续任务。
- 不做任何 UI 写入口、service 层 CRUD 动作、TOML 写、回收站删除——由后续 CRUD 动作任务按门闩接入。
- 不接 `scan_service` 的 `last_scan_at` 增量接线（扫描器级能力已有，端到端按需另立）。
- 不收口 `ensure_model_ids` 写入缺口（方案 A 已定，另立小 TASK）。
- 不做 schema 迁移。

## 验收标准

- Task 1–3 测试全部通过（含事务回滚注入、遍历范围 spy、多子树分层对拍）；`-m "not ui"` 全量回归绿；Windows ruff + mypy 通过；Windows 全量 pytest 通过（本项目纯 Windows 开发/使用，WSL 已弃用，不再要求 WSL 验证）。
- `replace_asset` 不允许退化为仅 UPDATE `path`，也无条件覆盖第三方行（均有用例守护）。
- 扫描 errors/取消不删库；已删除子树清空旧索引；单工作区根不一致拒绝——均有用例。
- Windows 实机人工验证通过（见验证记录定义）。
- REVIEW-20260728 前置条件清单 #3 更新为已完成。
- CHANGELOG：本任务无用户入口，预期标记「不适用」；若实现中产生用户可感知变化再改记 Unreleased。

## 文档与收口

- Review：REVIEW-20260728 gate #3 已更新为 ✅ 已完成（含验证记录回填）。
- CHANGELOG：预期「不适用」（纯内部能力，无用户入口）；后续 CRUD 用户功能接入时统一记录。
- 迁移说明：不适用（无路径/配置/schema 迁移）。

---

## 验证记录

### 自动化验证（已完成）

| 平台 | 环境 | 命令 | 结果 |
| --- | --- | --- | --- |
| Windows | `.venv` | `uv run python -m pytest -q` | 通过（477 passed；覆盖率 95.18%） |
| Windows | `.venv` | `uv run python -m pytest -m "not ui" -q` | 通过（446 passed；覆盖率 89.7%） |
| Windows | `.venv` | `uv run ruff check src scripts` | 通过 |
| Windows | `.venv` | `uv run mypy` | 通过（34 文件） |

- 新增测试 46 例：`test_asset_index_write_api.py`（行级写 API：全键/绝对路径校验、整行替换、clash/缺失旧行拒绝、hidden 三类同步、A/AB 边界回归、整批校验、工作区一致性、大小写/分隔符身份归一、祖先隐藏项清理、junction/真实路径混用判活清理、SQL 触发器注入的 DELETE 后 INSERT 失败回滚 + `__cause__` 链）、`test_file_scan_subtree.py`（walk spy 限定遍历、字段级对拍、越界/缺失/非目录/取消/排除目录/自定义 catalog/onerror 错误返回）、`test_asset_reconcile.py`（多子树分层对拍：目标子树字段级 + 兄弟子树逐行不变 + 整库对拍 + scan_meta 不变；错误/取消不写库；已删子树空快照；工作区根消失拒绝；预置取消阻止空快照清空；真实 onerror 错误阻止写库）、`test_path_guard.py` 新增 helper 用例。
- 既有 `prune_missing_hidden_items` 修复为路径边界判断（原 `startswith` 会把 `...\A` 与 `...\AB` 混淆），相关既有测试全绿。
- codex 实现审查（第一轮）发现 1 P0 / 3 P1 / 2 P2 已全部修复：P0 工作区根消失被误判为已删子树（现报错不改库）+ 预置取消先于空快照写库；P1 stale 行与 hidden 边界采用词法/resolved 双重归属、单行接口按 normcase 身份匹配防大小写变体重复行、隐藏项清理扩展到子树祖先（兄弟仍保留）、hidden 判活身份贯穿（junction 场景，附 mklink /J 回归测试）；P2 补自定义 catalog 透传与 onerror 错误测试、验收标准按用户决定改为纯 Windows。第二轮终验结论：「实现合格，无阻断问题」。
- 已知平台差异：无（本项目纯 Windows 开发/使用，验证以 Windows `.venv` 为准；WSL 不再使用）。
- 提交：`7a00879`

### 人工验证（已完成）

- 平台：Windows 实机（一次性工作区 + 一次性数据库，不经 UI；CRUD UI/服务层属后续任务，本任务验证对象是 core API 本身）
- 方式：`uv run python scripts\verify_r3_write_api.py`（隔离现场 `.scenario/r3/`，按「无 UI 的人工验证等效规则」由 Agent 脚本驱动）
- 结论：
  1. **新增**：目录落盘 → `scan_firmware_subtree` → `upsert_asset`，新行字段级入库，scan_meta 不受影响；
  2. **重命名**：目录改名 → 子树重扫 → `replace_asset` 整行替换（旧行删除、新行为完整行，非仅改 path）；
  3. **删除**：`reconcile_subtree` 清空已删子树且兄弟子树逐行不变；`delete_asset` 单行删除含 asset 隐藏行、重复删除幂等返回 False；
  4. **失败恢复**：SQL 触发器注入写库失败 → 抛 `AssetIndexError` 且库不被破坏 → `reconcile_subtree` 后整库与磁盘字段级一致。
- 四类场景全部通过（脚本 exit 0），用户已确认「验证通过」。

## Task DoD

- [x] Task 1：`asset_index` 行级写 API（4 个写接口签名 + 单工作区一致性 + 入参校验 + hidden 三类同步 + 事务回滚注入测试）
- [x] Task 2：`scan_firmware_subtree` 子树扫描入口（限定遍历 spy + 字段级对拍 + 分支策略测试）
- [x] Task 3：`core/asset_reconcile.py` 对账冷接口（扫描错误/取消不删库 + 已删子树空快照）+ 多子树分层对拍集成测试
- [x] 自动化验证已记录
- [x] 人工验证已记录（脚本场景四类全通过，等效规则 + 用户确认）
- [x] Review 已更新（REVIEW-20260728 #3）
- [x] CHANGELOG 已同步 / 明确标记不适用（无用户入口，标记不适用）
