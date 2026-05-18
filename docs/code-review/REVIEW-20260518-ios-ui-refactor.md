---
### 问题 1：UI设计系统混乱 — 硬编码颜色、魔法数字间距、不一致圆角/高度

**类型**： 重构

**模块**： `src/fwasset/ui/` (全部16个文件)

**问题描述**
- 7处硬编码颜色绕过design_tokens（`#E74C3C`, `#27AE60`, `#4B5563`, `"white"`等）
- 无间距/圆角/高度Token，所有值都是魔法数字
- 两套重复Treeview样式（`Modern.Treeview`和`Asset.Treeview`）
- 侧边栏760px vs 主内容区320px，比例本末倒置
- DetailPanel实例化后立即grid_forget()，为死代码
- tool_launch_panel有重复按钮代码
- asset_tree容器用`tk.Frame`而非`ctk.CTkFrame`

**处理方案**
- 重建design_tokens.py为iOS HIG色系，新增8类Token（间距/圆角/高度/图标/布局/字体等）
- 布局比例改为3:5（sidebar:main）
- 所有硬编码颜色→语义Token
- 合并Treeview样式为唯一标准
- 移除DetailPanel死代码
- 合并tool_launch_panel重复按钮到shared_actions
- 全部硬编码padding/corner_radius/height→Token

**状态**： ✅ 已修复

**验证记录**
- 验证日期：2026-05-18
- 验证人：人工
- 验证结果：通过
- 对应版本：未发布

**相关 Commit**： 待提交
---