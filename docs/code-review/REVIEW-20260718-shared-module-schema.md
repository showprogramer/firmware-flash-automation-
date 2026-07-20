# REVIEW-20260718: 共享引用 schema + 解析器（Phase B1）

| 项 | 内容 |
| --- | --- |
| 类型 | 核心配置扩展 / 新解析器 |
| 模块 | `model_config`、`shared_module_resolver`、`scheme_workbench_model` |
| 状态 | ✅ 二轮独立审查完成；2 个真 bug 已修，其余记录可接受 |
| 相关 TASK | `specs/active/TASK-20260718-shared-module-schema.md` |
| 审查日期 | 首轮 2026-07-17；二轮独立审查 2026-07-20 |

## 问题描述

跨型号共用需稳定引用落盘与命中/缺失解析；不得与方案回源混用，不得污染 `平台配置.toml`。

## 处理方案

1. `SharedModuleRef` 五字段数据类（无 `mode`），`型号配置.toml` `[shared_modules.*]` 读写。
2. 统一 `_merge_write_model_config` helper（`tomli-w` 序列化 + `atomic_write_text`）；`save_model_id` 从行级替换一并迁移。
3. `resolve_shared_module` 一套路径覆盖命中/缺失四因（`source_not_imported` / `path_not_found` / `id_mismatch` / `out_of_workspace`）。
4. view model 最小 API（`get_shared_modules` / `resolve_shared_module`）；**不**改 `get_scheme_modules`（B4 隔离）。

## 自动化门禁

```text
# 首轮
uv run python -m pytest -m "not ui" -q → 331 passed；coverage 86.10%

# 二轮修复后（+3 回归测试 R1/R2）
uv run python -m pytest -m "not ui" -q → 334 passed, 52 deselected；coverage 86.17%
uv run python -m pytest src/fwasset/tests/test_model_config.py src/fwasset/tests/test_shared_module_config.py src/fwasset/tests/test_shared_module_resolver.py src/fwasset/tests/test_scheme_workbench_model.py -q --no-cov → 88 passed
```

B0 回归：`test_model_config.py` 全部通过（含 `test_save_preserves_shared_modules_section`、`test_save_replace_failure_keeps_bytes`、`test_chinese_model_root`）。

## 审查议题

### Issue 1（建议·低）：`_SHARED_FIELDS` 元组与 `SharedModuleRef` 字段隐式耦合

**文件：** `core/model_config.py:43-48`

`_SHARED_FIELDS` 硬编码四个字段名用于 `load_shared_modules` 的缺失检测。若将来给 `SharedModuleRef` 加字段但忘记更新 `_SHARED_FIELDS`，新字段不会被验证（静默接受空值）。

**建议：** 可改为从 dataclass fields 派生（`tuple(f.name for f in fields(SharedModuleRef) if f.name != 'module_key')`），或至少加注释标注同步要求。当前 B 期字段稳定，不阻塞。

**状态：** 关闭（可接受，B2/B3 扩展时再处理）

### Issue 2（建议·低）：`source_group` 字段存储但未被解析器使用

**文件：** `core/shared_module_resolver.py`

`SharedModuleRef.source_group` 持久化到 TOML 但 `resolve_shared_module` 不读取该字段。它是 Phase B 的分组元数据预留（如 `"l36-single"`），当前为死数据。

**状态：** 关闭（设计预留，Phase C 或 B2 UI 分组展示时启用）

### Issue 3（建议·低）：`shared_module_resolver` 私有导入 `_is_excluded_dir`

**文件：** `core/shared_module_resolver.py:10`

从 `scheme_config` 导入 `_is_excluded_dir`（下划线前缀 = 模块私有）。TASK 规范明确要求「沿用 `scheme_config._is_excluded_dir`」，因此导入本身合规。若将来 `scheme_config` 重构该函数，此处会受影响。

**建议：** 可考虑将 `_is_excluded_dir` 提升为公共 API 或移到共享工具模块。当前不阻塞。

**状态：** 关闭

### Issue 4（建议·低）：`_serialize_model_config` 行为细节

**文件：** `core/model_config.py:153-158`

```python
def _serialize_model_config(data: dict[str, Any]) -> str:
    body = tomli_w.dumps(data)
    if body and not body.endswith("\n"):
        body += "\n"
    return MODEL_CONFIG_HEADER + "\n" + body if body else MODEL_CONFIG_HEADER
```

`tomli_w.dumps({})` 返回 `""` → 走 `else` 分支 → 只返回 header（header 自身有尾换行）。`tomli_w.dumps({"model_id": "x"})` 返回 `"model_id = \"x\"\n"` → 走拼接 → header + `\n` + body = header 后有空行分隔。这是**有意设计**（空 dict 写回只保留 header；有数据时 header 与内容间有空行）。现有测试 `test_header_comment_rewritten` 只验证头注释存在，不校验精确换行数。

**状态：** 关闭（行为正确）

### Issue 5（P1·已修）：`..` 路径绕过源型号 id 校验

