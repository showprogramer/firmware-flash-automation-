"""Qt 版设计令牌（布局度量）。

颜色与字体由 QFluentWidgets 主题统一供给（`setTheme`），不在此重复定义；
本模块只承载布局度量，数值对齐 `ui/design_tokens.py` 的 8pt 栅格。
CTk 退役后此文件成为唯一令牌源。
"""
from __future__ import annotations

# --- Spacing Scale（对应 ui/design_tokens.SPACE_*） ---
SPACE_XXS = 2
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16

# --- 布局尺寸 ---
# CTk 版侧边栏为 400；Qt 壳左侧另有 FluentWindow 导航栏（约 48px），
# 等宽会挤压主区，故收窄。
SIDEBAR_WIDTH = 300
SEARCH_MIN_WIDTH = 280
USB_COMBO_MIN_WIDTH = 100
LOG_TEXT_HEIGHT = 140

# --- DataGrid ---
GRID_BORDER_RADIUS = 8
# 列宽：程序类型 / 程序名称 / 版本 / 程序归属（程序文件列自动伸展）
# 归属列需容纳「定制专属 · {方案名}」（Issue 20-A），118px 会截断不可读
GRID_COL_WIDTHS = (170, 220, 80, 200)
