from __future__ import annotations

import customtkinter as ctk

# ==========================================
# iOS HIG Design Tokens
# ==========================================

# --- Background Layers (Fluent desktop: window -> rail -> surface -> field) ---
BG_WINDOW = ("#F3F6FB", "#111214")
BG_SIDEBAR = ("#F8FAFD", "#1A1B1E")
BG_CARD = ("#FFFFFF", "#25262A")
BG_HOVER = ("#EAF1FB", "#303136")
BG_INPUT = ("#FFFFFF", "#1F2024")

# --- Semantic Colors (iOS HIG system colors) ---
COLOR_PRIMARY = ("#2563EB", "#60A5FA")
COLOR_PRIMARY_HOVER = ("#1D4ED8", "#93C5FD")
COLOR_SUCCESS = ("#34C759", "#30D158")
COLOR_WARNING = ("#FF9500", "#FF9F0A")
COLOR_DANGER = ("#FF3B30", "#FF453A")
COLOR_INFO = ("#5AC8FA", "#64D2FF")

# --- Text Hierarchy ---
TEXT_PRIMARY = ("#111827", "#F9FAFB")
TEXT_SECONDARY = ("#4B5563", "#CBD5E1")
TEXT_TERTIARY = ("#8A94A6", "#7C8494")
TEXT_ON_PRIMARY = ("#FFFFFF", "#FFFFFF")

# --- Borders & Separators ---
BORDER_COLOR = ("#D9E1EC", "#3B3D44")
SEPARATOR = ("#E3E8F0", "#3B3D44")

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
SIDEBAR_WIDTH = 248
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
    hover_bg = BG_HOVER[1] if mode == "Dark" else BG_HOVER[0]
    header_bg = BG_CARD[1] if mode == "Dark" else BG_CARD[0]
    border = SEPARATOR[1] if mode == "Dark" else SEPARATOR[0]
    
    style.configure(
        "Treeview",
        background=bg,
        foreground=fg,
        rowheight=34,
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
        padding=(10, 8),
        font=(FONT_FAMILY, FONT_SIZE_MD, "bold")
    )
    style.map("Treeview.Heading", background=[("active", header_bg)])
    style.configure("Vertical.TScrollbar", troughcolor=bg, background=border, borderwidth=0, arrowcolor=hover_bg)
