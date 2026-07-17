# TASK-20260716: 平台配置读取与原子写盘安全收口

> **For Hermes:** 实施时使用 `test-driven-development`，逐项完成 RED → GREEN → REFACTOR；本 TASK 涉及核心配置逻辑，必须在人工验证通过后才能 commit。

## 状态

| 项 | 状态 |
| --- | --- |
| 类型 | Phase A.1 安全收口 / Phase B0 前置 |
| 当前状态 | ✅ 人验通过并提交 |
| 父任务 | `specs/active/TASK-20260714-config-takeover.md` |
| 分支 | 建议从 `feature/pyside6-migration` 当前 HEAD 切 `feature/config-takeover` 后实施 |
| 前置 | Phase A 已提交并人验通过（`094f441`） |
| 后续 | 本 TASK 人验并提交后，才开始父任务 Phase B0 |

## Goal

防止损坏或不可读取的 `平台配置.toml` 被误判为“无配置”后静默覆盖，并把平台配置写入改为同目录临时文件 + 原子替换，确保写入失败时原文件保持不变。

## Architecture

保留现有 `load_platform_config(model_root) -> list[PlatformDefaults]` 兼容读取接口，新增带状态的严格读取接口供写服务使用；只有 `missing` 或合法的空配置允许 bootstrap。新增 core 层通用原子文本写入助手，`save_platform_config()` 统一通过该助手落盘，为后续 `型号配置.toml` 提供可复用但不夹带 B0 业务的安全基础。写服务必须先完成严格读取和错误拦截，再调用 `ensure_platform_blocks()` / `_apply_module_default()`；任何 mutate/bootstrap 都不得发生在严格读取拦截之前。

## Tech Stack

Python 3.8+、`pathlib`、`tempfile.mkstemp`、`os.replace`、`os.fsync`、TOML（`tomllib` / `tomli`）、pytest。

---

## 背景与已验证问题

当前代码：

- `src/fwasset/core/platform_config.py:31-52`：文件缺失、解析失败、解析器不可用都返回 `[]`；
- `src/fwasset/core/services/platform_default_service.py:195-204`：`[]` 会进入 `ensure_platform_blocks()`，随后整体重写配置；
- `src/fwasset/core/platform_config.py:118-119`：直接 `Path.write_text()`，不是原子替换。

已在临时目录复现：损坏的既有 `平台配置.toml` 在执行“设为默认”后，服务返回 `ok`，原文件被覆盖为单一内部块 `默认`。这属于配置数据丢失风险。

## 不可变约束

1. 缺少配置文件仍须支持 Phase A：首次设默认时自动初始化。
2. 合法但没有 `[[platform]]` 的空配置仍可按 A2 bootstrap。
3. 已有合法配置继续保留历史块，并把型号+模块默认同步写入全部块。
4. 损坏配置、结构错误或解析器不可用时禁止写入，原文件必须字节级保持不变。
5. 用户可见消息使用中文；不得要求烧录员手工编辑 TOML。
6. `平台配置.toml` 仍只承载 `[[platform]]` + `defaults`。
7. 本 TASK 不创建或读取 `型号配置.toml`，不实现 `model_id`、`shared_modules` 或 Phase B/C。
8. 不修改 `types.py`，不改变 `ServiceResult` 的四键结构。
9. 不启动 UI 或自动运行 `@pytest.mark.ui` 测试；UI 行为由用户人工验证。
10. 不对 `D:\按摩器程序` 做破坏性验证；损坏配置与失败写入只能在 pytest 临时目录或人工创建的测试副本中验证。

---

## 决策：严格读取状态与服务错误码

### 严格读取接口

在 `src/fwasset/core/platform_config.py` 新增：

```python
from typing import Literal

PlatformConfigStatus = Literal[
    "ok",
    "missing",
    "parse_error",
    "parser_missing",
]


def load_platform_config_with_status(
    model_root: Path,
) -> tuple[list[PlatformDefaults], PlatformConfigStatus, str]:
    ...
```

状态语义：

| 状态 | 含义 | 写服务行为 |
| --- | --- | --- |
| `ok` | TOML 可解析且结构合法；允许 0 个 platform 块 | 继续，空列表可 bootstrap |
| `missing` | 文件不存在 | 继续，按 A2 bootstrap |
| `parse_error` | TOML 语法错误或结构不符合平台配置契约 | 拒绝写入，保留原文件 |
| `parser_missing` | `tomllib` / `tomli` 均不可用 | 拒绝写入，保留原文件 |

兼容接口保持：

