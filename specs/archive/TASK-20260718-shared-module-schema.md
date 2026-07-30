# TASK-20260718: 共享引用 schema + 解析器（Phase B1）

> **For Hermes:** 实施时使用 `test-driven-development`，逐项 RED → GREEN → REFACTOR；本 TASK 动 core（`型号配置.toml` 共享段读写 + 新解析器）与工作台 view model，**必须人工验证通过后才能 commit**。

## 状态

| 项 | 状态 |
| --- | --- |
| 类型 | 父任务 Phase B1（B2–B3 前置） |
| 当前状态 | ✅ 数据层验收通过并提交 |
| 父任务 | `specs/archive/TASK-20260714-config-takeover.md`（B1 专节 + 落盘文件专节为契约源） |
| 分支 | 继续 `feature/pyside6-migration`（或按父任务约定，实施前定） |
| 前置（代码） | **B0**（`TASK-20260717`）已提交（`1c287b8`）；`TASK-20260716`（原子写）已提交（`72d1cca`） |
| 后续 | 本 TASK 人验并提交后，才开始 B2（登记入口）/ B3（UI 共享态） |

## Goal

在 B0 的 `型号配置.toml` 之上，加 `[shared_modules.*]` 段的**读写**（读-合并-写回，保留 `model_id` 与未知键）与**一套解析器**：把一条共享引用解析为「命中（可跳转/可烧的具体路径或变体）」或「缺失（源未导入 / 路径不存在 / id 不符）」。**只做数据层 schema + 解析器 + 工作台最小 load/save API**；**不**实现登记入口（B2）、**不**实现 UI 共享态渲染（B3）、**不**碰方案回源（B4）、**无** `mode` 字段（Phase C）。

## Architecture

扩展 `core/model_config.py`：新增 `SharedModuleRef` 数据模型、`load_shared_modules(model_root)`、`save_shared_module(model_root, ref)` / `remove_shared_module(model_root, module_key)`（均**读-合并-写回**，复用 B0 的行级/表级保留策略与 `atomic_write_text`，**保留** `model_id`）。新增 `core/shared_module_resolver.py`（或 `core/services/shared_module_service.py`，实施前择一并写死）：`resolve_shared_module(ref, workspace_root, id_lookup) -> SharedModuleResolution`，一套解析路径覆盖命中/缺失两分支。`SchemeWorkbenchModel` 加最小 API：`get_shared_modules(model_name)` 读该型号引用、`resolve_shared_module(model_name, module_key)` 走解析器；**不**改 `get_scheme_modules` / `get_scheme_module_tree`（B4 隔离）。

## Tech Stack

Python 3.11+（`requires-python` 已收紧到 `>=3.11`，`tomllib` 为 stdlib）、`pathlib`、TOML 读（`tomllib`）、**TOML 写（`tomli-w`，本 TASK 新增无条件依赖）**、`core.config_io.atomic_write_text`、B0 的 `core.model_config`、pytest。

---

## 契约来源（父任务 B1 / 落盘文件 / B4 专节，已写死）

本 TASK 不重述、不修改父任务语义；以下为执行必须遵守的要点复述：

