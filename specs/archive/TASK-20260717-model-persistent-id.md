# TASK-20260717: 型号持久 id（Phase B0）

> **For Hermes:** 实施时使用 `test-driven-development`，逐项 RED → GREEN → REFACTOR；本 TASK 动 core 与工作台 view model，**必须人工验证通过后才能 commit**。

## 状态

| 项 | 状态 |
| --- | --- |
| 类型 | 父任务 Phase B0（B1 前置） |
| 当前状态 | ✅ 人验通过并提交 |
| 父任务 | `specs/archive/TASK-20260714-config-takeover.md`（B0 专节为契约源） |
| 分支 | 继续当前分支或按父任务约定切 `feature/config-takeover`（实施前定） |
| 前置（代码） | `TASK-20260716`（严格读 + `atomic_write_text`）已提交（`72d1cca`） |
| 后续 | 本 TASK 人验并提交后，才开始 B1（引用 schema + 解析器） |

## Goal

给每个型号根落一个**持久稳定 id**（`model_id`），写入型号根下软件托管的 `型号配置.toml`；扫描/bind 后在内存建立 `model_id ↔ dir_name ↔ display_name` 映射并提供三个查询 API。目录改名后 id 不变；同工作区 id 唯一。**只做 B0 落盘 + 映射 + API**，不实现 `shared_modules` / 解析器 / 任何 UI 选型键改造。

## Architecture

新增 `core/model_config.py`：独立的 `型号配置.toml` load/save（读-合并-写回，复用 `config_io.atomic_write_text`），**绝不**调用 `save_platform_config`（后者整体重写 `平台配置.toml`）。新增 `core/services/model_id_service.py`：`ensure_model_ids(workspace_roots)` 先读全量已有 id 再为无 id 者 slug 生成。`SchemeWorkbenchModel` 在 `bind()` 内调用服务，新增 id 映射层与三个 API，保留现有 `_multi_model_dirs` 不推翻。

## Tech Stack

Python 3.8+、`pathlib`、TOML（`tomllib` / `tomli`）、`core.config_io.atomic_write_text`、pytest。

---

## 契约来源（父任务 B0 专节，已写死）

本 TASK 不重述、不修改父任务 B0 语义；以下为执行必须遵守的要点复述：

1. **三名分离**：`model_id`（落盘、稳定主键）/ `display_name`（不落盘、永远 `_strip_model_suffix(dir_name)` 现推）/ `dir_name`（目录名、可变）。
2. **落盘文件 = 型号根/`型号配置.toml`**；B0 仅写 `model_id` 顶层键；**禁止**写进 `通用/`；**禁止**与 `平台配置.toml` 混写。
3. **先读全量、再生成**：先遍历所有型号根读出已有合法 `model_id` 记占用集合，再仅对无 id 者 slug；碰撞加 `-2/-3…`。
4. **已有合法 id → 只读，永不按目录重算覆盖**；`-2` 一旦写入永久稳定，不因碰撞方移走而"升回"。
5. **资产字段 `model`（文件名解析）绝不能当 `model_id`**。
6. 写盘用 `atomic_write_text`；写失败 → 服务结果失败，不静默用展示名冒充 id。

## 不可变约束

1. 不实现 `shared_modules`、引用解析器、`.ref` 迁移、Phase B1+ 任何内容。
2. 不改 `平台配置.toml` 的格式或读写；不改 `save_platform_config`。
3. 不修改 `types.py`，不改 `ServiceResult` 四键结构（服务返回仍 `{ok,code,message,payload}`）。
4. UI 继续以现推 `display_name` 选型号；**不**把 UI 选型键改成 id。
5. 用户可见消息中文；不要求手写 TOML。
6. 不自动启动 UI、不自动跑 `@pytest.mark.ui`。
7. 不对 `D:\按摩器程序` 做破坏性写入；失败注入只在 pytest 临时目录。
8. 单型号根（扫描根自身含 `通用/定制`）与多型号父根两种布局都要支持（对齐 `_detect_single_model_root`）。

