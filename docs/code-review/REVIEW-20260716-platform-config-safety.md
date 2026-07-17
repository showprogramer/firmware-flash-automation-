# REVIEW-20260716: 平台配置读取与原子写盘安全

| 项 | 内容 |
| --- | --- |
| 类型 | 核心配置安全 / 服务错误码 |
| 模块 | `core/config_io.py`、`core/platform_config.py`、`core/services/platform_default_service.py` |
| 状态 | ✅ 人验通过，已提交 |
| 相关 TASK | `specs/active/TASK-20260716-platform-config-write-safety.md` |

## 问题描述

1. `load_platform_config` 对缺失/损坏/解析器不可用均返回 `[]`，写服务把 `[]` 当成「无配置」进入 bootstrap，**损坏的既有 `平台配置.toml` 会被设默认静默覆盖**。
2. `save_platform_config` 使用 `Path.write_text` 直接截断目标文件，非原子替换。

## 处理方案

1. 新增 `load_platform_config_with_status`：`ok` / `missing` / `parse_error` / `parser_missing`；结构校验（platform 须为 array of tables，defaults 须为 table）。
2. 兼容 `load_platform_config` 仍对非 `ok` 返回 `[]`（只读路径）。
3. 新增 `atomic_write_text`（同目录 mkstemp + fsync + os.replace）；`save_platform_config` 接入。
4. `set_default_variant` / `set_module_default_for_model` 写前严格读取；`config_parse_error` / `parser_missing` 在任何 mutate 之前返回；原文件不变。

## 验证记录

自动化：

```text
uv run python -m pytest src/fwasset/tests/test_config_io.py src/fwasset/tests/test_platform_config.py src/fwasset/tests/test_platform_default_service.py src/fwasset/tests/test_scheme_workbench_model.py src/fwasset/tests/test_workbench_panel_helpers.py -q --no-cov
→ 113 passed

uv run python -m pytest -m "not ui" -q
→ 281 passed, 52 deselected；coverage 84.58% (>= 80%)
```

人工验证：用户确认通过（合法配置 / 无配置初始化 / 损坏禁止覆盖）。

## 相关 Commit

`72d1cca` fix(core): 平台配置严格读取与原子写盘（TASK-20260716）
