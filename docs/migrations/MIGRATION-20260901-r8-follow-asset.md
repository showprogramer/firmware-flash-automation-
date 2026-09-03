# MIGRATION-20260901: 借用语义迁移（follow_default → follow_asset）

> 对应 TASK-20260901-r8-reference-integrity（规则 2/3）。阅读对象：维护者与后续 CRUD 任务实现者。

## 背景

借用（共享引用）落盘在借入方 `型号配置.toml` 的 `[shared_modules]` 中。R8 之前
`SharedModuleRef.mode` 只有两个值：

| mode | 语义 | 来源 |
| --- | --- | --- |
| `static` | 固定用来源的具体程序（锚定 `source_relative_path`） | Phase B |
| `follow_default` | 跟随来源型号该模块的平台默认（可选 `source_platform`） | Phase C |

HTML 原型（TASK-20260806）定稿的产品规则是「跟随这个程序」——来源更新、改名、
换文件夹后借入方自动同步，**明确不做「跟着对方的默认走」**。因此 R8 新增
`follow_asset`，并迁移存量 `follow_default`。

## 新语义（R8 起生效）

| mode | 落盘 | 重命名/移动来源 | 更新来源程序 |
| --- | --- | --- | --- |
| `static` | 四字段锚定具体程序 | 级联改写到新路径 | **不改写**：旧程序退位后解析 `missing`（「用不了」） |
| `follow_asset` | 同 static | 级联改写到新路径 | **级联改写**到 replacement（跟随更新） |
| `follow_default` | 兼容读取，不再新登记 | —（解析按默认语义） | — |

- `follow_asset` **不引入 UUID 或额外落盘标识**：稳定身份由「操作矩阵级联 + 路径
  身份不复用约束（`path_identity_conflict`，属 CRUD 写语义 gate）」共同保证。
- 应用外（资源管理器）改动不受 R8 保证：解析按磁盘真相降级 `missing`。
- 「同路径原位换内容」不是 R8 支持的操作：正式 CRUD 的 update 一律禁止
  replacement 与旧锚点物理/词法身份等价（`invalid_operation`）。

## 迁移

- 入口：`fwasset.core.services.reference_service.migrate_follow_default_refs(configured_root, workspace_root)`。
- 时机：正式 CRUD 任务在开放写操作前调用一次；UI 不暴露入口。
- 行为：逐条解析 `follow_default` 的当前默认指向，改写为 `follow_asset`
  （锚定迁移时刻的默认程序），清空 `source_platform`。
- 失败处理：
  - 单条解析失败（missing / no_source_default / path_not_found / id_mismatch）→
    条目保持 `follow_default` 原样，计入报告，不丢数据；
  - 借入方或来源配置损坏（parse_error 等）→ 该型号整体 `failed`，不写该文件；
  - 写失败即停，**可重入**：再次运行从未迁移的文件继续，直到收敛；
    无 `follow_default` 时返回零改动（幂等）。
- 读端兼容：未迁移的 `follow_default` 条目继续按 Phase C 语义解析，不强制迁移。

## 已知限制

- `static` 在同路径原位换内容时也会看到新内容（目录树 + TOML 真源架构的固有限制）；
  严格快照由正式 CRUD 保证「更新总是换目录」实现。
- 删除程序/模块/方案/型号**零 TOML 改写**：借用条目保留、解析自然 `missing`，
  回收站撤销后自动恢复；悬空 defaults 期间依赖该默认的定制方案该模块不可用
  （读端不回退，撤销或另设默认后恢复）。

## 验证

- `uv run python -m pytest -q`（含 `test_reference_service.py` 迁移矩阵）。
- `uv run python scripts\verify_r8_reference_integrity.py`（隔离场景人工验证脚本）。
