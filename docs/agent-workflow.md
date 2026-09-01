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

## 任务文件写法

`specs/active/` 里的 Task 是给后续 Agent 对照执行的**当前规格**，不是会话日记。Git 负责过程历史。

- 只保留：当前目标、当前规则、当前验收、当前 DoD、最新一次验证记录，以及仍有效的非目标或「须另立 TASK」项。
- 用户改需求时**改原文**（规则、验收、DoD 一起改成现在的样子）。不要追加「修订 N」「修订理由」或新旧对照长文。
- 作废规则直接删掉，不要留「已作废，仅记录过程」。
- 验证记录只留**最新一次**跑通的命令和结果；表格覆盖写入，不按轮次追加行。
- DoD 是当前完成清单，随规格改写；不要把每次反馈加成新勾选项。

## 任务验证与提交

以下改动完成后，必须先通知人工验证，得到“验证通过”后才能提交：

- UI 改动；
- `core/` 公共 API、类型契约、服务返回结构或数据库 schema 改动；
- 固件资产、USB、配置、性能或安全边界改动；
- 重构、新功能、操作面板注册表或 UI 入口改动。

**无 UI 的人工验证等效规则：** 改动没有 UI 可供人工操作时（如纯 core 层能力），允许由 Agent 编写并执行一次性隔离场景脚本（独立临时目录，不触碰真实用户数据）驱动验证；把脚本命令与全部通过的结果记入 Task 的人工验证记录，用户确认「验证通过」后即可提交。涉及 UI 或现场行为的改动仍须用户实机验证。

每个 Task 都必须维护完成状态；Review 和人工验证按任务风险条件决定，不是所有任务的固定步骤。Task 文件至少应能明确表达：

```md
- [ ] Task DoD 已更新
- [ ] 自动化验证已记录 / 不适用
- [ ] 人工验证已记录 / 不适用
- [ ] Review 已完成 / 不适用
- [ ] CHANGELOG 已同步 / 不适用
```

流程：

1. 按当前规格改写 Task DoD，并区分实现状态与验收状态。
2. 用最新一次自动化验证覆盖写入命令和结果；没有适用验证时明确写“不适用”。验证记录使用统一模板，六要素齐全：

```markdown
## 验证记录

### 自动化验证（已完成 / 不适用）

| 平台 | 环境 | 命令 | 结果 |
| --- | --- | --- | --- |
| Windows | `.venv` | `uv run python -m pytest -m "not ui" -q` | 通过（N passed） |
| Windows | `.venv` | `uv run ruff check src scripts` | 通过 |
| Windows | `.venv` | `uv run mypy` | 通过 |

（本项目纯 Windows，验证只在 Windows `.venv` 下执行，不再使用 WSL / `.venv-wsl`。）

- 已知平台差异：无（或在 Linux 失败、Windows 通过的用例需逐条列出原因，禁止用“环境问题”笼统带过）
- 提交：`77cbbd0`（提交前写「待提交」，提交后回填真实 hash）

### 人工验证（已完成 / 不适用）

- 平台：Windows 实机 / 不适用
- 结论：具体验证内容与结果，不能只写“验证通过”
```
3. 需要人工验证的任务回复“实现完成，等待人工验证”，不能直接宣称最终完成。
4. 用户确认“验证通过”后，补写人工验证记录和最终状态。
5. 仅在触发条件满足时创建或关闭 Review；未触发时明确标记 Review“不适用”。
6. 需要时同步 `docs/CHANGELOG.md`、当前任务状态和迁移说明。
7. 所有必需项完成后，按 `docs/COMMIT_TEMPLATE.md` 生成 Conventional Commit 并提交。
8. 提交前与提交后各跑一次任务状态一致性检查（error 或 warning 都必须清零）：

```powershell
uv run python scripts/check_task_sync.py --pre-commit --strict   # 提交前：允许“完成 commit”为“本次提交”
uv run python scripts/check_task_sync.py --strict                # 提交后：必须回填真实 hash
```

提交前阶段通过后提交；提交完成后把 `完成 commit` 回填为真实 hash（需要时随收尾 commit 落地），再跑提交后阶段。检查项：当前状态与 Task DoD 一致性、「待人工验证」与人工验证记录冲突、Review/CHANGELOG/迁移说明标记、「完成 commit」是否填写且 hash 真实存在。脚本只查存在性与结构，标记内容是否正确仍需人工判断。

最终回复必须区分：

- `实现完成，等待人工验证`
- `人工验证通过，Task 记录已更新`
- `已提交：<commit>`

普通文档、单测补充等低风险任务可以不创建 Review；UI、公共 API、类型契约、schema、扫描索引、USB、重大重构和新功能仍按上面的人工验证及 Review 触发条件执行。

## CHANGELOG 规范

`docs/CHANGELOG.md` 按 Keep a Changelog 结构维护，使用 `Unreleased` 和日期/版本段落，并按实际内容使用以下分类：

- `Added`：新增用户可使用的能力。
- `Changed`：已有用户流程、界面或配置语义发生变化。
- `Fixed`：用户可感知的缺陷修复或安全边界修复。
- `Removed`：移除已有能力或明确取消的范围。
- `Deprecated` / `Security`：仅在确有对应内容时使用。

写入规则：

- 一条记录描述一个用户结果，不按 commit 数量逐条复制，也不在标题中堆叠 Task、Review 或 commit hash。
- 只记录用户可感知功能、重要缺陷、数据/配置兼容性和安全边界变化；纯格式化、类型标注、内部重构、测试用例、测试命令和任务状态不写入。
- 同一功能的实现、修复和 UI 调整合并为一条结果导向记录，避免重复描述内部文件和阶段名称。
- 有用户可见变化时更新 `Unreleased`；只有内部工程或测试变化时标记 CHANGELOG 为“不适用”。
- 验证命令、测试数量、人工验收和 Review 结论写入 Task/Review 的**当前**验证记录，不复制到 CHANGELOG，也不在 Task 里堆积历史轮次。
- 历史细节以 Git 历史和归档文档为准，不在 CHANGELOG 或活跃 Task 里保留逐提交流水账。

## 复杂度标注

新建或改写 `specs/active/` 任务及活跃 Review 时，每个**当前仍有效**的 Task 或 Issue 都要在标题末尾标注 `complexity: low|medium|high|xhigh`，并在文件列表前说明理由。同一任务的后续反馈用来改写该 Task/Issue，不要为此新增「修订 N」小节。

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
.\scripts\quality.ps1     # ruff + format + mypy
```

具体模块的 focused test 由任务范围决定；没有对应命令时应明确记录为未验证，而不是猜测结果。
