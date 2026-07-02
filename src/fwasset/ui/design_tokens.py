from __future__ import annotations

import customtkinter as ctk

# ==========================================
# iOS HIG Design Tokens
# ==========================================

# --- Background Layers (iOS: window → sidebar → card → input) ---
BG_WINDOW = ("#F2F2F7", "#000000")
BG_SIDEBAR = ("#FFFFFF", "#1C1C1E")
BG_CARD = ("#FFFFFF", "#2C2C2E")
BG_HOVER = ("#F2F2F7", "#3A3A3C")
BG_INPUT = ("#F2F2F7", "#1C1C1E")

# --- Semantic Colors (iOS HIG system colors) ---
COLOR_PRIMARY = ("#007AFF", "#0A84FF")
COLOR_PRIMARY_HOVER = ("#0066CC", "#409CFF")
COLOR_SUCCESS = ("#34C759", "#30D158")
COLOR_WARNING = ("#FF9500", "#FF9F0A")
COLOR_DANGER = ("#FF3B30", "#FF453A")
COLOR_INFO = ("#5AC8FA", "#64D2FF")

# --- Text Hierarchy ---
TEXT_PRIMARY = ("#000000", "#FFFFFF")
TEXT_SECONDARY = ("#8E8E93", "#8E8E93")
TEXT_TERTIARY = ("#C7C7CC", "#48484A")
TEXT_ON_PRIMARY = ("#FFFFFF", "#FFFFFF")

# --- Borders & Separators ---
BORDER_COLOR = ("#E5E5EA", "#38383A")
SEPARATOR = ("#C6C6C8", "#48484A")

# --- Font System ---
FONT_FAMILY = "Segoe UI"
FONT_MONO = "Consolas"
FONT_SIZE_DISPLAY = 34
FONT_SIZE_XL = 28
FONT_SIZE_LG = 17
FONT_SIZE_MD = 14
FONT_SIZE_SM = 13
FONT_SIZE_XS = 11

# --- Spacing Scale (8pt grid) ---
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24
SPACE_2XL = 32
SPACE_3XL = 48

# --- Border Radius ---
RADIUS_SM = 8
RADIUS_MD = 10
RADIUS_LG = 14
RADIUS_XL = 20

# --- Control Heights ---
HEIGHT_SM = 30
HEIGHT_MD = 36
HEIGHT_LG = 44
HEIGHT_XL = 50

# --- Icon Sizes ---
ICON_SM = 16
ICON_MD = 20
ICON_LG = 24
ICON_XL = 32

# --- Layout Constants ---
SIDEBAR_WIDTH = 400
MAIN_MIN_WIDTH = 600

# --- Legacy aliases (deprecated, use FONT_SIZE_* instead) ---
FONT_XL = FONT_SIZE_XL
FONT_LG = FONT_SIZE_LG
FONT_MD = FONT_SIZE_MD
FONT_SM = FONT_SIZE_SM

def apply_ttk_theme():
    """Apply CustomTkinter-compatible flat theme to ttk widgets (like Treeview)."""
    import tkinter.ttk as ttk
    
    style = ttk.Style()
    style.theme_use("default")
    
    mode = ctk.get_appearance_mode()
    
    bg = BG_CARD[1] if mode == "Dark" else BG_CARD[0]
    fg = TEXT_PRIMARY[1] if mode == "Dark" else TEXT_PRIMARY[0]
    select_bg = COLOR_PRIMARY[1] if mode == "Dark" else COLOR_PRIMARY[0]
    select_fg = TEXT_ON_PRIMARY[1] if mode == "Dark" else TEXT_ON_PRIMARY[0]
    header_bg = BG_WINDOW[1] if mode == "Dark" else BG_WINDOW[0]
    
    style.configure(
        "Treeview",
        background=bg,
        foreground=fg,
        rowheight=36,
        fieldbackground=bg,
        borderwidth=0,
        font=(FONT_FAMILY, FONT_SIZE_MD)
    )
    style.map(
        "Treeview",
        background=[("selected", select_bg)],
        foreground=[("selected", select_fg)]
    )
    style.configure(
        "Treeview.Heading",
        background=header_bg,
        foreground=fg,
        relief="flat",
        borderwidth=0,
        font=(FONT_FAMILY, FONT_SIZE_MD, "bold")
    )
    style.map("Treeview.Heading", background=[("active", header_bg)])