1. **落盘文件 = 型号根/`型号配置.toml`**；共享段写 `[shared_modules.*]`；**禁止**把 `model_id` / `shared_modules` 写进 `平台配置.toml`；**禁止**写进 `通用/`；**禁止**调用 `save_platform_config` 碰该文件。
2. **保存共享保留 `model_id`；保存 `model_id`（B0）保留 `shared_modules`。** 两侧读-合并-写回互不覆盖。
3. **无 `mode` 字段**：B 期 toml / 解析器中**禁止**出现 `mode` / `follow_default` / `pinned`。
4. **`source_relative_path` 永远相对固件工作区根**（路径含源型号目录段，如 `L36程序/通用/快捷键/贝乐`）；**禁止**相对当前型号根 / 源型号根。
5. **id 校验**：绝对路径 = `工作区根 / source_relative_path`；解析时**校验路径第一段所属型号根的 `model_id == source_model_id`**；不符 → 缺失。
6. **命中**：源已导入 + 路径存在 + id 相符 → 可跳转、可烧（单路径直接；多变体列出源侧变体待用户选）。**缺失**：源未导入 / 路径无 / id 不符 → 「共享来源缺失」；**禁止**静默跨型号搜同名、**禁止**回落本地副本。
7. **防 `..`**：解析后的绝对路径必须仍在工作区根内。**禁止**引用链递归与循环。
8. **键 = 目标型号规范模块键**（`canonical_module_dir`，如 `快捷键` / `3D机芯板程序`）；`source_module` 同用规范名；**禁止** `机芯版`/`机芯板` 各成一条。
9. **B4 隔离**：解析器 / 共享读写**不得**被 `get_scheme_modules` / 回源路径调用；本 TASK 不改回源代码。

## 不可变约束

1. 不实现 B2 登记入口（手动「设为共享」右键、`.ref` 迁移预览确认）；本 TASK 的 `save_shared_module` 仅为 B2 打底的**纯数据写盘 API**，不接 UI、不做冲突弹窗、不读 `.ref`。
2. 不实现 B3 UI 渲染（角标、打开来源、可烧、缺失灰掉）；本 TASK 只提供解析结果数据，不画界面。
3. 不改 `get_scheme_modules` / `get_scheme_module_tree` / 任何方案回源逻辑（B4）。
4. 不引入 `mode` / `follow_default` / `pinned`（Phase C）。
5. 不改 `平台配置.toml` 格式或 `save_platform_config`。**允许**把 B0 的 `save_model_id` 内部改造为与共享写**同一套 dict 读-合并-写回**（见下方决策），但**对外行为不回退**：`save_model_id` 仍是「保留其余键、只覆盖 `model_id`」；B0 现有测试全过。
6. 不修改 `types.py::FirmwareAsset` / `ServiceResult` 四键结构；不改数据库 schema（共享引用**只**存 toml，**不**进 SQLite 索引）。
7. 用户可见消息中文；不要求手写 TOML。
8. 不自动启动 UI、不自动跑 `@pytest.mark.ui`；不对 `D:\按摩器程序` 做破坏性写入（失败注入只在 pytest 临时目录）。
9. 单型号根与多型号父根两种布局都要支持；解析器的「工作区根」= 扫描根（多型号父根即父目录）。

---

## 决策：schema、读写与解析（实现前写死）

### `SharedModuleRef` 数据模型（B 期四字段，无 mode）

```python
@dataclass
class SharedModuleRef:
    module_key: str            # 目标型号规范模块键（toml 中 [shared_modules.<module_key>]）
    source_model_id: str       # B0 的 model_id
    source_group: str          # 源侧分组/共用区 id，如 "l50s-l66s-dual" / "l36-single"
    source_module: str         # 源模块逻辑名（规范）
    source_relative_path: str  # 相对固件工作区根 的确定物理路径（模块目录 或 变体目录）
```

### `型号配置.toml` 共享段格式（对齐父任务示例）

```toml
# 本文件由 fwasset 管理（型号 id + 共享引用）。用户无需手写。
model_id = "l36双机芯-上3d-下2d"

[shared_modules."快捷键程序"]
source_model_id = "l36"
source_group = "l36-single"
source_module = "快捷键程序"
source_relative_path = "L36程序/通用/快捷键/贝乐"
# Phase B：禁止写入 mode；Phase C 再增加 follow_default / pinned
```

### 读写 API（`core/model_config.py`，读-合并-写回）

