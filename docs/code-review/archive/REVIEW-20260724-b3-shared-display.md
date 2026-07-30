# REVIEW-20260724：B3 共享模块展示与烧录候选

| 项 | 内容 |
| --- | --- |
| 类型 | Phase B3 Qt UI / 共享候选收敛 |
| 模块 | `ui_common/view_models/scheme_workbench_model.py`、`ui_qt/data_grid.py`、`ui_qt/workbench_window.py` |
| 状态 | 🟡 实现与自动化完成，待归档；Qt 人工验证已通过（2026-07-24） |
| 相关 TASK | `specs/archive/TASK-20260724-b3-shared-display.md` |

## 处理内容

- 现有模块行增加 `local / shared_hit / shared_missing` 内部状态，不创建独立共享列表。
- 有效共享行显示“共享自 …”，双击打开解析后的来源目录，操作面板使用来源资产。
- 共享来源缺失时显示“共享来源缺失”，不打开、不烧录、不回落本地副本。
- 方案回源不读取共享展示状态，保持 B4 隔离。

## 验证记录

```text
.\scripts\test.ps1
→ 353 passed, 1 warning；coverage 93.36%

Qt smoke + B3 tests
→ 20 passed, 1 warning

B3 + scheme model tests
→ 56 passed
```

人工验证：用户于 2026-07-24 使用 Qt 测试副本验证通过：有效共享、目标型号本地副本覆盖、来源缺失不回落、方案隔离。

## 相关文件

- `specs/archive/TASK-20260724-b3-shared-display.md`
- `specs/archive/TASK-20260714-config-takeover.md`
- `docs/CHANGELOG.md`