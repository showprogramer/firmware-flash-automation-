---
### 问题 1：扫描取消状态仍耦合在 FirmwareListPanel

**类型**： 重构

**模块**： `src/fwasset/ui/firmware_list_panel.py`, `src/fwasset/ui/view_models/scan_state_model.py`

**问题描述**
- `FirmwareListPanel` 直接维护 `_scan_cancel_event`，扫描生命周期、取消状态和按钮事件耦合在 UI 面板中。
- 后续继续拆分扫描控制或增加进度状态时，需要继续扩大 `FirmwareListPanel` 的职责。

**处理方案**
- 新增 `ScanStateModel`，封装扫描开始、取消请求、完成清理和当前事件读取。
- `FirmwareListPanel._scan()` 改为通过 `ScanStateModel` 管理扫描状态，并保留 `_scan_cancel_event` 兼容层，降低对既有测试和调用点的冲击。
- 新增 `tests/test_scan_state_model.py` 覆盖扫描生命周期、重复 begin、取消和旧任务完成隔离。

**状态**： ✅ 已修复

**验证记录**
- 验证日期：2026-05-16
- 验证人：人工 / Agent
- 验证结果：通过
- 对应版本：Unreleased

**相关 Commit**： 本次提交
---