- `load_shared_modules(model_root) -> list[SharedModuleRef]`：文件不存在 / 无 `[shared_modules]` → 空列表；缺字段的条目按契约处理（**默认策略：字段缺失 → 跳过该条并可选打日志；测试固定此行为**）；解析失败不抛，返回已成功解析部分（与 B0 只读容错一致）。
- `save_shared_module(model_root, ref)`：**读原文件全文** → **保留 `model_id` 与其它 `[shared_modules.*]` 段** → 覆盖/新增 `ref.module_key` 对应段 → `atomic_write_text`。同 `module_key` 已存在 → **覆盖该段**（B2 的「不静默覆盖」在 UI 层拦，本数据 API 是幂等写）。
- `remove_shared_module(model_root, module_key)`：删除该段；**不删任何固件文件**（对齐 B4b「取消共享只删 toml 条目」）；`model_id` 与其余段保留。
- 三个 API **均不**调用 `save_platform_config`；落盘目录严格为传入 `model_root`。

#### 写回策略（**已定，用户确认 2026-07-18**）：dict 读-合并-自写序列化，B0 一并改

1. **统一一套 dict 合并写**：`save_model_id`、`save_shared_module`、`remove_shared_module` 共用一个「读全量 dict → 局部改一个键 → 写回**整个 dict**」的 helper（如 `_merge_write_model_config(model_root, mutate: Callable[[dict], None])`）。**B0 的 `save_model_id` 在本 TASK 一并从「文本行级替换」改为这套 dict 合并**——避免行级替换与 dict 写两套并存、交替调用时互相打架（一个保结构丢注释、一个保注释丢结构）。
2. **合并 = 改现有完整 dict 的一个键，不是重建 dict**（核心防坑，正是父任务警告的 `save_platform_config` 整写删段的反面）：
   - `save_model_id`：`data = 读全量`；`data["model_id"] = 新值`；写回 `data`（含 `shared_modules` 与任何未知 table）。**禁止**只写 `{"model_id": ...}`。
   - `save_shared_module`：`data = 读全量`；`data.setdefault("shared_modules", {})[ref.module_key] = {四字段}`；写回 `data`（含 `model_id`）。
   - `remove_shared_module`：`data = 读全量`；`data.get("shared_modules", {}).pop(module_key, None)`（空了可保留空表或删表，实施时定，删不存在键不报错）；写回 `data`。
3. **不丢什么**：`model_id`、全部 `shared_modules` 段、**未知顶层键 / 未知 table** 均随 dict 往返保留（含 Phase C 预留字段）。
4. **注释**：dict 重写会丢用户注释——**可接受**；但序列化时**固定重新打印文件头注释**（`# 本文件由 fwasset 管理…` 两行是固定文案、非用户数据），使体验上文件头注释不丢。
5. **序列化用 `tomli-w`（新增依赖，用户确认）**：不再手写「带引号 table 头 + 嵌套 table」的拼串；`tomli_w.dump(data, f)` 落到 `atomic_write_text` 的临时文件流。文件头注释在 `tomli_w.dump` 输出前手工 `f.write(...)` 前置（或 dump 成字符串后前缀拼接，实施时择一）。加入 `pyproject.toml` `dependencies`（**无条件**，`tomli-w` 无 stdlib 等价物，不像 `tomli` 那样 gate 在 `python_version < '3.11'`）。
6. 三个 API **均不**调用 `save_platform_config`；落盘目录严格为传入 `model_root`。

### 解析器（一套路径，命中/缺失两分支）

```python
@dataclass
class SharedModuleResolution:
    ref: SharedModuleRef
    status: Literal["hit", "missing"]
    reason: str                 # missing 时：source_not_imported / path_not_found / id_mismatch / out_of_workspace
    resolved_path: Path | None  # hit：模块目录 或 变体目录的绝对路径
    variants: list[Path]        # hit：源侧可烧目录列表（见下方 variants 判定，永不为空）
```

`resolve_shared_module(ref, workspace_root, root_for_model_id) -> SharedModuleResolution`：

