# 代码审查归档索引

以下文件已从 `docs/code-review/` **根目录移出**，议题均已闭环或被后续审查吸收。  
需要细节时打开对应文件；**不要**再当作未完成任务列表。

| 文件 | 日期 | 主题 | 处置 |
|------|------|------|------|
| [REVIEW-20260720-shared-module-registration.md](./REVIEW-20260720-shared-module-registration.md) | 2026-07-24 | B2 共享手动登记入口 | Qt 3 场景人验通过；CTk 随 B3；已闭环 |
| [REVIEW-20260720-shared-module-registration-independent.md](./REVIEW-20260720-shared-module-registration-independent.md) | 2026-07-24 | B2 独立审查 | B2 议题闭环；迁移议题移交后置 TASK |
| [REVIEW-20260514-scan-index-race.md](./REVIEW-20260514-scan-index-race.md) | 2026-05-14 | 扫描/索引竞态 | 已闭环；扫描互锁见分支总审 Issue 3 |
| [REVIEW-20260516-scan-state-model.md](./REVIEW-20260516-scan-state-model.md) | 2026-05-16 | ScanStateModel 抽取 | 已修复并合入 |
| [REVIEW-20260518-agents-and-doc-naming.md](./REVIEW-20260518-agents-and-doc-naming.md) | 2026-05-18 | AGENTS / 文档命名 | 规范已落地 AGENTS.md |
| [REVIEW-20260518-ios-ui-refactor.md](./REVIEW-20260518-ios-ui-refactor.md) | 2026-05-18 | 早期 iOS 风 UI | 界面已多次重写，仅历史参考 |
| [REVIEW-20260518-sidebar-panel.md](./REVIEW-20260518-sidebar-panel.md) | 2026-05-18 | 旧侧边栏面板 | 组件已替换为工作台 |
| [REVIEW-20260606-l36-directory-standard.md](./REVIEW-20260606-l36-directory-standard.md) | 2026-06-06 | L36 目录标准长文 | 目录约定以 `docs/migrations/MIGRATION-20260606-*` + 现行扫描为准 |
| [REVIEW-20260608-l36-scanner.md](./REVIEW-20260608-l36-scanner.md) | 2026-06-08 | L36 扫描器重构 | 已合入 |
| [REVIEW-20260609-workbench-ui.md](./REVIEW-20260609-workbench-ui.md) | 2026-06-09 | 方案工作台 UI | 已被后续 workbench / Qt 审查覆盖 |
| [REVIEW-20260702-workbench-step-d.md](./REVIEW-20260702-workbench-step-d.md) | 2026-07-02 | 工作台 Step D | 已闭环 |
| [REVIEW-20260706-ui-review-bugfix.md](./REVIEW-20260706-ui-review-bugfix.md) | 2026-07-06 | UI Review 六项修复 | 已合入（CHANGELOG 有链） |
| [REVIEW-20260708-platform-default.md](./REVIEW-20260708-platform-default.md) | 2026-07-08 | 设为平台默认 | 已合入 |
| [REVIEW-20260708-pyside6-p1-p2.md](./REVIEW-20260708-pyside6-p1-p2.md) | 2026-07-08 | PySide6 Phase 1+2 | 已吸收进分支总审 / Phase3 |
| [REVIEW-20260709-pyside6-phase3-core.md](./REVIEW-20260709-pyside6-phase3-core.md) | 2026-07-09 | Phase3 + 核心域 | 处置表已并入分支总审 |

## 归档策略（简）

- **不删 git 历史**：搬迁用 `git mv`，旧路径在历史中仍可查。  
- **根目录只留活文档**，避免「十几份 REVIEW 全像未完成任务」。  
- 目录标准、迁移说明仍以 `docs/migrations/` 为准；本目录长文仅作当时决策快照。

归档日期：2026-07-09  
