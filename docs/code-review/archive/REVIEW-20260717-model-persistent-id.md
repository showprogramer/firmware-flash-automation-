# REVIEW-20260717: 型号持久 id（Phase B0）

| 项 | 内容 |
| --- | --- |
| 类型 | 核心配置 / 新服务 |
| 模块 | `core/model_config.py`、`core/services/model_id_service.py`、`scheme_workbench_model` |
| 状态 | ✅ 人验通过，已提交 |
| 相关 TASK | `specs/archive/TASK-20260717-model-persistent-id.md` |

## 问题描述

型号仅有目录现推展示名，无稳定主键，无法支撑 Phase B `source_model_id`、改名校验与源缺失分支。

## 处理方案

1. `型号配置.toml` 仅写 `model_id`；save 行级合并保留未知键（B1 `shared_modules` 保命）。
2. `ensure_model_ids` 两遍：先读全量 occupied，再 slug + 碰撞后缀写入。
3. 工作台 bind 后映射 + 三 API；UI 选型键不变。

## 验证记录

自动化:

```text
uv run python -m pytest src/fwasset/tests/test_model_config.py src/fwasset/tests/test_model_id_service.py src/fwasset/tests/test_scheme_workbench_model.py ... -q --no-cov
→ 相关套件通过

uv run python -m pytest -m "not ui" -q
→ 305 passed, 52 deselected；coverage 85.25%
```

人工验证：用户确认通过（损坏 / 改名 / 首次生成）。

## 相关 Commit

`1c287b8` feat(core): 型号持久 id（Phase B0）
