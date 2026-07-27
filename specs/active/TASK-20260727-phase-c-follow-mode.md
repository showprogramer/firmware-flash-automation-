# TASK-20260727：Phase C — 自动更新 / 固定版本模式

## 状态

| 项 | 状态 |
| --- | --- |
| 类型 | Phase C 设计 + 分解（xhigh 主线；子 TASK 立项前置） |
| 当前状态 | 📐 设计完成，待逐 子TASK 开工 |
| 前置 | Phase B（B0–B6）已全部人验通过并提交 |
| 父任务 | `specs/active/TASK-20260714-config-takeover.md`（Phase C 节） |
| 分支 | `feature/pyside6-migration`（或从此处切子分支） |
| 验收界面 | Qt-only |

> **xhigh 约束**：本 TASK 含 schema 扩展 + 解析器逻辑 + service 入口 + UI 全层改动，
> 必须先按下方子 TASK 拆分后方可开工各子 TASK。

---

## 背景与动机

Phase B 的共享引用是**静态指针**：`source_relative_path` 写死某个变体目录。
工厂程序文件迭代频繁时，烧录员每次更新源型号默认变体后，
目标型号侧的引用仍指向旧目录——要么烧错版，要么逐条重新手动登记。

Phase C 引入 `mode` 字段，让共享引用可以**动态跟随源型号模块默认**，
零额外操作即可跟上版本迭代。

---

## 设计决策

### D1：mode 字段（二值）

| mode | 烧录员视角 | `source_relative_path` 指向 | 解析行为 |
|---|---|---|---|
| `"static"` | **固定版本** | 变体目录（Phase B 现有行为；或模块目录，解析器对两层透明） | 直接返回路径 + variants |
| `"follow_default"` | **自动更新** | 模块目录（e.g. `L50S程序/通用/手控UI`；注册时由 C2 service 从 asset.path 派生） | 读源型号 `平台配置.toml` → 找默认变体 → 返回 `module_dir/variant_name` |

**向后兼容**：Phase B 写入的 toml 无 `mode` 键 → 读取时视为 `"static"`（固定版本），行为完全不变。
存量 `mode = "pinned"` → 容错回退为 `"static"`。

---

### D2：platform 映射方案（选 A：per-ref 显式）

**拒绝的方案**：全局 `[platform_mapping]` 表（DRY 但增加跨文件依赖，且平台对应关系本来就因模块而异）。

**采用**：每条 `follow_default` 引用带可选 `source_platform` 字段：

```toml
# 型号配置.toml 示例（L36双机芯）
[shared_modules.手控UI]
source_model_id     = "l50s-l66s"
source_group        = "l50s-l66s"
source_module       = "手控UI"
source_relative_path = "L50S-L66S程序/通用/手控UI"
mode                = "follow_default"
source_platform     = "标准单机芯"        # 可选；空时自动检测

[shared_modules.主板程序]
source_model_id     = "l50s-l66s"
source_group        = "l50s-l66s"
source_module       = "主板程序"
source_relative_path = "L50S-L66S程序/通用/主板程序"
mode                = "follow_default"
# source_platform 未填 → 自动检测
```

**`source_platform` 为空时的自动检测规则**（按优先级）：
1. 找源 `平台配置.toml` 中 `defaults` 包含 `source_module` 的第一个 platform 块；
2. 若无则取第一个 platform 块；
3. 若 `平台配置.toml` 不存在或空 → `missing`，reason = `no_source_platform`。

---

### D3：`follow_default` 解析流程

```
resolve_shared_module(ref, mode="follow_default"):
  1. abs_module_dir = workspace / source_relative_path
     （注册时 C2 已保证此处存模块目录，非变体目录）
  2. source_dir     = workspace / first_path_segment     （源型号根）
  3. 校验 model_id（同 Phase B）
  4. 校验 abs_module_dir ∈ source_dir（双保险）
  5. 加载源型号 平台配置.toml
  6. 确定 platform 块（source_platform 显式 or 自动检测）
  7. if source_module not in platform_block.defaults:
         → missing, reason = "no_source_default"
     elif platform_block.defaults[source_module] == "":
         → 唯一变体：resolved_path = abs_module_dir
     else:
         variant_name = platform_block.defaults[source_module]
         resolved_path = abs_module_dir / variant_name
  8. resolved_path.exists() 校验
  9. 返回 hit（resolved_path, variants=[resolved_path]）或 missing
```

