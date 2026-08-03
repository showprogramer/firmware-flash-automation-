# Agent 工作流规范

本文档保存 Agent 使用项目时的低频流程规则。`AGENTS.md` 只保留高频约束和入口索引。

## 共享入口

- Codex、OpenCode 和其他支持 `AGENTS.md` 的工具以根目录 `AGENTS.md` 为共享规范入口。
- `CLAUDE.md` 只作为 Claude Code 兼容入口，避免维护第二套完整规范。
- 产品概览见根目录 `README.md`；架构细节见 `docs/architecture.md`。

## 上下文读取纪律

- 默认只读取与当前任务直接相关的代码、测试、当前任务规格和 `CHANGELOG.md` 的 Unreleased 区域。
- 不默认打开本地配置、运行缓存、构建产物、公司内部资料、办公文件或 IDE/Agent 本地状态。
- 查询本地配置时使用 `config.example.toml`；需要真实值时由用户主动提供相关片段。
- USB 设备、路径和序列号使用 `<USB_DRIVE>` 等占位符，不在文档中记录现场值。
- 不把原始会话、私人提示词、本地缓存或敏感配置复制进共享报告。

## Ignore 文件同步

修改 `.claudeignore`、`.codexignore` 或 `.cursorignore` 时，三份文件必须同步；只允许保留顶部工具名称注释的差异。

本地 Agent 状态、个人草稿和运行报告包括：

```text
.codex/
.qoder/
.local/
```

这些目录同时由 Git 和各 Agent ignore 文件排除。

## 任务验证与提交

以下改动完成后，必须先通知人工验证，得到“验证通过”后才能提交：

- UI 改动；
- `core/` 公共 API、类型契约、服务返回结构或数据库 schema 改动；
- 固件资产、USB、配置、性能或安全边界改动；
- 重构、新功能、操作面板注册表或 UI 入口改动。

每个 Task 都必须维护完成状态；Review 和人工验证按任务风险条件决定，不是所有任务的固定步骤。Task 文件至少应能明确表达：

```md
- [ ] Task DoD 已更新
- [ ] 自动化验证已记录 / 不适用
- [ ] 人工验证已记录 / 不适用
- [ ] Review 已完成 / 不适用
- [ ] CHANGELOG 已同步 / 不适用
```

流程：

1. 先更新 Task DoD，并区分实现状态与验收状态。
2. 列出自动化验证命令及结果；没有适用验证时明确写“不适用”。
3. 需要人工验证的任务回复“实现完成，等待人工验证”，不能直接宣称最终完成。
4. 用户确认“验证通过”后，补写人工验证记录和最终状态。
5. 仅在触发条件满足时创建或关闭 Review；未触发时明确标记 Review“不适用”。
6. 需要时同步 `docs/CHANGELOG.md`、当前任务状态和迁移说明。
7. 所有必需项完成后，按 `docs/COMMIT_TEMPLATE.md` 生成 Conventional Commit 并提交。

最终回复必须区分：

- `实现完成，等待人工验证`
- `人工验证通过，Task 记录已更新`
- `已提交：<commit>`

普通文档、单测补充等低风险任务可以不创建 Review；UI、公共 API、类型契约、schema、扫描索引、USB、重大重构和新功能仍按上面的人工验证及 Review 触发条件执行。

## 复杂度标注

新建或修改 `specs/active/` 任务及活跃 Review 时，每个 Task 或 Issue 都要在标题末尾标注 `complexity: low|medium|high|xhigh`，并在文件列表前说明理由。

- `low`：单文件、纯文档或测试补齐。
- `medium`：多文件但单一关注点，或涉及一层 UI/service。
- `high`：跨 core 与 UI，或涉及类型、服务契约、schema、扫描索引公共路径。
- `xhigh`：跨多个阶段且包含 schema、公共 API、UI 和现场语义变化；必须先拆成子任务。

复杂度理由应说明可复核的范围和风险，不能只依据代码行数或主观感受。

## Code Review 与迁移说明

- 重大重构、公共 API、schema、扫描索引、USB、服务契约或 UI 入口改动，需要在 `docs/code-review/` 建立活跃 Review。
- Review 关闭后移入 `docs/code-review/archive/`，并同步归档索引。
- 路径移动、公共入口、配置/runtime 路径、schema 迁移和兼容层变更，在 `docs/migrations/` 添加简短迁移说明。

## 常用命令

Windows 主验证命令：

```powershell
uv sync --extra dev
uv run fwasset
uv run python -m pytest -q
uv run python -m pytest -m "not ui" -q
.\scripts\test.ps1
```

具体模块的 focused test 由任务范围决定；没有对应命令时应明确记录为未验证，而不是猜测结果。

## 双平台虚拟环境纪律

- `.venv` 只在 Windows 下使用；`.venv-wsl` 只在 WSL/Linux 下使用。
- **WSL 下禁止执行裸 `uv run` / `uv sync`**：uv 检测到 `.venv` 平台不匹配会尝试重建它，在 `/mnt/d` 挂载上删除失败会留下残缺包（2026-08-03 曾损坏 psutil，缺 8 个文件导致 `ImportError: cannot import name '_common'`）。
- WSL 下正确的测试方式（二选一）：

```bash
.venv-wsl/bin/python -m pytest -m "not ui" -q
UV_PROJECT_ENVIRONMENT=.venv-wsl uv run python -m pytest -m "not ui" -q
```

- 若 `.venv-wsl` 未安装依赖：`UV_PROJECT_ENVIRONMENT=.venv-wsl uv sync --extra dev`（不会触碰 `.venv`）。
- Windows 侧 `.venv` 修复：`uv pip install --reinstall psutil`，或删除 `site-packages/psutil*` 后 `uv sync --extra dev`。