```python
def load_platform_config(model_root: Path) -> list[PlatformDefaults]:
    platforms, status, _error = load_platform_config_with_status(model_root)
    return platforms if status == "ok" else []
```

兼容接口继续服务只读 UI 路径；所有会写盘的服务必须改用严格接口，禁止再用 `[]` 推断“文件不存在”。

### 结构校验

严格读取至少校验：

- TOML 顶层是 table；
- `platform` 缺失时视为合法空配置；
- `platform` 存在时必须是 array of tables；
- 每个 platform 条目必须是 table；
- `defaults` 缺失时按空 table；存在时必须是 table；
- 历史兼容：无 `name` / 空 `name` 的条目继续跳过，不单独判损坏；即使文件含有 `[[platform]]` 但所有条目都没有有效名称，整体仍判为 `ok` 且返回空列表，允许 A2 bootstrap；
- 键和值延续现行为字符串化，但容器结构错误必须返回 `parse_error`。

### 服务错误码

`set_default_variant()` 与 `set_module_default_for_model()` 统一增加：

| code | 条件 | 用户消息原则 |
| --- | --- | --- |
| `config_parse_error` | 既有平台配置无法解析或结构错误 | “平台配置读取失败，已停止写入并保留原文件” |
| `parser_missing` | TOML 解析组件不可用 | “平台配置读取组件不可用，已停止写入” |

保留既有：`ok`、`invalid_args`、`write_failed`。原子临时写入、`fsync` 或 `os.replace` 失败均返回 `write_failed`；不得退回直接覆盖目标文件。

CTk 和 Qt 当前都对 `result["ok"] is False` 统一记录日志并弹出 `result["message"]`，因此本 TASK 不新增 UI 分支；人工验证确认两壳均能显示新消息。

---

## 决策：原子文本写入

新增 `src/fwasset/core/config_io.py`：

```python
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """在目标同目录写临时文件，flush/fsync 后用 os.replace 原子替换。"""
    target = Path(path)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as file_obj:
            file_obj.write(content)
            file_obj.flush()
            os.fsync(file_obj.fileno())
        os.replace(temp_path, target)
    except BaseException:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
```

实施注意：

- 临时文件必须和目标文件同目录，保证 `os.replace` 不跨文件系统；
- 不在 helper 内自动创建父目录，型号根不存在仍由服务返回 `invalid_args`；
- 替换成功后不保留 `.tmp`；
- 写入、`fsync` 或替换失败时清理 `.tmp`，并让异常上抛给服务包装；Windows、网络盘或杀软环境中的 `fsync` 失败也必须走 `write_failed`，原文件保持不变；
- 不引入第三方 TOML writer 或 `tomlkit`。

`save_platform_config()` 先完整生成字符串，再调用：

```python
atomic_write_text(toml_path, "\n".join(lines) + "\n")
```

---

## 实施计划（TDD）

### Task 1：为原子写入建立失败测试

**Objective:** 先钉住“失败时原文件不变、临时文件清理”的核心契约。

**Files:**

- Create: `src/fwasset/tests/test_config_io.py`
- Future create: `src/fwasset/core/config_io.py`

**Step 1 — RED：新增测试**

至少覆盖：

1. 新文件写入成功，内容与换行正确；
2. 覆盖既有文件成功；
3. monkeypatch `os.replace` 抛 `OSError` 时，既有目标内容字节级不变；
4. monkeypatch `os.fsync` 抛 `OSError` 时，既有目标内容字节级不变；
5. 替换或 fsync 失败后同目录没有 `.{目标名}.*.tmp` 残留；
6. 目标原本不存在且替换失败时，不产生半成品目标文件；
7. 中文目录和中文文件名可写。

**Step 2 — 验证 RED**

```bash
uv run python -m pytest src/fwasset/tests/test_config_io.py -q --no-cov
```

Expected: FAIL，原因是 `fwasset.core.config_io` 或 `atomic_write_text` 尚不存在。

**Step 3 — GREEN：实现最小原子写入助手**

创建 `src/fwasset/core/config_io.py`，按上文原子写入决策实现。

**Step 4 — 验证 GREEN**

```bash
uv run python -m pytest src/fwasset/tests/test_config_io.py -q --no-cov
```

Expected: PASS。

---

### Task 2：为平台配置严格读取建立状态测试

**Objective:** 区分缺失、合法、损坏和解析器缺失，不破坏原兼容接口。

**Files:**

- Modify: `src/fwasset/tests/test_platform_config.py`
- Modify later: `src/fwasset/core/platform_config.py`

**Step 1 — RED：新增测试**

至少覆盖：

