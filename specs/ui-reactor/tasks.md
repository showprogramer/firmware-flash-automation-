# UI Reactor 重构任务清单（2026-04-17 现状版）

## A. 已完成（基线）
- [x] 服务层抽离：`serial_service / at_command_service / music_flash_service` 已落地。
- [x] 配置化：`config.toml` 已支持 `[music]`、`[serial]`。
- [x] 单程序双模式：`app.py` 已支持手控/音乐两条流程。
- [x] 测试补齐（当前范围）：`test_serial_service / test_at_command_service / test_music_flash_service / test_app_service_smoke` 已覆盖关键链路。

## B. 下一阶段（CTk 迁移）

### B1. 架构拆分
- [ ] 新建 `src/handcontrol/ui/shell.py`：承载模式切换、全局状态与任务调度入口。
- [ ] 新建 `src/handcontrol/ui/handcontrol_panel.py`：迁移手控面板 UI。
- [ ] 新建 `src/handcontrol/ui/music_panel.py`：迁移音乐面板 UI。
- [ ] 新建 `src/handcontrol/ui/shared_widgets.py`：抽公共组件。

### B2. 手控 UI 迁移
- [ ] 将左侧列表从 `Listbox` 迁移为卡片列表（CTk）。
- [ ] 将右侧刷机与审核区域迁移到 CTk 组件。
- [ ] 将底部预览/日志迁移为 CTk 风格容器，保留 Treeview 数据能力。

### B3. 音乐 UI 迁移
- [ ] 将串口扫描、连接、AT 发送区迁移到 CTk 面板。
- [ ] 将音乐 U 盘流程区迁移到 CTk 面板。
- [ ] 保持调用 `core/services`，禁止把业务逻辑回写到 UI。

### B4. 回归与验收
- [ ] 自动化：`.\scripts\test.ps1` 全绿。
- [ ] 手工：手控全流程 + 音乐全流程 + 模式切换稳定。
- [ ] 文档同步：`design.md`、`tasks.md`、`CHANGELOG.md`。

## C. 执行顺序（严格）
- [ ] UI 架构拆分
- [ ] 手控面板迁移
- [ ] 音乐面板迁移
- [ ] 联调与回归
- [ ] 文档收口