1. `abs_path = (workspace_root / ref.source_relative_path)`；`resolve()` 后必须仍在 `workspace_root` 内，否则 `missing / out_of_workspace`。
2. 取 `source_relative_path` **第一段目录** → 找其型号根 → 经 `root_for_model_id`（或反查）得该根 `model_id`；与 `ref.source_model_id` 不符 → `missing / id_mismatch`；源根不在工作区（无此 id）→ `missing / source_not_imported`。
3. `abs_path` 不存在 → `missing / path_not_found`。
4. 命中：`status="hit"`，`resolved_path=abs_path`；`variants` 按下方**判定规则**产出（永不为空）。
5. **禁止**在缺失时跨型号搜同名、**禁止**回落本地副本、**禁止**递归解析引用链。

#### variants 判定（**已定，用户确认 2026-07-18**）

以 `abs_path` 的**直接子目录列表**为准（过滤后）：

| 情况 | variants |
| --- | --- |
| `abs_path` 是变体目录（叶子，过滤后直接子目录为空） | `[abs_path]` |
| `abs_path` 是模块目录且过滤后有子目录 | 过滤后的直接子目录列表 |
| `abs_path` 是模块目录但过滤后无子目录（文件直接躺模块层） | `[abs_path]` |

- **叶子判定 = 过滤后直接子目录列表为空 → 视为变体/叶子，不再往下展**（不依赖 catalog 名匹配）。
- **过滤规则**：只列**目录**（忽略文件）；沿用 [`scheme_config._is_excluded_dir`](src/fwasset/core/scheme_config.py:91) 跳过 `backup/旧/temp/tmp` 等噪声目录。
- **排序**：`variants` 按目录名排序，保证跨机器/跨扫描顺序稳定、UI 变体顺序不抖、测试可断言。
- **永不为空**：命中时至少 `[abs_path]`（模块层直接放文件的情形也可烧）。

> `root_for_model_id` 由调用方注入（view model 传 `self.model_root_for_id`；纯 core 测试传 lambda / dict），保持解析器对 view model 无硬依赖、可单测。

---

## 实施计划（TDD）

### Task 1：`SharedModuleRef` + `load_shared_modules`（读）

**Files:** Modify `src/fwasset/tests/test_model_config.py`（或新建 `test_shared_module_config.py`，实施前择一）；Modify `src/fwasset/core/model_config.py`

**RED** — 覆盖：
1. 无文件 / 有文件无 `[shared_modules]` → `[]`；
2. 一段合法引用 → 一个 `SharedModuleRef`，四字段读回正确；
3. 多段 → 列表按键有序/稳定；
4. 某段缺 `source_relative_path` 等必需字段 → 该条按固定策略跳过（其余正常返回）；
5. 与 `model_id` 共存：文件含 `model_id` + 共享段，`load_model_config` 仍读回 id、`load_shared_modules` 读回引用（互不干扰）；
6. 语法错误 / `tomllib=None` → 空列表容错（不抛）。

**GREEN:** 实现 `SharedModuleRef` 与 `load_shared_modules`。

---

### Task 2：`save_shared_module` / `remove_shared_module`（读-合并-写回）

**Files:** Modify 同上测试；Modify `src/fwasset/core/model_config.py`

**RED** — 覆盖：
1. 空文件（无 toml）→ `save_shared_module` 新建文件含该段（**不**要求同时有 `model_id`，但若传入根已有 `model_id` 必须保留）；
2. **保留 `model_id`**：预置 `model_id = "x"`，`save_shared_module` 后 `load_model_config` 仍读回 `x`；
3. **保留其它共享段**：已有段 A，`save_shared_module` 段 B → A、B 都在；
4. **同键覆盖幂等**：对同 `module_key` 连写两次（字段不同）→ 只剩一段、值为后者、无重复键；
5. `remove_shared_module`：删指定段后其余段与 `model_id` 保留；删不存在的键 → 无异常、文件不损坏；
6. **B0 往返不丢**：`save_model_id` 后 `save_shared_module` 后再 `save_model_id`（改 id）→ 共享段仍在、id 为最后值（守住父任务「两侧互不覆盖」）；
7. **原子写**：monkeypatch `config_io.os.replace` 抛错 → 原文件字节不变、无 `.tmp` 残留；
8. **未知 table 保留**：预置文件含 `model_id` + 一段自定义未知 table（如 `[future_section]`）→ `save_shared_module` / `save_model_id` 后该未知 table 仍在（守住 Phase C 预留字段往返）；
9. **文件头注释固定重打**：dict 重写后，文件头 `# 本文件由 fwasset 管理…` 两行仍在（固定文案重新前置）；
10. **B0 现有测试全过**：`save_model_id` 改为 dict 合并后，`test_model_config.py` 中 B0 既有断言（含 `test_save_preserves_shared_modules_section`、`test_save_replace_failure_keeps_bytes`、`test_chinese_model_root`）不回退。