---

## 决策：`model_id` 生成与文件格式

### slug 规则（`slugify_model_id(dir_name) -> str`，纯函数）

1. 取 `dir_name`，去尾缀 `程序` / `目录`（对齐 `_strip_model_suffix`）。
2. ASCII 字母数字段转小写；中文保留；空白压成单个 `-`；去掉路径危险字符（`/ \ : * ? " < > |` 及控制字符）。
3. 首尾 `-` 去除；结果为空串时回退 `"model"`（异常兜底，打日志）。
4. 例：`L50程序` → `l50`；`L36程序` → `l36`；`L36双机芯-上3D-下2D程序` → `l36双机芯-上3d-下2d`。
5. **纯函数不做碰撞处理**；碰撞由服务层按占用集合加后缀。

### `型号配置.toml` 格式（B0 仅此一键）

```toml
# 本文件由 fwasset 管理（型号 id + 未来共享引用）。用户无需手写。
# display_name 不落盘（永远由目录名现推）。
model_id = "l36双机芯-上3d-下2d"
```

- `load_model_config(model_root) -> tuple[str, ModelConfigStatus, str]` 返回 `(model_id, status, error)`；
  status ∈ `"ok"`（有合法 model_id）/ `"missing"`（文件不存在）/ `"no_id"`（文件在但无/空 model_id）/ `"parse_error"` / `"parser_missing"`。
- `save_model_id(model_root, model_id)`：**读-合并-写回**——读现有文件全部内容（未来的 `shared_modules` 段必须原样保留），只覆盖/新增 `model_id` 顶层键，`atomic_write_text` 落盘。B0 阶段文件只有 `model_id`，但 save 实现**必须**保留未知键，为 B1 复用打底。
- 落盘目录严格为传入 `model_root`；调用方（服务/view model）负责保证它是型号根而非 `通用/`。

### 服务层错误码（`model_id_service`）

`ensure_model_ids(workspace_roots, log_fn=print) -> dict`（`ServiceResult` 形状）：

| code | 条件 |
| --- | --- |
| `ok` | 全部型号根已有或成功生成 id |
| `parse_error` | 某 `型号配置.toml` 损坏（`parse_error`/`parser_missing`）→ 停止对该根写入，不覆盖 |
| `write_failed` | `atomic_write_text` / `os.replace` 失败 |

payload 至少含 `{"assigned": {dir_name: model_id}, "existing": {dir_name: model_id}}`。损坏根跳过写入并在 payload 标注，不因单根损坏而中断其余根（除非你判断更适合整体失败——**默认策略：损坏根跳过、其余继续、整体 code 视是否有损坏而定**；测试固定此行为）。

---

## 实施计划（TDD）

### Task 1：slug 纯函数

**Files:** Create `src/fwasset/tests/test_model_config.py`；Create later `src/fwasset/core/model_config.py`

**RED** — 测试 `slugify_model_id`：
1. `L50程序` → `l50`；`L36程序` → `l36`；
2. `L36双机芯-上3D-下2D程序` → `l36双机芯-上3d-下2d`；
3. 尾缀 `目录` 去除；无尾缀原样；
4. 含路径危险字符被清除；多空白压成单 `-`；首尾 `-` 去除；
5. 全部被清空 → `"model"` 兜底。

**验证 RED:** `uv run python -m pytest src/fwasset/tests/test_model_config.py -q --no-cov` → FAIL（模块/函数不存在）。

**GREEN:** 实现 `slugify_model_id`。

---

### Task 2：`型号配置.toml` load/save（保留未知键）

**Files:** Modify `test_model_config.py`；Modify `src/fwasset/core/model_config.py`

