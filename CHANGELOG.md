# 记录变更

## Unreleased

### docs
- 新增 `COMMIT_TEMPLATE.md`，提供中文 commit message 标准模板、`type` 对照与项目示例。

### app
- 调整 Excel 写入调用逻辑：从布尔返回值改为读取结构化结果。
- 根据写入结果区分提示：`locked` 显示“占用并给出备用文件路径”，其他失败显示具体错误信息。

### core
- `core/excel_ops.py`：
  - `write_excel_record` 返回结构改为 `ok / reason / tmp_path / error`。
  - 增加文件不存在场景处理；Excel 被占用时写入 `*_刷机记录_待导入.xlsx` 并返回 `reason=locked`。
- `core/settings.py`：
  - 新增 `config.toml` 加载能力（优先 `tomllib`，回退可选 `tomli`）。
  - 增加默认配置回退与类型兜底（路径、Excel Sheet/Header、USB 清理规则）。
  - 支持相对 `excel_path` 按项目根目录解析为绝对路径。

### data
- 更新 `data/handcontrol_ui_template.xlsx` 模板内容（二进制文件变更）。

### config
- 新增 `config.toml`，用于集中配置扫描目录、Excel 参数和 USB 清理规则。

### 接口变更
- `core.excel_ops.write_excel_record` 的返回类型由 `bool` 变为结果字典；调用方需按键读取状态，不再只判断真/假。

## 2026-03-20

### fbe220d
- `refactor: split ui app and core modules with compatible launcher`
- 将 UI 与 `core` 能力模块拆分，保留兼容入口，形成更清晰的分层结构。

### 789b8e6
- `chore: initialize repo, uv setup, sanitize template, and module1 cleanup`
- 完成仓库初始化与基础工程落地（含模板文件、项目配置与初始脚手架整理）。
