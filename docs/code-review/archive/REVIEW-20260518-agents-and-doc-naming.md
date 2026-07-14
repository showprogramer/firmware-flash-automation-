---
### 问题 1：AGENTS.md 测试路径错误且缺少编码风格规范

**类型**： 规范

**模块**： `AGENTS.md`, `pyproject.toml`, `docs/`, `specs/`

**问题描述**
- `AGENTS.md` 写 `tests/test_asset_index.py` 但实际测试在 `src/fwasset/tests/`，单测命令引用错误路径。
- `pyproject.toml` 的 `testpaths = ["tests"]` 指向不存在的顶层 `tests/` 目录，与 src layout 不匹配。
- AGENTS.md 缺少核心编码风格说明：`from __future__ import annotations`、TypedDict 契约、ServiceResult 返回规范、Panel 注册表、Design tokens、`log_fn=print` DI、`threading.Event` 取消模式等。
- 缺少 review 触发时机说明。
- 文档命名不统一：code-review 用 `YYYYMMDD-序号`、migration note 用单文件、task 无日期前缀。

**处理方案**
- 修正 `pyproject.toml` testpaths 为 `["src/fwasset/tests"]`。
- 重写 AGENTS.md（93 → 144 行），补充完整的编码风格章节、测试约定、文档命名规范表、review 触发时机。
- 统一文档命名：REVIEW/MIGRATION/TASK/ADR 四类前缀+日期。
- 移动文档到对应目录：`docs/migrations/`、`specs/active/`、`specs/decisions/`。
- 移动测试目录 `tests/` → `src/fwasset/tests/`，移动 `COMMIT_TEMPLATE.md` → `docs/`。
- 清理过时文档和重复文件。

**状态**： ✅ 已修复

**验证记录**
- 验证日期：2026-05-18
- 验证人：人工
- 验证结果：通过
- 对应版本：Unreleased

**相关 Commit**： df4e980, 07bd9d1
---