**RED** — 至少覆盖：
1. 文件不存在 → `("", "missing", "")`；
2. 合法 `model_id = "l36"` → `("l36", "ok", "")`；
3. 文件存在但无 `model_id` / 空串 → `("", "no_id", "")`；
4. 语法错误 → `parse_error`；monkeypatch `tomllib=None` → `parser_missing`；
5. `save_model_id` 新建文件后可被 `load_model_config` 读回同值；
6. **保留未知键**：预置文件含 `model_id` + 一段 `[shared_modules."x"]`（手工写入模拟未来数据），`save_model_id` 改 id 后，重新读原文件文本，`[shared_modules."x"]` 段仍在；
7. `save_model_id` 经 `atomic_write_text`：monkeypatch `config_io.os.replace` 抛错 → 原文件字节不变、无 `.tmp` 残留；
8. 中文型号根目录可写。

**验证 RED / GREEN:** 同上命令。GREEN 实现 load/save，save 用 `atomic_write_text` 且读-合并-写回保留未知顶层键与表。

> 实现提示：B0 不引入 tomlkit；"保留未知键"可用"读原始文本 → 若已有 `model_id` 行则替换该行，否则在首个非注释位置插入"策略，或读 TOML 成 dict 后自写序列化并把未识别 table 原样透传。二选一，但测试 6 必须过。

---

### Task 3：`ensure_model_ids` 服务（先读全量、再生成、碰撞后缀）

**Files:** Create `src/fwasset/tests/test_model_id_service.py`；Create `src/fwasset/core/services/model_id_service.py`

**RED** — 用临时工作区（若干型号根目录）覆盖：
1. 两个无 id 型号根（`L36程序`、`L50程序`）→ 生成 `l36`、`l50`，各自 `型号配置.toml` 落盘；
2. **二次调用 id 不变**（第二次 `ensure_model_ids` 不重算、不改文件 mtime 语义——断言值不变即可）；
3. **改名不变**：先生成 `l36`，把目录连同 `型号配置.toml` 改名为 `L36改名程序`，再 `ensure_model_ids` → 该根 id 仍 `l36`（读盘得来，不按新目录重算）；
4. **碰撞**：两个不同目录 slug 同为 `l36`（如 `L36程序`、`L36`）→ 一个 `l36`、一个 `l36-2`；且**先读全量已有 id**：预置其一已写死 `l36`，另一新根必须拿 `l36-2`，不得把已写死那个改成 `-2`；
5. **碰撞稳定**：`l36-2` 写入后，即使 `l36` 那个根被移走再扫，`l36-2` 不"升回" `l36`；
6. **损坏根跳过**：一个根 `型号配置.toml` 损坏 → 该根不被覆盖、payload 标注，其余根正常生成；整体 code 反映有损坏（固定为 `parse_error`）；
7. `atomic_write_text` 失败 → `write_failed`，已处理的根不回滚但未处理根不产生半成品（说明清楚——本服务逐根写，失败即停并返回，已成功的根保留）。

**验证 RED / GREEN:** `uv run python -m pytest src/fwasset/tests/test_model_id_service.py -q --no-cov`。

> 实现要点：`ensure_model_ids` 必须**两遍**：第一遍对所有根 `load_model_config` 收集 `status=="ok"` 的 id 入 `occupied`；第二遍仅对 `missing`/`no_id` 的根 slug + 去 `occupied` 碰撞 + `save_model_id` + 把新 id 加入 `occupied`。禁止边读边写单遍。

---

### Task 4：view model 接入 id 映射 + 三 API

**Files:** Modify `src/fwasset/tests/test_scheme_workbench_model.py`；Modify `src/fwasset/ui/view_models/scheme_workbench_model.py`

**新增映射与 API（名称可微调，语义固定）：**
- `bind()` 内、`_load_multi_model_dirs()` 之后调用 `ensure_model_ids(<所有型号根>)`，再建内存映射 `self._model_id_by_dir: dict[dir_name, model_id]`。
- `ensure_model_id(model_root) -> str`：返回该根 id（缺则触发服务补写后返回）。
- `resolve_model_id(name) -> str | None`：入参可为 `display_name` 或 `dir_name`，返回 id 或 `None`。
- `model_root_for_id(model_id) -> Path | None`：反查型号根路径；工作区内无此 id → `None`（为 B6 缺失分支打底）。

