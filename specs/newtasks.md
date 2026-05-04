# 任务清单

> 来源文档：[specs/requirements-spec.md](./requirements-spec.md)
>
> 本文档把最新需求规格整理为可执行 todolist，按优先级推进。除特别说明外，均以 `requirements-spec.md` 为唯一需求依据。
>
> 状态：`[ ]` 待办 / `[~]` 进行中 / `[x]` 已完成 / `[-]` 已取消

---

## P0 —— 立即执行

### 1. 移除剩余台账遗留

- [x] 删除 `core/excel_ops.py`、`core/services/excel_service.py`、`data/handcontrol_ui_template.xlsx`
- [x] 删除 `tests/test_excel_ops.py`、`tests/test_excel_service.py`、`tests/test_excel_integration.py`、`tests/test_crud_ops.py`、`tests/test_app_preview_cache.py`
- [x] 从 `core/services/__init__.py` 移除 `excel_service` 导出
- [x] 从 `settings.py` 移除 `DEFAULT_EXCEL` / `EXCEL_SHEET` / `EXCEL_HEADER_ROW`
- [x] 从 `config.toml` 移除 `[excel]` 配置段
- [x] 从 `handcontrol_panel.py` 移除台账表单 UI、台账预览 Tab、Excel 操作按钮、状态图例
- [x] 从 `handcontrol_panel.py` 移除台账相关变量（`field_logo` / `field_language` / `field_salesman` / `field_attachment` / `review_status` / `preview_search_var`）
- [x] 从 `flash_service.py` 移除 Excel 写入逻辑（`write_excel_record` / `update_record_fields` 调用）
- [x] 从 `scan_service.py` 移除 `excel_path` / `excel_sheet` / `status_map` 参数
- [x] 清理 `sort_config.py` 死代码：`SortKey.STATUS` / `_STATUS_RANK` / `status_map` 参数均已移除
- [x] 复查运行时代码确认无 `import excel_ops` / `import excel_service` 残留

> 验收：手控 UI 无 Excel 相关控件；运行时代码无 Excel 相关 import/调用；`sort_config.py` 只保留 PATH/MODEL/VERSION 三种排序。

---

### 2. 统一左侧为"固件资源列表"

> ⚠️ **依赖关系**：本任务与 P0-3（扩展类型）、P0-4（接入 catalog）、P0-5（扫描引擎）**强耦合**——类型定义 → 扫描引擎 → 列表 UI 是同一链路的三层，应在一个 PR 内同步完成，不独立验收。

- [ ] 移除 `shell.py` 中 `CTkSegmentedButton` 的"手控模式"/"音乐模式"切换
- [ ] 移除 `HandcontrolPanel` / `MusicPanel` 双 Panel 架构，改为单一 `FirmwareListPanel`
- [ ] 左侧边栏结构：
  - [ ] 搜索框（保留现有）
  - [ ] 固件类型多选筛选（checkbox / dropdown）
  - [ ] 统一资源列表（型号、版本、固件类型标签、目录名、刷写方式标记）
- [ ] 中间详情区域：统一展示选中条目的型号/版本/路径/文件清单/修改时间
- [ ] 右侧操作区：按 `flash_mode` 动态渲染（见 P1-9，本阶段先保留手控 USB 操作）
- [ ] `MusicPanel` 的 U 盘刷机逻辑合并到 `auto_usb` 操作区
- [ ] `MusicPanel` 的串口 AT 能力提取为独立的可复用操作区组件（`ui/serial_control.py`），供 P1-9 使用

> 验收：不再按固件类型建平级 Panel；所有固件类型资源进入同一列表浏览体系。

---

### 3. 扩展固件类型模型到 19 类

> 与 P0-2/4/5 同步完成。

- [ ] 在 `types.py` 中把 `FirmwareType` 从 `Literal["handcontrol_ui", "music_bt"]` 扩展为完整 19 类
- [ ] 每种类型定义：`key` / `label` / `flash_mode` / 基础元数据
- [ ] 类型覆盖：主板、手控UI、蓝牙、语音、快捷键、3D机芯、2D机芯、旋钮、腿部、膝盖、音波、健康检测、商用主板、占座、刷卡、乐摇摇、三合一、老化、断码屏

> 验收：类型定义完整；代码不再只围绕两类设计。

---