**GREEN:** 用 `tomli-w` 实现共用 helper `_merge_write_model_config(model_root, mutate)`（读全量 dict → `mutate(data)` 局部改键 → 固定前置文件头注释 → `tomli_w` 序列化 → `atomic_write_text`）。`save_model_id` / `save_shared_module` / `remove_shared_module` 三者都走它。**REFACTOR**：把 B0 `save_model_id` 从行级替换切到该 helper；删掉不再需要的 `_MODEL_ID_LINE` 正则与文本插入分支。加 `tomli-w` 到 `pyproject.toml` `dependencies`。

---

### Task 3：`resolve_shared_module` 解析器（命中/缺失一套路径）

**Files:** Create `src/fwasset/tests/test_shared_module_resolver.py`；Create `src/fwasset/core/shared_module_resolver.py`（或 service，Task 起点前写死）

**RED** — 用临时工作区（源型号根 `L36程序` + 通用变体目录 + 目标型号根）覆盖：
1. **命中·直指变体（叶子）**：`source_relative_path="L36程序/通用/快捷键/贝乐"` 存在且其下无子目录、`L36程序` 的 `model_id == source_model_id` → `hit`，`resolved_path` 正确，`variants == [该变体目录]`；
2. **命中·指模块目录多变体**：路径指到 `.../快捷键`（其下多变体子目录）→ `hit`，`variants` = **排序后**的全部子变体目录；
3. **命中·模块目录直接放文件（无子目录）**：路径指到模块目录但其下只有文件无子目录 → `hit`，`variants == [该模块目录]`（永不为空）；
4. **variants 过滤噪声**：模块目录下含 `backup`/`旧` 等目录 → 不出现在 `variants`（沿用 `_is_excluded_dir`）；
5. **缺失·路径不存在** → `missing / path_not_found`；
6. **缺失·源未导入**（`source_relative_path` 第一段型号根不在工作区 / 无此 id）→ `missing / source_not_imported`；
7. **缺失·id 不符**（路径存在但该源根 `model_id != source_model_id`）→ `missing / id_mismatch`；
8. **防 `..`**：`source_relative_path` 含 `../跨出工作区` → `missing / out_of_workspace`，不解析到工作区外；
9. **不跨型号搜同名**：源缺失时**不**去别的型号找同名模块（断言返回 missing 而非其它路径）。

**验证 RED / GREEN:** `uv run python -m pytest src/fwasset/tests/test_shared_module_resolver.py -q --no-cov`。

---

### Task 4：view model 最小 API（读引用 + 走解析器）

**Files:** Modify `src/fwasset/tests/test_scheme_workbench_model.py`；Modify `src/fwasset/ui/view_models/scheme_workbench_model.py`

**新增 API（名称可微调，语义固定）：**
- `get_shared_modules(model_name) -> list[SharedModuleRef]`：按型号根读 `型号配置.toml` 共享段（型号根枚举复用 B0 `_enumerate_model_roots` / `_platform_config_root` 纪律，**不落 `通用/`**）。
- `resolve_shared_module(model_name, module_key) -> SharedModuleResolution`：取该引用 → 调 `resolve_shared_module(ref, workspace_root=self.root_dir, root_for_model_id=self.model_root_for_id)`。