**型号根枚举**：单型号根 → 扫描根自身；多型号父根 → `_multi_model_dirs` 的各 `root_dir/dir_name`。落盘目录纪律对齐 `_platform_config_root`（**不写 `通用/`**）。

**RED** — 覆盖：
1. 多型号父根 bind 后，`resolve_model_id("L36")`（display）与 `resolve_model_id("L36程序")`（dir）都得到同一 id；
2. `model_root_for_id(<已知id>)` 返回存在目录；未知 id → `None`；
3. bind 后各型号根出现 `型号配置.toml` 且含 `model_id`；**不**出现在 `通用/` 下；
4. 单型号根布局：扫描根自身拿到 id，`display_name` 现推正确；
5. **回归**：`load_all_models` / 侧栏 / 设默认 / A4-A5 现有测试全过（id 接入不改变既有行为）；
6. bind 到只读或损坏 `型号配置.toml` 的根：不抛未捕获异常，映射对该根缺失即可（不阻断其余型号加载）。

**验证:**
```bash
uv run python -m pytest \
  src/fwasset/tests/test_model_config.py \
  src/fwasset/tests/test_model_id_service.py \
  src/fwasset/tests/test_scheme_workbench_model.py \
  src/fwasset/tests/test_platform_default_service.py \
  src/fwasset/tests/test_workbench_panel_helpers.py \
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
- Create `docs/code-review/REVIEW-20260717-model-persistent-id.md`（类型：核心配置/新服务；问题：型号无稳定身份；处理：`型号配置.toml` + `ensure_model_ids`；新服务错误码；验证记录；人验状态；commit 后补哈希）
- Modify `docs/CHANGELOG.md`（Unreleased 增条目）
- Modify `specs/archive/TASK-20260714-config-takeover.md`（B0 checklist 勾选、注明 `TASK-20260717` 承载）
- Modify 本文件状态与 DoD

---

## 人工验证（必须在 commit 前）

完成代码与非 UI 自动化后，Agent 明确回复「已完成，请人工验证」并列出实际命令与结果。用户在**测试副本**上：

### 场景（逆序共用一个副本：先损坏 → 再改名 → 最后首次生成）

1. **损坏容错**：副本某型号根放损坏 `型号配置.toml`，启动软件切到该型号 → 不崩溃；该型号仍可浏览（id 映射缺失不阻断）；原损坏文件不被覆盖。
2. **改名不变**：把一个已有 `型号配置.toml`（含 `model_id`）的型号目录改名后重扫 → 该型号 id 不变（可在 `型号配置.toml` 内确认值未变）。
3. **首次生成**：对尚无 `型号配置.toml` 的型号根（如双机芯占位）切换/扫描 → 型号根下自动出现 `型号配置.toml` 且含 `model_id`；`通用/` 下无该文件；型号列表与设默认行为不回退。

### 现场只读确认

不修改 `D:\按摩器程序`；上述均在副本执行。

人工回复「验证通过」后：标记完成 → 更新审查文档 → 按 `docs/COMMIT_TEMPLATE.md` 提交 → 更新 CHANGELOG → 父任务 B0 勾选 → 解锁 B1。

**建议提交信息：**
```text
feat(core): 型号持久 id（Phase B0）

- 新增 型号配置.toml 独立 load/save（读-合并-写回，保留未知键）
- ensure_model_ids：先读全量已有 id 再 slug 生成，碰撞加后缀且稳定
- 工作台 bind 建立 model_id ↔ dir_name ↔ display_name 映射 + 三查询 API
- 目录改名 id 不变；同工作区 id 唯一；写盘复用 atomic_write_text

影响范围:
- core/model_config、core/services/model_id_service
- ui/view_models/scheme_workbench_model（id 映射，UI 选型键不变）

