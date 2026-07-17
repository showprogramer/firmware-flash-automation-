# REVIEW-20260718: 共享引用 schema + 解析器（Phase B1）

| 项 | 内容 |
| --- | --- |
| 类型 | 核心配置扩展 / 新解析器 |
| 模块 | `model_config`、`shared_module_resolver`、`scheme_workbench_model` |
| 状态 | ✅ 数据层验收通过并提交（B1 无 UI） |
| 相关 TASK | `specs/active/TASK-20260718-shared-module-schema.md` |

## 问题描述

跨型号共用需稳定引用落盘与命中/缺失解析；不得与方案回源混用，不得污染 `平台配置.toml`。

## 处理方案

1. `[shared_modules.*]` 读写 + 统一 `_merge_write_model_config`（tomli-w）。
2. `resolve_shared_module` 一套路径、四类缺失原因。
3. view model 最小 API；不改 `get_scheme_modules`。

## 验证记录

```text
uv run python -m pytest -m "not ui" -q
→ 330 passed, 52 deselected；coverage 86.11%
```

验收：非 UI 全量 + 临时目录脚本覆盖 TASK 四场景（用户确认 B1 无 UI 可由 agent 直接验收）。

## 相关 Commit

`4c8b6db` feat(core): 共享引用 schema + 解析器（Phase B1）