**新增 missing reason**：
- `no_source_platform`：源无 `平台配置.toml` 或无可用 platform 块
- `no_source_default`：platform 块存在但 `defaults` 无该模块键且自动检测失败

---

### D4：schema 字段增量（不破坏 Phase B）

`SharedModuleRef` 新增两个可选字段：

```python
mode: Literal["static", "follow_default"] = "static"
source_platform: str = ""  # 仅 follow_default 有效
```

`_SHARED_FIELDS`（当前4 个必填）保持不变；`mode`/`source_platform` 作为**可选字段**单独读写：
- 读：缺失 → 默认值（`"static"` / `""`）；存在但无效值（含存量 `"pinned"`）→ fallback `"static"` + 警告
- 写：`mode == "static"` 时**不写入**该键（保持 Phase B toml 格式兼容）；`source_platform` 为空时不写入

---

## 子 TASK 分解

### Task C0：SharedModuleRef schema 扩展与兼容读写  `complexity: medium`

**复杂度理由：** 单文件 `model_config.py` 数据层改动；无 UI、无 schema 迁移（加可选字段）；测试约8 条（向后兼容 + round-trip）。

**Files:**
- Modify `src/fwasset/core/model_config.py` ✅ (`f8e196a`)
- Create `src/fwasset/tests/test_model_config_phase_c.py` ✅

**验收：** 已通过，8 passed。

---

### Task C1：`follow_default` 解析器  `complexity: high`

**复杂度理由：** 改 `shared_module_resolver.py` 核心解析路径；新增 `load_platform_config` 调用链；新 missing reason；需要8-10 条边界测试（命中/空defaults/无platform块/source_platform显式/自动检测/id_mismatch 不受影响）。

**Files:**
- Modify `src/fwasset/core/shared_module_resolver.py` ✅ (`cc3fc40`)
- Create `src/fwasset/tests/test_shared_module_resolver_phase_c.py` ✅

**验收：** 已通过，11 passed。

---

### Task C2：service 层入口扩展  `complexity: medium`

**复杂度理由：** `set_shared_module` 增加 `mode`/`source_platform` 参数；含 `source_platform` 存在性校验（需读源平台配置）；无 UI、无 schema；测试约8 条。

**Files:**
- Modify `src/fwasset/core/services/shared_module_service.py` ✅ (`0229b9e`)
- Create `src/fwasset/tests/test_shared_module_service_phase_c.py` ✅

**验收：** 已通过，8 passed。

---

### Task C3：Qt UI 模式选择与展示  `complexity: high`

**复杂度理由：** 改登记对话框（新增 mode 选择 + source_platform 下拉）；改列表展示文案（`"自动更新"` / `"固定版本"`）；需 Qt 人验。

**Files:**
- Modify `src/fwasset/ui_qt/workbench_window.py`（或对话框文件）
- Modify `src/fwasset/ui_common/view_models/scheme_workbench_model.py`（展示文案逻辑）
- 必要时扩 `src/fwasset/tests/test_qt_smoke.py`

**验收（Qt 人工验证）：**
- 登记对话框有 mode 选择（默认 `static` = 固定版本）
- 选 `follow_default`（自动更新）后出现 source_platform 下拉（从源型号 `平台配置.toml` 动态读取）
- 模块列表显示对应文案：`同 L50S`（自动更新）/ `来自 L50S`（固定版本）
- 缺失态（`no_source_default` 等）展示「共享来源缺失」，不静默降级

---

## Definition of Done（整体 Phase C）

- [ ] C0 测试通过；Phase B toml 向后兼容无退化
- [ ] C1 解析器：`follow_default` 边界测试全绿；Phase B 基线不破
- [ ] C2 service 入口：模式参数测试全绿
- [ ] C3 Qt 人工验证通过并记录日期
- [ ] `.\scripts\test.ps1` coverage ≥ 80%（预期维持 93%+）
- [ ] CHANGELOG、REVIEW（如涉及 types/service 契约变更）、本 TASK 收口
- [ ] 父任务 `TASK-20260714-config-takeover.md` Phase C 勾选

---

## 相关文档

- 父任务：`specs/active/TASK-20260714-config-takeover.md`（Phase C 节）
- Phase B 共享登记：`specs/active/TASK-20260720-shared-module-registration.md`
- 解析器：`src/fwasset/core/shared_module_resolver.py`
- 数据层：`src/fwasset/core/model_config.py`
- 平台配置服务：`src/fwasset/core/services/platform_default_service.py`