验证:
- 型号 id 纯数据层与服务测试通过
- 非 UI 测试与覆盖率门禁通过
- CTk / Qt 人工验证通过
```

---

## Files Likely to Change

| 操作 | 路径 | 目的 |
| --- | --- | --- |
| Create | `src/fwasset/core/model_config.py` | slug + `型号配置.toml` load/save |
| Create | `src/fwasset/core/services/model_id_service.py` | `ensure_model_ids`（先读后生成） |
| Create | `src/fwasset/tests/test_model_config.py` | slug / load-save / 保留未知键 / 原子失败 |
| Create | `src/fwasset/tests/test_model_id_service.py` | 生成 / 改名不变 / 碰撞 / 损坏跳过 |
| Modify | `src/fwasset/ui/view_models/scheme_workbench_model.py` | bind 接入 + id 映射 + 三 API |
| Modify | `src/fwasset/tests/test_scheme_workbench_model.py` | 映射 / API / 回归 |
| Create | `docs/code-review/REVIEW-20260717-model-persistent-id.md` | 审查记录 |
| Modify | `docs/CHANGELOG.md` | 未发布变更 |
| Modify | `specs/archive/TASK-20260714-config-takeover.md` | B0 勾选 |
| Modify | 本文件 | 进度 |

预计不改：`platform_config.py`、`save_platform_config`、`types.py`、数据库 schema、CTk/Qt 面板文件、`D:\按摩器程序`。

---

## Definition of Done

- [x] `slugify_model_id` 按规则产出，中文保留、ASCII 小写、危险字符清除、空串兜底。
- [x] `型号配置.toml` load/save 可用；save **保留未知键**（为 B1 打底）；经 `atomic_write_text`。
- [x] `ensure_model_ids` **先读全量已有 id 再生成**；碰撞 `-2/-3`；改名不变；碰撞后 id 稳定。
- [x] 损坏 `型号配置.toml` 不被覆盖；写失败返回 `write_failed`，无半成品/`.tmp` 残留。
- [x] view model 三 API（`ensure_model_id` / `resolve_model_id` / `model_root_for_id`）可用；display 与 dir 都能解析到同一 id。
- [x] `model_id` 不写入 `通用/`；不写入 `平台配置.toml`。
- [x] UI 选型键仍用 `display_name`；`load_all_models` / 设默认 / A4-A5 行为不回退。
- [x] 资产字段 `model` 未被当作 id。
- [x] `pytest -m "not ui"` 通过且 coverage ≥ 80%；未自动启动 UI。
- [x] 未对 `D:\按摩器程序` 做破坏性写入。
- [x] CHANGELOG、审查文档、父任务 B0 状态同步。
- [x] 人验通过后按模板提交；B1 才解除阻塞。（实现提交：`1c287b8`）

## Risks and Trade-offs

1. **"保留未知键"实现**：B0 文件只有 `model_id`，但 save 必须为 B1 的 `shared_modules` 段保命；若图省事整体重写只输出 `model_id`，B1 写引用后一设 id 就丢共享段——与 `平台配置.toml` 当年同类坑。测试 6 强制守住。
2. **两遍扫描的顺序**：单遍边读边写会让后处理根拿错碰撞后缀或覆盖已写死 id。服务实现必须"先读全量 occupied，再生成"。
3. **落盘目录纪律**：scanner 的 `model_directory_path` 可能指向 `通用/`；枚举型号根用 `_multi_model_dirs`/扫描根，不用可能落到 `通用/` 的路径。
4. **id 映射缺失不得阻断**：损坏/只读根只影响该型号的 id 能力，不能让整个工作台加载失败。
5. **不做过度**：不建工作区全局 id 中心、不改 UI 主键、不碰 `shared_modules` 业务——全部留 B1+。

## Open Questions

无。slug 规则、文件格式、服务错误码与两遍生成顺序、落盘纪律、人验边界均已写死；实施前如需改动，先改本 TASK 并经用户确认。