1. 文件不存在 → `([], "missing", "")`；
2. 合法配置 → `status == "ok"` 且内容正确；
3. 合法空文件或无 `platform` 键 → `([], "ok", "")`；
4. 含一个或多个 `[[platform]]` 但所有条目都无 `name` / `name = ""` → `status == "ok"` 且返回空列表，不能判为 `parse_error`；此用例必须独立测试，不得只依赖空文件覆盖；
5. TOML 语法错误 → `status == "parse_error"` 且 error 非空；
6. `platform` 是 table 而不是 array of tables → `parse_error`；
7. `defaults` 不是 table → `parse_error`；
8. monkeypatch `tomllib = None` → `parser_missing`；
9. 原 `load_platform_config()` 对缺失/损坏仍返回 `[]`，保持只读兼容；
10. 原 round-trip、转义、机芯版/板兼容测试继续通过。

**Step 2 — 验证 RED**

```bash
uv run python -m pytest src/fwasset/tests/test_platform_config.py -q --no-cov
```

Expected: 新严格接口相关测试 FAIL。

**Step 3 — GREEN：实现严格读取并保留兼容 wrapper**

修改 `src/fwasset/core/platform_config.py`：

- 增加 `PlatformConfigStatus`；
- 增加 `load_platform_config_with_status()`；
- 把解析与结构校验集中在严格接口；
- `load_platform_config()` 仅作兼容 wrapper；
- 不在此步骤改变写服务。

**Step 4 — 验证 GREEN**

运行同一命令，Expected: PASS。

---

### Task 3：把平台配置保存切换为原子替换

**Objective:** `save_platform_config()` 不再直接截断目标文件。

**Files:**

- Modify: `src/fwasset/core/platform_config.py`
- Modify: `src/fwasset/tests/test_platform_config.py`

**Step 1 — RED：新增集成测试**

monkeypatch `fwasset.core.config_io.os.replace` 抛异常，通过 `save_platform_config()` 写既有配置，断言：

- 抛出 `OSError`；
- 原配置文本完全不变；
- 无临时文件残留。

**Step 2 — 验证 RED**

```bash
uv run python -m pytest src/fwasset/tests/test_platform_config.py -q --no-cov
```

Expected: 当前直接 `write_text()` 会覆盖文件，新增测试 FAIL。

**Step 3 — GREEN：接入 `atomic_write_text()`**

`save_platform_config()` 只替换最终写盘动作，不改变 TOML 序列化格式和返回路径。

**Step 4 — 验证 GREEN**

运行同一命令，Expected: PASS。

---

### Task 4：写服务遇到损坏配置时停止写入

**Objective:** 两个写 API 都必须使用严格读取状态，损坏配置绝不 bootstrap。

**Files:**

- Modify: `src/fwasset/tests/test_platform_default_service.py`
- Modify: `src/fwasset/core/services/platform_default_service.py`

**Step 1 — RED：新增服务测试**

对 `set_default_variant()` 与 `set_module_default_for_model()` 分别覆盖：

1. 损坏 TOML → `ok is False`；
2. `code == "config_parse_error"`；
3. 消息包含“已停止写入”与“保留原文件”；
4. 原文件字节级不变；
5. parser missing → `code == "parser_missing"`，原文件不变；
6. `os.replace` 失败 → `code == "write_failed"`，原文件不变且无临时文件；
7. `os.fsync` 失败 → `code == "write_failed"`，原文件不变且无临时文件；
8. 文件缺失 → 原 Phase A bootstrap 测试仍成功；
9. 合法空配置 → 仍按 A2 初始化；
10. 合法已有配置 → 保留历史块并同步全部块。

特别增加“拦截先于 mutate”断言：对损坏 TOML 调用写 API 时，monkeypatch `ensure_platform_blocks` / `_apply_module_default` 为一旦调用就失败，测试必须证明两个 helper 都不会被调用；该测试不依赖“写盘失败后的原子回滚”来证明安全。

**Step 2 — 验证 RED**

```bash
uv run python -m pytest src/fwasset/tests/test_platform_default_service.py -q --no-cov
```

Expected: 损坏配置目前会被覆盖并返回 `ok`，新增测试 FAIL。

**Step 3 — GREEN：集中处理严格读取结果**

在 `platform_default_service.py` 增加私有 helper，供两个写 API 共用。执行顺序必须固定为：严格读取 → 根据 status 返回错误或取得 platforms → `ensure_platform_blocks()` → `_apply_module_default()` → 序列化 → 原子写盘；其中 parse_error / parser_missing 的错误返回必须发生在任何 `ensure_platform_blocks()`、列表 append、`_apply_module_default()` 或其他内存 mutate/bootstrap 之前：

