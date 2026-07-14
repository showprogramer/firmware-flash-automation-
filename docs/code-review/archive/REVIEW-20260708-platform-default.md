# REVIEW-20260708-platform-default

## 类型
新功能（设为平台默认）

## 模块
- `core/platform_config.py` — 新增 `save_platform_config()`（规范格式整体重写 `平台配置.toml`，含转义）
- `core/services/platform_default_service.py` — 新增服务 `set_default_variant()`，返回 ServiceResult（codes: `ok` / `invalid_args` / `write_failed`）
- `ui/view_models/scheme_workbench_model.py` — 新增 `platform_names()`、`default_platforms_for()`、`default_badge()`、`set_default_variant()`、`_common_module_parts()`、`_platform_config_root()`；`ModuleCardData` / `ModuleVariant` 新增 `default_badge` 字段
- `ui/panels/data_grid_panel.py` — 程序名称列渲染 ★默认 徽章；新增 `on_right_click` 回调（右键先选中行再上抛）
- `ui/workbench_panel.py` — 右键菜单：通用变体上提供「设为平台默认」（单平台直出、多平台子菜单、当前默认置灰打勾），另有打开目录/复制路径；确认框 → 服务调用 → 就地重载平台配置并刷新表格

## 问题描述
通用模块的默认变体此前靠手工编辑 `平台配置.toml` / 随意初始值。只有烧录员知道定制方案缺失模块应回源到哪个通用程序，且程序会随时间更换，需要应用内可操作的设默认入口。

## 处理方案
- 事实源唯一：默认 = `平台配置.toml` 的 `[platform.defaults]` 条目；目录名 `_默认` 后缀不再作为写入依据（仅遗留展示）。
- 写入位置按加载器同样的候选顺序找**现存配置文件所在目录**（规范位置是扫描根）。修复了开发中发现的坑：`model_directory_path` 可能指向 `通用/` 子目录，直接用 `_get_model_root` 会把配置写到错误位置且被扫描根旧文件按平台名去重压制。
- 模块键沿用 toml 既有键（`_module_matches`，容忍 版/板 用字差异），避免同一模块产生重复 defaults 条目。
- 资产目录直接位于模块层（模块唯一一份）时变体写空串，与既有回源语义一致。
- 设默认成功后就地 `_load_platforms_for_all_models()`，回源与徽章立即生效，**不需要重新扫描**（默认不入库）。
- UI 语言约束遵守：无"回源"字样；徽章文案 `★默认`（多平台附平台名）。

## 追加：多型号根支持（同日）

用户把型号目录归入父文件夹（`D:\按摩器程序\L36程序` + `L36双机芯-上3D-下2D程序`）后，扫描只显示一个假型号「按摩器」——旧逻辑假设扫描根即单个型号目录。同批改动（均在 `scheme_workbench_model.py`）：

- `_detect_single_model_root()`：扫描根直接含 通用/定制 → 单型号根（原行为）；否则视为多型号父文件夹。根目录不存在时保持单型号语义（兼容纯索引测试）。
- `_load_multi_model_dirs()`：多型号根按资产路径一级子目录枚举型号（`L36程序`→`L36`），未整理的型号目录也会出现在型号列表。
- `_belongs_to_model` / `_get_model_root` / `load_all_models` / `_platform_config_root` 增加多型号分支；归属只看物理路径，不看文件名解析出的 model（避免 L50S 噪声跨型号误判）。
- 平台配置按型号隔离：`_platforms_by_model` + `_platforms_for(model)`；徽章、回源、右键平台菜单、设默认写入位置全部按型号取平台，避免同名平台/模块跨型号串扰。`self._platforms` 保留为合并列表供无型号上下文的旧调用。
- `platform_names(model_name)` 增加型号参数；资产退化路径也按型号过滤。

真实数据验证（`D:\按摩器程序`，临时索引）：70 资产、型号 `['L36', 'L36双机芯-上3D-下2D']`、L36 侧边树 7 通用模块 + 6 方案、双机芯 2 资产仅见于「全部」视图、无跨型号泄漏。

## 状态
已实现，待人工验证（未 commit）

## 验证记录
- `uv run python -m pytest src/fwasset/tests/test_platform_config.py src/fwasset/tests/test_platform_default_service.py src/fwasset/tests/test_scheme_workbench_model.py -q --no-cov` → 41 passed
- `uv run python -m pytest -m "not ui" -q` → 211 passed, coverage 85.86%（≥80% 门槛）
- 完整套件结果见任务对话记录

## 相关Commit
（人工验证通过后填写）
