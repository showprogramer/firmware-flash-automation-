# 代码审查：L36 扫描器及底层结构重构

- 日期：2026-06-08
- 类型：重构 / 数据库 Schema 迁移 / API 变更
- 模块：`core/types.py`, `core/asset_index.py`, `core/file_scan.py`, `core/platform_config.py`, `core/scheme_config.py`

## 问题描述
原有的扫描和索引逻辑基于扁平的 `FirmwareType`，无法处理 L36 项目中由于「通用模块」和「定制方案」分离而产生的多层级、多变体问题，也无法实现不同方案之间对通用模块的「默认回源」机制。这导致后续 UI 层无法按型号/方案展示完整的模块清单。

## 处理方案
1. **类型扩展**：在 `types.py` 中的 `FirmwareAsset` 增加了四个字段：`category` (common/custom), `platform` (所属平台), `scheme_name` (定制方案名称), `scheme_path` (定制方案路径)。
2. **配置读取**：新增 `platform_config.py` 解析 `平台配置.toml`，新增 `scheme_config.py` 扫描定制目录及解析 `方案配置.toml`。
3. **扫描器升级**：在 `file_scan.py` 的 `scan_firmware_assets` 中，扫描前加载配置，并在扫描时根据相对路径第一段动态推断 assets 的 category 和 scheme，同时完全向后兼容旧目录。
4. **数据库迁移**：`asset_index.py` 的 Schema 升级到 v3，新增上述 4 列并建立对应索引。在 `init_asset_index` 中实现从 v1/v2 到 v3 的非破坏性 SQL 升级。

## 验证记录
- `uv run python -m pytest -q --no-cov -m "not ui"`：核心数据模型和索引相关测试全部通过（补充了 `test_platform_config.py` 及针对新字段的 schema 迁移断言）。
- 向后兼容性验证：`query_assets` 和 `file_scan` 对缺少 TOML 配置或旧目录结构的资产静默将新字段留空，测试未发生 regression。

## 状态
- [x] 已验证通过
- [x] 准备合入（等待 UI 重写同步提交）

## 关联 Commit
- `feat(core): add scheme inference and v3 schema for L36 structure`