**文件：** `core/shared_module_resolver.py:62-68, 103-108`
**Commit：** `3d18f04`

`source_relative_path` 含 `../` 可跳到其它型号根，若只校验首段目录的 `model_id` 会误 hit。

**修复：** 双重防线——
1. 预检拒绝路径段中的 `..`（L64-68）
2. resolve 后再次校验 `abs_path` 仍位于 `source_dir`（L105-108）

回归测试 `test_dotdot_cannot_bypass_source_model_id_check` 覆盖：`L36/../L50/...` + `sid="l36"` → `out_of_workspace`；直接指 `L50` + `sid="l50"` → `hit`。

**状态：** 关闭（已修并验证）

## 二轮独立审查（2026-07-20，high effort，8 角度）

不信任首轮草稿结论，对 `298ea07..HEAD` 重跑一次独立审查，发现 6 项（首轮漏了其中 2 个真 bug）。无 P0 阻塞。

| # | 严重度 | 文件 | 摘要 | 处置 |
| --- | --- | --- | --- | --- |
| R1 | 正确性·中 | `model_config.py:remove_shared_module` | 对无 `型号配置.toml` 的根 remove，会凭空建仅含头注释的空文件（无 `model_id`），后续 `ensure_model_ids` 会当 no_id 重新 slug | **已修**：文件缺失短路返回，不写盘；测试 `test_remove_on_missing_file_is_noop` |
| R2 | 正确性·中 | `shared_module_resolver.py:97` | id 校验在盘上 `model_id` 已相符后，又与 bind 内存映射交叉比对；映射滞后或大小写/规范化异路径 → 误判 `id_mismatch` | **已修**：删除映射交叉校验，以 `source_dir` 盘上 id 为权威；`..` 越界由前置段校验 + source_dir 归属双保险覆盖；测试 `test_stale_id_map_does_not_force_mismatch` / `test_resolver_without_id_map` |
| R3 | 简化 | `scheme_workbench_model.py:_model_root_path_for_name` | 单型号根分支 `name == self.root_dir.name` 重复判定，第二段 `if` 恒不可达（死码） | **已修**：三条件合并为一，删死码 |
| R4 | 正确性·低 | `model_config.py:174` | 注释称 `_load_raw_dict` 可返回 `no_id`，实际从不返回（no_id 仅在 `load_model_config` 派生） | **已修**：更正注释 |
| R5 | 正确性·低 | `shared_module_resolver.py:_list_variant_dirs` | 若 `source_relative_path` 指向文件而非目录，`variants` 会把该文件当变体返回 | **记录·可接受**：契约要求指向目录；B3 UI 落地时若需严格拒绝再补校验 |
| R6 | 正确性·低 | `model_config.py:save_shared_module` | `source_module` 保存/读取的规范化回退分支不完全对称；手写 toml 的非规范 `source_module` 往返可能与 `save()` 结果不同 | **记录·可接受**：`module_key` 已有测试；`source_module` 当前仅元数据，不参与解析 |

R5/R6 为低风险边界项，留待 B2/B3 扩展时处理；R1–R4 已在本轮修复并过门禁。

## 契约合规检查

| 契约项 | 结果 |
| --- | --- |
| 落盘文件 = `型号配置.toml`，不碰 `平台配置.toml` | ✅ |
| 保存共享保留 `model_id`；保存 `model_id` 保留 `shared_modules` | ✅ 测试 `test_preserves_model_id` / `test_save_model_id_and_shared_roundtrip` |
| 无 `mode` / `follow_default` / `pinned` 字段 | ✅ |
| `source_relative_path` 相对工作区根 | ✅ |
| 路径首段 id 校验 | ✅ `load_model_config(source_dir)` |
| 防 `..` 越界 | ✅ 双重防线（`3d18f04`） |
| 不跨型号搜同名 | ✅ `test_no_cross_model_search` |
| 不回落本地副本 | ✅ 缺失时直接返回 missing |
| B4 隔离：`get_scheme_modules` 不含共享行 | ✅ `test_scheme_modules_ignore_shared_refs` |
| 共享引用只存 toml 不进 SQLite | ✅ 未改 `asset_index.py` / `types.py` |
| `tomli-w` 无条件依赖 | ✅ `pyproject.toml` |
| `atomic_write_text` 失败无半成品 | ✅ `test_atomic_replace_failure` |
| 未知 table 保留 | ✅ `test_unknown_table_preserved` |
| 文件头注释固定重打 | ✅ `test_header_comment_rewritten` |
| 缺字段条目跳过 | ✅ `test_skip_incomplete_entry` |
| `canonical_module_dir` 键规范化 | ✅ `test_canonical_module_key_on_save` |

## 相关 Commit

| 哈希 | 描述 |
| --- | --- |
| `4c8b6db` | feat(core): 共享引用 schema + 解析器（Phase B1） |
| `0d10630` | docs(code-review): 补写 TASK-20260718 相关 commit 哈希 |
| `3d18f04` | fix(core): 拒绝共享路径中的 .. 绕过源型号 id 校验 |
