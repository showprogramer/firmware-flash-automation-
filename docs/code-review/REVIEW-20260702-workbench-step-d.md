# 代码审查：工作台 Step D 查询体验收尾

- 日期：2026-07-02；更新：2026-07-06
- 类型：UI 变更 / 交互优化 / 测试补充
- 模块：`ui/workbench_panel.py`, `ui/panels/data_grid_panel.py`, `tests/test_workbench_panel_helpers.py`, `tests/test_data_grid_panel.py`

## 问题描述
工作台 A-C 阶段已经完成主区树表和操作区精简，但 Step D 中的查询入口仍保留单一下拉型号选择，树表缺少烧录方式和更明确的来源视觉提示，选中变体后底部操作区也缺少紧凑的上下文摘要。

2026-07-06 复盘 `specs/current_project_ui/ui.png` 与 `specs/images/treeview_workbench_mockup.png` 后，当前界面仍存在明显视觉差距：左侧栏过宽、型号入口像移动端胶囊导航、侧栏字符画和 emoji 降低质感、主表整行蓝字影响扫描、底部操作区和日志区空白过大。

## 处理方案
1. 将型号选择改为平铺按钮 + `更多型号` 下拉收纳，选中的溢出型号会回到可见按钮区。
2. 保留独立搜索框，搜索继续服务模块、版本、方案、平台等多维关键词。
3. 删除树表「方式」列：除手控 UI（非断码屏）走一键烧录外，其余主要依赖烧录工具，表格层无需重复展示。
4. 「来源」列改为更易理解的「程序归属」，展示 `定制专属` / `通用默认`，并通过设计 token 配置交替行底色与归属语义色。
5. 将树表列名调整为 `程序类型 / 程序名称 / 版本 / 程序归属 / 程序文件`，避免「模块类型 / 变体名称」对烧录员语义不清。
6. 单变体程序名称与程序类型重复时显示 `默认`，避免 `主板程序 / 主板程序` 这类重复阅读。
7. 树表表头对齐方式跟随内容列：文本列左对齐，版本/归属状态列居中，避免表头居中但内容左对齐。
8. 底部操作区新增「已选」摘要，并统一使用 `grid` 管理外层布局，避免占位 Label 与操作容器混用 `grid`/`pack`。
9. 将视觉底座从偏 iOS 大白卡片调整为 Fluent 桌面工具：固定 248px 窄侧栏、把型号/搜索迁移到主区顶部筛选条、侧栏收敛为纯导航。
10. 移除侧栏字符画和 emoji，导航项使用低噪声按钮、选中态和分组标签。
11. 表格行文字恢复正常文本色，避免整行蓝字；表格、操作区、日志区增加细边界，底部高度压缩。
12. 工具启动操作区改为紧凑动作行，常态突出「打开烧录工具」而不是大段说明。
13. 删除左侧栏底部「工具中心」按钮，底部仅保留「扫描目录」；同步调整 U 盘未选提示，避免引导到已移除入口。

## 验证记录
- Windows PowerShell: `.\.venv\Scripts\python.exe -m pytest -m "not ui" -q --no-cov` -> `173 passed, 29 deselected`
- Windows PowerShell: `.\.venv\Scripts\python.exe -m pytest src\fwasset\tests\test_workbench_panel_helpers.py src\fwasset\tests\test_data_grid_panel.py src\fwasset\tests\test_operation_panels.py -q --no-cov` -> `32 passed`
- Windows PowerShell: `python -m py_compile src\fwasset\ui\design_tokens.py src\fwasset\ui\workbench_panel.py src\fwasset\ui\panels\data_grid_panel.py src\fwasset\ui\panels\log_panel.py src\fwasset\ui\operation_panels\auto_usb_panel.py src\fwasset\ui\operation_panels\tool_launch_panel.py` -> passed

## 状态
- [x] 自动化验证通过
- [ ] 等待用户人工验证通过后提交

## 关联 Commit
- 本提交（提交哈希以 `git log` 为准）