**RED** — 覆盖：
1. 目标型号根预置一条共享引用 → `get_shared_modules` 读回；
2. 源型号根在工作区且路径存在 → `resolve_shared_module` 返回 `hit`；
3. 源型号根不在工作区 → `missing / source_not_imported`；
4. **B4 隔离回归**：`get_scheme_modules` / `get_scheme_module_tree` 结果**不含**任何共享来源行（预置共享引用后，方案树不变——共享不参与回源补洞）；
5. **回归**：`load_all_models` / 侧栏 / 设默认 / A4–A5 / B0 id 映射测试全过；
6. 共享段损坏或只读的根：不抛未捕获异常，`get_shared_modules` 该根返回 `[]`（不阻断其余型号）。

**验证:**
```bash
uv run python -m pytest \
  src/fwasset/tests/test_model_config.py \
  src/fwasset/tests/test_shared_module_resolver.py \
  src/fwasset/tests/test_scheme_workbench_model.py \
  src/fwasset/tests/test_platform_default_service.py \
  src/fwasset/tests/test_model_id_service.py \
  -q --no-cov
```
Expected: PASS。

---

### Task 5：非 UI 门禁

```bash
uv run python -m pytest -m "not ui" -q
```
Expected: 全部非 UI 通过；coverage ≥ 80%；UI 测试 deselect。

**禁止 Agent 执行**：`scripts/test.ps1`、`uv run fwasset`、`FWASSET_UI=qt uv run fwasset`、任何未过滤 `@pytest.mark.ui` 的全量测试。

---

### Task 6：审查记录、CHANGELOG 与父任务同步

**Files:**
- Create `docs/code-review/REVIEW-20260718-shared-module-schema.md`（类型：核心配置扩展 / 新解析器；问题：跨型号共享需稳定引用 + 命中/缺失一套解析；处理：`型号配置.toml` `[shared_modules]` 读-合并-写回 + `resolve_shared_module`；验证记录；人验状态；commit 后补哈希）
- Modify `docs/CHANGELOG.md`（Unreleased 增条目）
- Modify `specs/archive/TASK-20260714-config-takeover.md`（B1 checklist 勾选、注明 `TASK-20260718` 承载；解锁 B2–B3）
- Modify 本文件状态与 DoD

---

## 人工验证（必须在 commit 前）

完成代码与非 UI 自动化后，Agent 明确回复「已完成，请人工验证」并列出实际命令与结果。用户在**测试副本**上（对齐父任务验收场景 4/6/7）：

### 场景（共用一个副本，逆序：先缺失 → 再命中 → 最后 B4 隔离）

1. **来源缺失**（父任务场景 6）：目标型号根 `型号配置.toml` 手写一条指向**未导入**源型号的共享引用 → 软件解析为 **「共享来源缺失」**（缺失分支）；不跨型号自动搜相似模块；不静默补本地副本。
2. **命中可解析**（父任务场景 4）：把源型号根扫入同工作区、路径存在、id 相符 → 同一引用解析为 **命中**，`resolved_path` 指向源变体/模块目录（多变体时列出源侧变体）。
3. **方案页不吃共享**（父任务场景 7）：目标型号已登记某模块共享，但该模块方案无定制专属、本型号通用也补不上 → **方案页该模块缺失、不出现「共享自 …」回源行**（B4 隔离）。
4. **设默认不破坏共享**：对已含 `shared_modules` 的型号「设为平台默认」→ `平台配置.toml` 更新、`型号配置.toml` 的 `model_id` 与共享段**原样保留**。

### 现场只读确认

不修改 `D:\按摩器程序`；上述均在副本执行（含手写引用条目）。

人工回复「验证通过」后：标记完成 → 更新审查文档 → 按 `docs/COMMIT_TEMPLATE.md` 提交 → 更新 CHANGELOG → 父任务 B1 勾选 → 解锁 B2–B3。