- `ok` / `missing`：返回 platforms，允许继续；
- `parse_error`：生成 `config_parse_error`；
- `parser_missing`：生成 `parser_missing`；
- 错误结果始终保持 `{"ok", "code", "message", "payload"}` 四键结构；
- 不复制两套状态映射逻辑；
- 不把读取错误包装成 `write_failed`。

**Step 4 — 验证 GREEN**

运行同一命令，Expected: PASS。

---

### Task 5：工作台集成回归

**Objective:** 确认 view model 不会吞掉新服务失败，并保持 Phase A 行为。

**Files:**

- Modify: `src/fwasset/tests/test_scheme_workbench_model.py`
- Production UI files: expected no change

**Step 1 — RED/契约测试**

新增或补强：

1. 绑定到有损坏 `平台配置.toml` 的临时型号根；
2. 对通用资产调用 `SchemeWorkbenchModel.set_default_variant()`；
3. 结果为 `config_parse_error`；
4. 原配置不变；
5. model 不伪造新的 `_platforms`；
6. 无配置首次设置、方案 platform 初始化、设置后免重扫更新徽章等现有测试继续通过。

**Step 2 — 运行针对性回归**

```bash
uv run python -m pytest \
  src/fwasset/tests/test_config_io.py \
  src/fwasset/tests/test_platform_config.py \
  src/fwasset/tests/test_platform_default_service.py \
  src/fwasset/tests/test_scheme_workbench_model.py \
  src/fwasset/tests/test_workbench_panel_helpers.py \
  -q --no-cov
```

Expected: PASS。

如 view model 已正确透传失败，则无需修改生产代码；禁止为了“有改动”而修改 CTk/Qt。

---

### Task 6：非 UI 自动化门禁

**Objective:** 确认 core 安全修补没有破坏其他非 UI 逻辑和覆盖率门禁。

**只运行非 UI 测试：**

```bash
uv run python -m pytest -m "not ui" -q
```

Expected:

- 所有非 UI 测试通过；
- coverage >= 80%；
- UI 测试被 deselect，不启动桌面窗口。

禁止由 Agent 自动执行：

```text
scripts/test.ps1
uv run fwasset
FWASSET_UI=qt uv run fwasset
任何未过滤 @pytest.mark.ui 的全量测试
```

---

### Task 7：审查记录、CHANGELOG 与父任务同步

**Objective:** 按仓库规范记录本次核心配置契约变化，但在人工验证前不提交。

**Files:**

- Create: `docs/code-review/REVIEW-20260716-platform-config-safety.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `specs/active/TASK-20260714-config-takeover.md`
- Modify: 本文件状态与 checklist

审查文档记录：

- 类型：核心配置安全 / 服务错误码；
- 问题：损坏 TOML 被视为空配置并覆盖；直接写入可能截断；
- 处理：严格读取状态 + 原子替换；
- 新错误码：`config_parse_error`、`parser_missing`；
- 自动化验证命令与结果；
- 人工验证状态；
- 相关 commit 在提交后补写。

父任务增加或更新 Phase B0 前置说明：

```text
[x] Phase A.1 平台配置解析/原子写盘安全收口（人验通过后勾选）
```

在本 TASK 人验通过前，父任务 B0 保持未开始。

---

## 人工验证（必须在 commit 前）

完成代码与非 UI 自动化后，Agent 必须明确回复：

```text
已完成，请人工验证
```

并列出实际运行的非 UI 命令及结果。用户只在测试副本中执行以下场景：

### 场景 1：既有合法配置不回退

- 使用复制出的测试型号根；
- CTk 与 Qt 各设置一次通用模块默认；
- 结果：成功；历史 platform 块保留；全部块同步；徽章和方案补齐免重扫更新。

### 场景 2：无配置仍可初始化

- 测试型号根删除副本中的 `平台配置.toml`；
- 设置默认；
- 结果：成功创建；有方案 platform 时按方案名建块，无方案时使用内部块 `默认`。

### 场景 3：损坏配置禁止覆盖

- 在测试副本中准备损坏的 `平台配置.toml`，先记录原始内容或校验值；
- CTk 与 Qt 各触发一次“设为默认”；
- 结果：显示中文失败消息；原文件内容完全不变；不出现半截文件或 `.tmp` 残留。

### 场景 4：现场目录只读确认

- 不修改 `D:\按摩器程序`；
- 确认本次人工测试全部使用副本；
- 真实现场配置写入仍留到后续正常业务操作，不用故障注入验证。

人工回复“验证通过”后才允许：

1. 把本 TASK 标记完成；
2. 更新审查文档人工验证状态；
3. 按 `docs/COMMIT_TEMPLATE.md` 生成 Conventional Commit；
4. commit；
5. 返回父任务并开始 Phase B0。

建议提交信息：

```text
fix(core): 防止平台配置损坏时被覆盖

