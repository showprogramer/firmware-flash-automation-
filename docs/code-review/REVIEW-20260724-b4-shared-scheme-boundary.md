# REVIEW-20260724：B4 共享 / 方案边界硬化收口

| 项 | 内容 |
| --- | --- |
| 类型 | Phase B4 / B4b / B6 ViewModel 边界硬化 |
| 模块 | `ui_common/view_models/scheme_workbench_model.py` |
| 状态 | ✅ 已修复并人验通过（2026-07-24）；待归档 |
| 相关 TASK | `specs/active/TASK-20260724-b4-shared-scheme-boundary.md` |

## Issue 1（P1·缺口）：方案回源把保留本地副本当通用行 `complexity: medium`

**复杂度理由：** 单路径改 `get_scheme_modules` 回源跳过共享键 + 一组边界回归；不动 schema / service。

**文件：** `src/fwasset/ui_common/view_models/scheme_workbench_model.py`（`get_scheme_modules`）

**问题：** 已登记 `shared_modules` 且本型号 `通用/` 仍有文件、方案无定制专属时，defaults / A4 回源仍 `_append_fallback` 本地副本，违反父任务 B4b。

**处理：** 预收集 `shared_keys`；defaults 与 A4 两处若键命中共享条目（不论 hit/missing）则跳过回源。定制专属不受影响。

**状态：** ✅ 已修复并人验通过

## 验证记录

```text
uv run python -m pytest src/fwasset/tests/test_b4_shared_scheme_boundary.py src/fwasset/tests/test_b3_shared_display.py src/fwasset/tests/test_scheme_workbench_model.py -q --no-cov
→ 61 passed

.\scripts\test.ps1
→ 358 passed, 1 warning；coverage 93.47%
```

人工验证：用户于 2026-07-24 确认场景 4 / 6 / 7 / 8 通过（含方案页不吃共享、不回落本地副本）。

## 相关文件

- `specs/active/TASK-20260724-b4-shared-scheme-boundary.md`
- `specs/active/TASK-20260714-config-takeover.md`
- `src/fwasset/tests/test_b4_shared_scheme_boundary.py`
- `docs/CHANGELOG.md`
