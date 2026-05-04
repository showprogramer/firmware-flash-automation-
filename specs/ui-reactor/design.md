# UI Reactor 设计文档（2026-04-17 现状版）

## 1. 目标与边界
- 目标：在不破坏已上线能力的前提下，完成从 `tkinter/ttk` 到 `customtkinter` 的 UI 迁移。
- 已完成基线：
1. 服务层抽离（serial/at/music_flash）。
2. 音乐版配置化（`[music]`、`[serial]`）。
3. 单程序双模式（`app.py` 已有“手控 + 音乐”入口）。
- 本阶段边界：仅做 UI 壳重构，不改 `core/services` 对外契约。

## 2. 当前架构（已落地）
- 主入口：`src/handcontrol/app.py`
- 核心服务：
1. 手控：`scan_service / flash_service / usb_repair_service`
2. 音乐：`serial_service / at_command_service / music_flash_service`
- 配置入口：`config.toml`

## 3. 目标架构（下一阶段）
- UI 技术栈：`customtkinter + ttk(Treeview)`
- 模块拆分建议：
1. `ui/shell.py`：顶层容器与模式切换。
2. `ui/handcontrol_panel.py`：手控面板。
3. `ui/music_panel.py`：音乐面板。
4. `ui/shared_widgets.py`：公共组件（日志、状态条、路径选择、按钮组）。
- 业务调用保持不变，全部通过 `core/services`。

## 4. 信息架构
- 模式容器：顶部 `Tab/Segmented`（手控 / 音乐）。
- 手控面板：列表区 + 操作区 + 资源详情/日志。
- 音乐面板：U 盘流程区 + 串口/AT区 + 音乐日志区。

## 5. 交互约束
- 所有 IO 操作必须走现有 `_run_task + queue` 或同等异步模型。
- 异常反馈保持双通道：`messagebox + 日志`。
- 模式切换不重置全局配置（路径、盘符、串口选择尽量保留）。

## 6. 视觉方向
- 视觉参考：`specs/ui-reactor/new_uigemini.py`。
- 迁移策略：先保持布局和交互稳定，再替换样式和细节动画，避免一次性大改导致回归。

## 7. 验收标准
- 自动化：`.\scripts\test.ps1` 全绿。
- 手工链路：
1. 手控：扫描→选择→一键/分步→写表→预览更新。
2. 音乐：目录选择→U盘流程→串口连接→AT发送→波特率切换。
- 可观测性：关键动作均可在日志区定位。