### 4. 接入 `firmware_catalog.toml` 到运行时扫描

> 与 P0-2/3/5 同步完成。

- [ ] 将 `firmware_catalog.py` 从死代码变为扫描主入口
- [ ] 扫描流程改为配置驱动：`dir_keywords` + `file_extensions` 匹配目录
- [ ] 输出统一 `FirmwareAsset` 结构，至少包含：`firmware_type` / `model` / `version` / `path` / `files` / `flash_mode`
- [ ] `firmware_catalog.toml` 从当前 5 种扩展为 19 种类型配置

> 验收：扫描逻辑不再硬编码为手控专用；运行时实际调用 catalog 配置。

---

### 5. 实现通用扫描引擎

> 与 P0-2/3/4 同步完成。

- [ ] 实现通用扫描服务，替代 `file_scan.py` 的手控专用扫描
- [ ] 两层扫描：先按 `dir_keywords` 识别目录的固件类型，再按该类型规则提取型号/版本/文件
- [ ] 性能：1000+ 目录 < 5 秒
- [ ] 错误处理：目录不可读时明确返回错误，不静默跳过

> 验收：可识别多种固件类型目录；扫描失败时有明确错误返回。

---

### 6. 修复 `format_usb` 的命令注入风险

> 独立任务，可与 P0-2~5 并行。

- [ ] `usb_ops.py:275` 将 `shell=True` 改为参数列表形式
- [x] 测试覆盖已覆盖成功/失败/异常分支（`tests/test_usb_ops.py` L153）
- [ ] 补充测试覆盖超时分支

> 验收：无 `shell=True` 格式化命令路径；测试覆盖成功/失败/异常/超时全部四个分支。

---

## P1 —— 短期

### 7. 构建工具中心

- [ ] 基于 `firmware_catalog.toml` 的 `tool_name` / `tool_path` 实现工具注册与一键启动
- [ ] `tool_launch` 类型资产在操作区显示"打开工具"按钮
- [ ] 工具路径可配置、可修改

> 验收：`tool_launch` 类型资产可一键打开对应工具。

---

### 8. 资源列表支持多维筛选

- [ ] 按固件类型筛选（多选）
- [ ] 按刷写方式筛选
- [ ] 按状态筛选
- [ ] 保留现有按名称/型号/版本排序
- [ ] 筛选和排序可组合使用

> 验收：筛选和排序可组合使用且不冲突。

---

### 9. 操作区按 `flash_mode` 动态渲染

- [ ] `auto_usb`：一键刷机 + 手动分步操作（默认折叠）
- [ ] `auto_serial`：串口连接/断开、波特率选择、AT 命令预设按钮、自定义命令输入、串口日志（复用 P0-2 中提取的 `serial_control` 组件）
- [ ] `tool_launch`：打开工具按钮（复用 P1-7 工具中心）
- [ ] `manual_doc`：查看说明按钮 + 图文弹窗
- [ ] `disabled`：按钮灰显并说明原因

> 验收：切换不同固件类型条目时，右侧操作区随 `flash_mode` 变化。

---

### 10. 调研并固化主板刷写方式

- [ ] 明确主板程序实际刷写方式（USB？串口？专用烧录器？）
- [ ] 根据结论更新 `firmware_catalog.toml` 中 `mainboard` 的 `flash_mode`
- [ ] 如可自动化，规划实现任务纳入 P2

> 验收：主板类型有明确可执行路径。

---

### 11. 评估蓝牙、语音、快捷键自动化能力

- [ ] 确认蓝牙程序是否只需 USB 流程，还是需串口 AT 增强
- [ ] 调研语音程序烧录方式和标准化可行性
- [ ] 调研快捷键程序烧录方式
- [ ] 输出结论文档：哪些可做、怎么做、工作量估算

> 验收：结论文档输出到 specs；评估通过的固件类型加入 P2 实现计划。

---

## P2 —— 中期

### 12. 实现"按型号聚合"视图

- [ ] 从"资源条目列表"视角可切换到"型号集合"视角
- [ ] 一个型号下聚合展示全部固件类型及其状态
- [ ] 标记缺失的固件类型（该型号该有但没有的）

> 验收：可以按型号查看完整固件集合，识别缺口。

---

### 13. 建立兼容型号记录机制

