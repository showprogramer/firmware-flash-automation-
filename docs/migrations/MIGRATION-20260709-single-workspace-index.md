# Migration: 资产索引单工作区语义收口

Date: 2026-07-09  
Scope: `src/fwasset/core/asset_index.py`  
Status: Completed (behavior clarification; no SCHEMA_VERSION bump)

## Reason

`scan_meta` 以 `root_dir` 为 PK 可多行，而 `assets` 无 `root_dir` 且 `save_assets` 全表 `DELETE`，叙事上像「多根索引」，实现上是「单索引」。产品定为：**一次一个工作区（固件根）**，目录 + TOML 为真相，索引为缓存；未来 CRUD 后全量扫描仅作导入/修复。

## Old → New

| 项 | 旧 | 新 |
|----|----|-----|
| `save_assets` + `scan_meta` | `ON CONFLICT(root_dir)` 累加多行，旧根 meta 残留 | 先 `DELETE FROM scan_meta`，再插入当前根 **一行** |
| `assets` 全表 DELETE | 已有，语义未文档化 | 明确为「当前工作区快照覆盖整库」 |
| 换根扫描 | 资产被替换、meta 可能残留旧根 | 资产替换 + meta 仅当前根 |
| API | 仅 `load_scan_meta()` 列表 | 新增 `active_workspace_root()` 取当前根 |

无表结构变更，**不升** `SCHEMA_VERSION`。旧库多行 `scan_meta` 在下次全量扫描/`save_assets` 后自动收口。

## Impact

- 调用方仍可用 `load_scan_meta()[0]`；正常路径至多一行。
- 不支持「多根资产同时在库」；需要多根时需另立设计（加 `root_dir` 列），当前不做。
- CRUD / 行级写（`asset_write_service`）仍待后续 TASK。

## Verification

```bash
uv run python -m pytest src/fwasset/tests/test_asset_index.py -q --no-cov
```

## Rollback

恢复 `save_assets` 中 `ON CONFLICT` 写入、去掉 `DELETE FROM scan_meta` 即可；库文件无需迁移回滚。