**建议提交信息：**
```text
feat(core): 共享引用 schema + 解析器（Phase B1）

- 型号配置.toml 新增 [shared_modules] 读-合并-写回（保留 model_id 与未知段）
- 统一 dict 合并写 helper（tomli-w 序列化）；save_model_id 一并切换，弃行级替换
- resolve_shared_module：一套解析器覆盖命中/缺失（源未导入/路径无/id 不符/越界）
- 工作台 get_shared_modules / resolve_shared_module；不参与方案回源（B4 隔离）
- 无 mode 字段；共享只存 toml 不进索引；写盘复用 atomic_write_text

影响范围:
- core/model_config（共享段读写 + B0 写改造）、core/shared_module_resolver（新）
- ui/view_models/scheme_workbench_model（读引用 + 解析 API）
- pyproject.toml（新增 tomli-w 依赖）

验证:
- 共享 schema 读写 / 保留 model_id / 原子失败测试通过
- 解析器命中/缺失/防越界/不跨型号搜同名测试通过
- B4 隔离回归（方案树不含共享行）通过
- 非 UI 测试与覆盖率门禁通过
- CTk / Qt 人工验证通过
```

---

## Files Likely to Change

| 操作 | 路径 | 目的 |
| --- | --- | --- |
| Modify | `src/fwasset/core/model_config.py` | `SharedModuleRef` + 共享段 load/save/remove；B0 `save_model_id` 改走 dict 合并 helper（`tomli-w` 序列化） |
| Modify | `pyproject.toml` | 新增无条件依赖 `tomli-w`（TOML 写） |
| Create | `src/fwasset/core/shared_module_resolver.py` | `resolve_shared_module`（命中/缺失一套路径） |
| Modify | `src/fwasset/ui/view_models/scheme_workbench_model.py` | `get_shared_modules` / `resolve_shared_module` API |
| Modify/Create | `src/fwasset/tests/test_model_config.py`（或 `test_shared_module_config.py`） | 共享段读写 / 保留 model_id / 原子失败 |
| Create | `src/fwasset/tests/test_shared_module_resolver.py` | 命中 / 缺失四因 / 防越界 / 不搜同名 |
| Modify | `src/fwasset/tests/test_scheme_workbench_model.py` | API / B4 隔离 / 回归 |
| Create | `docs/code-review/REVIEW-20260718-shared-module-schema.md` | 审查记录 |
| Modify | `docs/CHANGELOG.md` | 未发布变更 |
| Modify | `specs/archive/TASK-20260714-config-takeover.md` | B1 勾选、解锁 B2–B3 |
| Modify | 本文件 | 进度 |

预计不改：`platform_config.py` / `save_platform_config`、`scheme_config.py` 回源、`get_scheme_modules` / `get_scheme_module_tree`、`types.py`、数据库 schema、CTk/Qt 面板渲染、`D:\按摩器程序`。

---

## Definition of Done

