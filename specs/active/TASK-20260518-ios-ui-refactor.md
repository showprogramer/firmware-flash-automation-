# TASK-20260518-ios-ui-refactor

## 状态: ✅ 已完成

## 概述
将现有UI重构为iOS HIG风格的简洁美观布局：内容优先、大量留白、统一设计Token、消除硬编码、修复代码问题。

## 背景
- 当前侧边栏占760px (weight=8) vs 主内容区320px (weight=0)，比例失衡
- 7处硬编码颜色绕过design_tokens
- 无间距/圆角/高度Token，全是魔法数字
- 两套重复Treeview样式，DetailPanel死代码
- 整体观感不够专业，缺乏iOS风格的美感

## Phase 1: 设计系统重建 (design_tokens.py)
- [ ] 1.1 颜色Token重构为iOS HIG色系（BG_WINDOW, COLOR_PRIMARY→#007AFF等）
- [ ] 1.2 新增TEXT_TERTIARY, TEXT_ON_PRIMARY, SEPARATOR, COLOR_INFO
- [ ] 1.3 新增间距Token: SPACE_XS/SM/MD/LG/XL/2XL/3XL
- [ ] 1.4 新增圆角Token: RADIUS_SM/MD/LG/XL
- [ ] 1.5 新增高度Token: HEIGHT_SM/MD/LG/XL
- [ ] 1.6 新增FONT_SIZE_DISPLAY/XS, FONT_MONO
- [ ] 1.7 新增ICON_SM/MD/LG/XL, SIDEBAR_WIDTH
- [ ] 1.8 标记FONT_XL/LG/MD/SM为deprecated

## Phase 2: 布局重构
- [ ] 2.1 firmware_list_panel.py: 列比例改为 sidebar(weight=0,minsize=260) / main(weight=1,minsize=600)
- [ ] 2.2 sidebar_panel.py: 默认width=280，精简品牌头部高度
- [ ] 2.3 base_panel.py: _build_sidebar_frame(width=280)
- [ ] 2.4 主内容区padding: padx=SPACE_XL, pady=SPACE_XL
- [ ] 2.5 HeaderBar下方pady: 24→SPACE_LG(16)
- [ ] 2.6 树视图行高40→36，字体LG→MD

## Phase 3: 组件样式统一
- [ ] 3.1 修复硬编码颜色：header_bar.py "white"→TEXT_ON_PRIMARY
- [ ] 3.2 修复硬编码颜色：asset_tree.py "#4B5563"→_resolve(TEXT_SECONDARY)
- [ ] 3.3 修复硬编码颜色：tool_launch_panel.py "#E74C3C"→COLOR_DANGER
- [ ] 3.4 修复硬编码颜色：tool_center_panel.py "#E74C3C"/"#27AE60"/"white"→COLOR_DANGER/COLOR_SUCCESS/TEXT_ON_PRIMARY
- [ ] 3.5 合并Treeview样式：移除shared_widgets.apply_treeview_modern_style()，统一为Asset.Treeview
- [ ] 3.6 shell.py移除apply_treeview_modern_style调用
- [ ] 3.7 所有corner_radius→RADIUS Token
- [ ] 3.8 所有button height→HEIGHT Token
- [ ] 3.9 所有padding/margin→SPACE Token
- [ ] 3.10 asset_tree.py容器从tk.Frame改为ctk.CTkFrame

## Phase 4: 视觉层级精修
- [ ] 4.1 HeaderBar: 版本badge text_color→TEXT_ON_PRIMARY, 类型badge默认→TEXT_TERTIARY
- [ ] 4.2 ops_card: border_width=0 (iOS靠背景色差分层), corner_radius=RADIUS_LG
- [ ] 4.3 section_title: 字号LG→MD, 颜色→TEXT_SECONDARY
- [ ] 4.4 日志面板按钮文字优化
- [ ] 4.5 空状态标签居中+大字号+更多留白
- [ ] 4.6 侧边栏搜索框高度→HEIGHT_LG(44)

## Phase 5: 代码清理
- [ ] 5.1 移除DetailPanel实例化和grid_forget()死代码
- [ ] 5.2 tool_launch_panel.py合并重复按钮到build_handoff_actions(include_tool_combo=True)
- [ ] 5.3 运行.\scripts\test.ps1验证通过

## 修改文件清单
1. design_tokens.py
2. shared_widgets.py
3. asset_tree.py
4. shell.py
5. panels/sidebar_panel.py
6. panels/header_bar.py
7. panels/detail_panel.py
8. panels/log_panel.py
9. firmware_list_panel.py
10. base_panel.py
11. operation_panels/auto_usb_panel.py
12. operation_panels/tool_launch_panel.py
13. operation_panels/manual_doc_panel.py
14. operation_panels/disabled_panel.py
15. operation_panels/shared_actions.py
16. tool_center_panel.py

## 验证
- 运行 `.\scripts\test.ps1`
- 覆盖率 >= 80%
- 手动验证：侧边栏变窄、主内容区放大、iOS色系、间距圆角统一、无硬编码颜色