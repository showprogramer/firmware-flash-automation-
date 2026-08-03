# TASK-20260803-r5-path-guard：统一工作区路径守卫

## 状态

| 项 | 状态 |
| --- | --- |
| 类型 | core 公共 API + 服务契约（安全边界） |
| 当前状态 | 🔄 实现完成，待 Windows 人工验证 |
| 前置 | REVIEW-20260728 R5（P1·阻断） |
| 父任务 | CRUD 前置（REVIEW-20260728-pre-crud-readiness） |
| 分支 | `feature/pyside6-migration` |
| 完成 commit | 待提交 |

---

## 目标

实现 R5：抽出统一的工作区路径守卫 `assert_within_workspace`，让所有写入口（现有 TOML 写入口 + 未来 CRUD）共用同一份"目标路径必须在工作区内"的校验，消除 `shared_module_service._resolve_relative` 与 `shared_module_resolver._is_under_workspace` 两处行为不一致的局部守卫。

## 关键决策

- 新建 `core/path_guard.py`，契约：`assert_within_workspace(path, workspace_root) -> Path`，失败抛 `PathGuardError`。
- 守卫最低契约（按 REVIEW R5）：空配置根先拒绝 → resolve 前显式拒绝 `..` → resolve 后确认落点在工作区内（允许相等，单型号根场景 model_root == workspace_root）→ Windows 比较统一 `normcase`，分隔符统一正斜杠。
- 服务层写入口 `workspace_root` 改为**必选参数**（强制接入，不允许"忘传就跳过"）；`set_shared_module` 已存在该参数。
- 读取端 `shared_module_resolver._is_under_workspace` 委托守卫实现，保持行为等价（词法双保险保留）。
- `_resolve_relative` 内部复用守卫，对外行为不变（扫描资产路径不含 `..`，等价）。

## 文件变更

### Task 1：`core/path_guard.py` 实现守卫  `complexity: low`

**复杂度理由：** 单文件纯函数 + 独立错误类型，无外部依赖，不涉及服务/UI 行为。

**Files:** 新建 `src/fwasset/core/path_guard.py`、`src/fwasset/tests/test_path_guard.py`

- `PathGuardError(ValueError)`：守卫拒绝时抛出，message 为中文用户可见文案。
- `assert_within_workspace(path, workspace_root) -> Path`：
  - workspace_root 为空 → 拒绝「工作区根目录未配置」；
  - resolve 前对原始 `parts` 拒绝 `..`（不拒绝 `.`，无害且 `Path` 构造会折叠）；
  - `Path.resolve()` 后，normcase + as_posix 统一后确认 `candidate == root` 或 `candidate` 在 `root` 之下；
  - 返回 resolve 后的 Path。

测试用例：空根拒绝；区域内放行（含相等）；区域内 `..` 拒绝；真越界拒绝；`. ` 放行；大小写/分隔符差异（仅 Windows 语义，Linux 上验证行为不回归）。

### Task 2：服务层写入口接入守卫  `complexity: medium`

**复杂度理由：** 4 个 service 函数签名变化（新增必选 `workspace_root`）+ 调用方（view model、测试）同步，涉及服务契约但无 UI 控件与 schema 变化。

**Files:** `src/fwasset/core/services/shared_module_service.py`、`src/fwasset/core/services/platform_default_service.py`、`src/fwasset/core/shared_module_resolver.py`

- `shared_module_service.set_shared_module`：`target_root` 写入前过守卫（新增）；`_resolve_relative` 复用守卫。
- `shared_module_service.clear_shared_module`：新增必选 `workspace_root`，`target_root` 过守卫。
- `platform_default_service.set_default_variant`：新增必选 `workspace_root`，`model_root` 过守卫。
- `platform_default_service.set_module_default_for_model`：新增必选 `workspace_root`，`model_root` 过守卫。
- `shared_module_resolver._is_under_workspace`：委托 `assert_within_workspace`（try/except 转 bool）。
- 守卫失败统一返回 `{"ok": False, "code": "out_of_workspace", ...}`，不以裸异常代替服务错误码。

### Task 3：view model 与测试同步  `complexity: medium`

**复杂度理由：** 调用方契约变化波及 ui_common 与 4 个既有测试文件，需同步参数并补守卫失败用例；无 UI 控件改动。

**Files:** `src/fwasset/ui_common/view_models/scheme_workbench_model.py`、`src/fwasset/tests/test_shared_module_service.py`、`src/fwasset/tests/test_shared_module_service_phase_c.py`、`src/fwasset/tests/test_platform_default_service.py`

- `unregister_shared_module` / `set_default_variant`（view model）：`root_dir` 为 None → `invalid_args`；否则传 `workspace_root=self.root_dir`。
- 既有测试补 `workspace_root` 参数；新增用例：目标根在工作区外 → `out_of_workspace`；`..` 路径 → `out_of_workspace`；model_root == workspace_root 放行。

## 非目标

- 不做 R1/R10（配置根权威 + UI 门闩），本任务只做路径守卫本身。
- 不修改 resolver 的读端词法检查（保留双保险）。
- 不引入 schema、数据库改动。
- 不提供 CRUD 写入口（后续任务）。

## 验收标准

- `assert_within_workspace` 通过全部越界/边界用例；既有测试全绿（`-m "not ui"`）。
- 所有写入口（登记/取消登记/设为默认）在目标根越界、根未配置、路径含 `..` 时返回 `out_of_workspace` 且不落盘。
- REVIEW-20260728 R5 状态更新为已完成。
- CHANGELOG Unreleased 记录本次改动。

---

## 验证记录

- 自动化验证（已完成）：
  - `pytest src/fwasset/tests/test_path_guard.py src/fwasset/tests/test_platform_default_service.py src/fwasset/tests/test_shared_module_service.py src/fwasset/tests/test_b4_shared_scheme_boundary.py src/fwasset/tests/test_scheme_workbench_model.py` → 通过
  - `pytest -m "not ui"`（WSL `.venv-wsl`）→ 362 passed, 1 skipped；7 个失败（test_panel_host_protocol ×4、test_settings ×2、test_file_scan ×1）经 git stash 基线复测确认是 Linux 环境差异（PySide6 未装 / Windows 路径语义），与本次改动无关
  - Windows 规范化回归用例 `_fake_win_normcase`（模拟 Windows C 版 normcase 把 `/` 转 `\`）已固化并通过
- 人工验证（已完成，Windows 实机）：
  - 首次实机登记共享被误拒，暴露 normcase 顺序回归：Windows `os.path.normcase` 会把 `/` 规范化为 `\`，初版先 `as_posix()` 再 normcase 导致前缀比较永不匹配（Linux no-op 掩盖）
  - 修复（先 normcase 再统一斜杠）后实机登记共享成功（`D:\按摩器程序\L36双机芯-上3D-下2D程序`）

## 文档与收口

- Review：REVIEW-20260728 R5 已关闭（✅ 已完成，含回归修复记录）。
- CHANGELOG：Unreleased 已新增条目（已完成，含回归说明）。
- 迁移说明：不适用（无路径/配置/运行时迁移）。

---

## Task DoD

- [x] `core/path_guard.py` 实现并通过越界/边界用例
- [x] 服务层写入口全部接入守卫并同步调用方
- [x] 自动化验证已记录（含 Windows normcase 回归用例）
- [x] 人工验证（Windows 实机）：登记共享成功；normcase 顺序回归已修复并固化
- [x] Review 已更新（REVIEW-20260728 R5 关闭）
- [x] CHANGELOG 已同步