- [x] `SharedModuleRef` 四字段（无 `mode`）；`load_shared_modules` 读回、缺字段条目按固定策略处理、容错不抛。
- [x] **统一 dict 合并写 helper（`tomli-w`）**：`save_model_id` / `save_shared_module` / `remove_shared_module` 三者共用；`save_model_id` 弃行级替换；合并 = 改现有完整 dict 的键、非重建。
- [x] `save_shared_module` / `remove_shared_module` **读-合并-写回**：保留 `model_id`、保留其它共享段与**未知 table**；同键幂等覆盖；删除只动 toml 不删固件文件；固定重打文件头注释；经 `atomic_write_text`（失败无半成品/`.tmp`）。
- [x] **B0 往返**：`save_model_id` ↔ `save_shared_module` 互不丢段；B0 既有测试全过。
- [x] `tomli-w` 加入 `pyproject.toml` `dependencies`（无条件）。
- [x] `resolve_shared_module` 一套路径：命中（`variants` 按叶子/模块目录判定产出、过滤噪声、排序、永不为空）；缺失四因（源未导入 / 路径无 / id 不符 / 越界）；**不**跨型号搜同名、**不**回落本地副本、**不**递归引用链。
- [x] `source_relative_path` 相对工作区根；路径首段 id 校验；`..` 越界拒绝。
- [x] view model `get_shared_modules` / `resolve_shared_module` 可用；型号根枚举不落 `通用/`。
- [x] **B4 隔离**：`get_scheme_modules` / `get_scheme_module_tree` 不含共享行；回源代码未被改。
- [x] **无 `mode`**；共享引用**只**存 `型号配置.toml`，**不**进 SQLite 索引 / 不改 `types.py` / schema。
- [x] 不写 `平台配置.toml`；设默认后共享段与 `model_id` 保留。
- [x] `pytest -m "not ui"` 通过且 coverage ≥ 80%；未自动启动 UI；未破坏性写入 `D:\按摩器程序`。
- [x] CHANGELOG、审查文档、父任务 B1 状态同步。
- [x] 人验通过后按模板提交；B2–B3 才解除阻塞。（实现提交：`4c8b6db` + 修复 `fafd65a`）

## Risks and Trade-offs

1. **合并 = 改现有完整 dict 的键，不是重建 dict**（用户确认的 dict 写回策略的核心防坑）：`save_model_id` / `save_shared_module` 都必须写「读到的整个 dict 局部改一键」，**禁止**只输出自己认识的字段——否则重演父任务警告的 `save_platform_config` 整写删段坑。Task 2 测试 6/8/10 强制守住。
2. **B0 与共享写两套并存会打架**：故本 TASK 把 `save_model_id` 从行级替换**一并切**到 dict 合并 helper（用户确认）。切换后 B0 既有测试全过是硬性回归门。
3. **`tomli-w` 序列化带引号中文 table 头**：`[shared_modules."快捷键程序"]` 交给库,不手拼；文件头注释非用户数据、序列化时固定前置。新增无条件依赖（`tomli-w` 无 stdlib 等价）。
4. **命中/缺失一套解析器**：父任务 B1 反复强调「源已导入」与「源未导入」共用同一解析路径，后者走缺失分支——**禁止**写第二套解析代码或在缺失时降级去搜同名。
5. **B4 隔离**：解析器 / 共享读写**绝不**被回源调用；Task 4 测试 4 断言方案树不含共享行。旧句「回源 = 本型号 + 显式共享」已作废。
6. **id 校验方向**：解析要用「路径首段型号根的实际 `model_id`」与 `ref.source_model_id` 比对；**禁止**用文件名解析的资产 `model` 字段冒充 id。
7. **variants 叶子判定 = 过滤后直接子目录为空**（用户确认）：不依赖 catalog 名匹配；过滤噪声目录 + 排序；永不为空。避免把变体目录再往下展一层。
8. **不做过度**：不接 B2 登记 UI、不画 B3 界面、不引入 `mode`、不进索引——全部留后续 phase。

## Open Questions

无。以下原「二选一」已由用户确认（2026-07-18）写死，实施不得另选：

1. **写回策略** → **dict 读-合并-自写序列化**（`tomli-w`）；`model_id` + 全部 `shared_modules` + 未知 table 往返不丢；注释丢失可接受但文件头注释固定重打；**B0 `save_model_id` 一并改为同一套 helper**。
2. **`variants` 语义** → 直指变体目录（叶子）`variants=[该目录]`；模块目录有子目录 → 直接子目录列表（过滤 + 排序）；模块目录无子目录 → `[模块目录]`；**永不为空**，叶子判定 = 过滤后直接子目录为空。

其余（落盘文件、无 mode、路径基准、id 校验、命中/缺失分支、B4 隔离、本地副本保留/无损取消、人验边界）均已由父任务写死。