- [ ] `firmware_catalog.toml` 或独立配置支持 `compatible_models` 字段
- [ ] 列表中展示兼容型号信息
- [ ] 详情面板展示兼容范围

> 验收：跨型号共用固件可查看和编辑兼容关系。

---

### 14. 探索快捷键自动化

> 前置依赖：P1-11 评估通过。

- [ ] 根据 P1-11 结论实现快捷键板自动化烧录流程
- [ ] 更新 `firmware_catalog.toml` 中 `shortcut_key` 的 `flash_mode`

> 验收：快捷键类型有可执行的自动化/工具启动路径。

---

### 15. 探索机芯板自动化

- [ ] 评估 `movement_3d` / `movement_2d` 的刷写流程
- [ ] 可接工具则接工具，可自动化则规划服务接口
- [ ] 更新 catalog 中的 `flash_mode`

> 验收：机芯板类型有明确操作路径。

---

## P3 —— 长期

### 16. 完成 19 类全覆盖接入

- [ ] 所有固件类型至少实现"目录识别 + 资产展示 + 工具启动或说明入口"
- [ ] 老化程序等特殊类型标注 `disabled` 并展示原因
- [ ] 优先保证可管理，再逐步提高自动化比例

> 验收：19 种固件类型全部可在平台中浏览和操作。

---

### 17. 商用机和外设类流程扩展

- [ ] 商用主板、占座、刷卡、乐摇摇分类接入（目录识别 + 工具/说明入口）
- [ ] 旋钮、腿机、膝盖、音波、健康检测外设类接入

> 验收：商用机和外设类固件进入资源管理体系。

---

### 18. 完整串口流程编排

- [ ] 对 `auto_serial` 类型抽象可配置 AT 命令序列
- [ ] 支持：连接 → 发送命令序列 → 校验响应 → 断开，全自动
- [ ] 命令序列可通过 `firmware_catalog.toml` 或独立配置定义

> 验收：至少一种 `auto_serial` 类型可执行完整自动串口烧录流程。

---

## 横向任务（持续）

### A. 数据模型统一

- [ ] 定义 `FirmwareAsset`、`FlashMode`、`ToolRegistration` 等核心 TypedDict
- [ ] 统一 UI 和 service 的输入输出结构
- [ ] 所有 service 返回 `ServiceResult` 格式

### B. 文档同步

- [ ] 每轮功能迁移后同步更新：`CHANGELOG.md` / `README.md` / `specs/requirements-spec.md`

### C. 测试补齐

- [ ] P0-5（扫描引擎）补充集成测试
- [ ] P0-6（format_usb）补充安全测试
- [ ] P1-7（工具中心）补充工具启动测试
- [ ] P1-9（动态操作区）补充 UI 渲染测试
- [ ] 持续保持 `core` 模块覆盖率 >= 80%

### D. 遗留代码清理

- [ ] 评估 `app.py`（65 行全部为旧版 tkinter monkey-patch）是否可删除，改为 `shell.main()` 作为唯一入口
- [ ] `sort_config.py` 清理后，确认 `STATUS` 枚举和 `status_map` 参数已移除

---

## 建议实施顺序

```
Phase 1 ─────────────────────────────────────────────
  P0-1  移除台账遗留（大部分已完成，仅剩 sort_config 死代码）
  ↓
  P0-2 + P0-3 + P0-4 + P0-5  ← 同一 PR，同步完成
  （统一列表 + 扩展类型 + 接入 catalog + 扫描引擎）
  ↓
  P0-6  修复 format_usb（可并行）
  ↓
Phase 2 ─────────────────────────────────────────────
  P1-7  工具中心
  P1-8  多维筛选
  P1-9  操作区动态渲染
  ↓
Phase 3 ─────────────────────────────────────────────
  P1-10 主板调研
  P1-11 蓝牙/语音/快捷键评估
  ↓
Phase 4 ─────────────────────────────────────────────
  P2-12 型号聚合视图
  P2-13 兼容型号记录
  P2-14 快捷键自动化（依赖 P1-11）
  P2-15 机芯板自动化
  ↓
Phase 5 ─────────────────────────────────────────────
  P3-16 19 类全覆盖
  P3-17 商用机和外设流程
  P3-18 串口流程编排
  ↓
横向任务 A/B/C/D 贯穿所有 Phase
```
