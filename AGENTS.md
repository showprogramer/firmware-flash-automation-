# Repository Guidelines

这是一个 Python 固件资产管理桌面应用。详细产品概览见 [README.md](README.md)，架构事实见 [docs/architecture.md](docs/architecture.md)，Agent 流程见 [docs/agent-workflow.md](docs/agent-workflow.md)。

## 项目结构

- `src/fwasset/core/`：扫描、索引、配置、领域类型和服务。
- `src/fwasset/ui_common/`：框架无关的 ViewModel 与辅助逻辑。
- `src/fwasset/ui_qt/`：PySide6 + QFluentWidgets 界面。
- `src/fwasset/tests/`：pytest 测试。
- `specs/active/`：当前任务；`specs/archive/`：已完成任务；`specs/design/`：设计规格和草图。
- `docs/`：架构、Agent 流程、UI 参考、Review、迁移说明和变更记录。

## 常用验证命令

```powershell
uv sync --extra dev
uv run fwasset
uv run python -m pytest -q
uv run python -m pytest -m "not ui" -q
.\scripts\test.ps1
```

**环境约束：** 本项目纯 Windows 开发、Windows 使用，所有验证只在 Windows `.venv` 下执行（`uv run`），不再使用 WSL / `.venv-wsl`。

`.venv` 损坏（如 psutil `ImportError: _common`）时：`uv pip install --reinstall psutil` 或删除 `site-packages/psutil*` 后 `uv sync --extra dev`。

覆盖率门槛为 `src/fwasset` 80%；`app.py` 和 `ui_qt/*` 不计入覆盖率，`ui_common/*` 计入覆盖率。

质量检查命令：

```powershell
uv run ruff check src scripts
uv run mypy
.\scripts\quality.ps1          # ruff + format + mypy 合集
```

mypy 范围：`src/fwasset/core`、`src/fwasset/ui_common`、`scripts`（排除 `spike_pyside6.py`）；`ui_qt/*` 和测试代码暂不纳入。ruff 检查 `src` 与 `scripts` 全部文件。改动后须同时跑通 ruff、mypy 和 pytest。

## 必须遵守的代码约束

- 新源文件使用 `from __future__ import annotations`；新 helper 和公共方法补充类型标注。
- 导入顺序为标准库、第三方库、`fwasset.*`。
- `core/types.py` 是 TypedDict 和 Literal 的类型真源；改动字段必须同步生产者、消费者和测试。
- 服务位于 `core/services/`，返回 `ServiceResult`，用户可见消息使用中文，不以裸异常代替服务错误码。
- `firmware_catalog.toml` 的条目顺序影响匹配；`handcontrol_ui` 必须同时有 `.rom` 和 `.pkg`。
- `asset_index.py` 采用单工作区语义；整理后的目录树和 TOML 是真源，SQLite 是搜索缓存。
- UI 只使用 Qt 方案；操作面板遵循 registry + `PanelHost`，ViewModel 采用组合，耗时任务使用后台线程和结果队列。
- UI 任务取消使用 `threading.Event`；不得新增第二套 UI 框架。
- 详细服务、数据库、固件目录和 UI 约束见 [architecture.md](docs/architecture.md)。

## 文档与本地文件

- 项目概览：`README.md`。
- 当前任务：`specs/active/`。任务文件只写当前规格（目标、规则、验收、DoD、最新验证）；需求变化时改原文，不追加修订流水账。详见 [agent-workflow.md](docs/agent-workflow.md)。
- 长期架构决策仅在有实际决策时创建 `specs/decisions/`。
- UI 运行截图：`docs/ui-reference/screenshots/`。
- UI 初始草图：`specs/design/sketches/`。
- 个人 AI 沟通草稿：`.local/ai-prompts/`，不提交、不共享。
- 本地配置只参考 `config.example.toml`；不要默认打开 `config.toml`、`.env`、运行缓存、构建产物和 Agent 本地状态。

## 验证与提交门槛

UI、核心公共 API、类型/服务契约、schema、扫描索引、USB、配置、性能边界、重构和新功能改动，完成后必须先人工验证，再提交。

**无 UI 的人工验证等效规则：** 改动没有 UI 可供人工操作时（如纯 core 层能力），允许由 Agent 编写并执行一次性隔离场景脚本（独立临时目录，不触碰真实用户数据）驱动验证，把脚本命令与全部通过的结果记入 Task 即视为人工验证完成；用户确认「验证通过」后提交。涉及 UI 或现场行为的改动仍须用户实机验证。

自动化验证必须列出命令和结果；人工确认后才按 `docs/COMMIT_TEMPLATE.md` 提交，并按需同步 CHANGELOG、Review、任务状态和迁移说明。

CHANGELOG 按 Keep a Changelog 维护：只记录用户可感知功能、重要缺陷修复和必要兼容性变化；测试命令、任务状态、Review 过程及纯格式化/类型修复不写入 CHANGELOG，具体格式见 `docs/agent-workflow.md`。

每个 Task 完成前都要按当前规格改写 DoD 和状态，不要追加修订史。人工验证、Review、CHANGELOG 和迁移说明不是所有任务都必需，但必须明确标记为“已完成”或“不适用”，不能留空。最终回复必须区分“实现完成，等待人工验证”和“人工验证通过，记录已更新”。

完整流程、任务文件写法、复杂度标注、Review 自动化和迁移说明见 [docs/agent-workflow.md](docs/agent-workflow.md)。