- 区分平台配置缺失、解析失败与解析器不可用
- 写服务遇到损坏配置时停止写入并保留原文件
- 平台配置改用同目录临时文件和原子替换
- 补充失败保留、临时文件清理与 Phase A 回归测试

影响范围:
- core/platform_config 与 platform_default_service
- 平台配置写盘与错误提示

验证:
- 平台配置相关纯数据层测试通过
- 非 UI 测试与覆盖率门禁通过
- CTk / Qt 人工验证通过
```

---

## Files Likely to Change

| 操作 | 路径 | 目的 |
| --- | --- | --- |
| Create | `src/fwasset/core/config_io.py` | 通用原子文本写入 |
| Create | `src/fwasset/tests/test_config_io.py` | 原子写入成功/失败契约 |
| Modify | `src/fwasset/core/platform_config.py` | 严格读取状态、结构校验、原子保存 |
| Modify | `src/fwasset/core/services/platform_default_service.py` | 写前严格读取和错误映射 |
| Modify | `src/fwasset/tests/test_platform_config.py` | 状态/结构/原子保存测试 |
| Modify | `src/fwasset/tests/test_platform_default_service.py` | 防覆盖与服务错误码测试 |
| Modify | `src/fwasset/tests/test_scheme_workbench_model.py` | 工作台失败透传与 Phase A 回归 |
| Create | `docs/code-review/REVIEW-20260716-platform-config-safety.md` | 核心配置审查记录 |
| Modify | `docs/CHANGELOG.md` | 未发布变更 |
| Modify | `specs/active/TASK-20260714-config-takeover.md` | 标记 B0 前置状态 |
| Modify | `specs/active/TASK-20260716-platform-config-write-safety.md` | 实施与验收进度 |

预计不改：

- `src/fwasset/ui/workbench_panel.py`
- `src/fwasset/ui_qt/workbench_window.py`
- `src/fwasset/core/types.py`
- 数据库 schema
- `D:\按摩器程序` 现场文件

---

## Definition of Done

- [ ] 严格读取能区分 `ok` / `missing` / `parse_error` / `parser_missing`。
- [ ] 原 `load_platform_config()` 兼容接口未破坏。
- [ ] 损坏 TOML 和解析器缺失时，两个写 API 都拒绝写入。
- [ ] 失败结果保持标准 `ServiceResult` 四键结构和中文消息。
- [ ] `save_platform_config()` 使用同目录临时文件 + `os.replace`。
- [ ] 写入/替换失败时原文件不变、无临时文件残留。
- [ ] 无配置首次初始化、方案 platform bootstrap、全块同步、A4/A5 行为不回退。
- [ ] 针对性纯数据层测试通过。
- [ ] `pytest -m "not ui"` 通过且 coverage >= 80%。
- [ ] 未自动启动 UI，未自动运行 UI 测试。
- [ ] CTk + Qt 人工验证通过。
- [ ] 未对 `D:\按摩器程序` 做故障注入或破坏性验证。
- [ ] CHANGELOG、代码审查文档、父任务状态同步。
- [ ] 人工确认后按模板提交；B0 才解除阻塞。

## Risks and Trade-offs

1. **兼容接口仍会把读取失败显示为空列表**：这是为了不一次性改动所有只读调用；安全边界由写服务的严格接口保证。后续可单独让 UI 展示配置健康状态，本 TASK 不扩 scope。
2. **新增错误码属于服务契约扩展**：结构不变，但需在代码审查文档和 CHANGELOG 中明确。
3. **`fsync`、`os.replace` 可能被权限、杀毒软件、网络盘或文件占用阻止**：两者都应返回 `write_failed`，清理临时文件且不能退回直接覆盖。
4. **原子替换不等于业务级备份**：本 TASK 保证旧文件在替换前不被截断，不增加 `.bak`、历史版本或修复 UI。
5. **共享写入 helper 为 B0 可复用基础，但不是提前实施 B0**：本 TASK 结束时不得出现任何 `型号配置.toml` 业务代码。

## Open Questions

无。范围、错误状态、错误码、原子写入方式和人工验证边界均在本计划中写死；实施前如需改变，应先修改本 TASK 并由用户确认。
