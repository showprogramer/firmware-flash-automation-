from __future__ import annotations

from typing import Any

import tkinter as tk

import customtkinter as ctk
from tkinter import ttk
from fwasset.ui.design_tokens import (
    BG_CARD, BG_HOVER, BG_SIDEBAR, BORDER_COLOR, COLOR_PRIMARY,
    FONT_FAMILY, FONT_SIZE_LG, FONT_SIZE_MD, TEXT_PRIMARY, TEXT_SECONDARY
)


def make_bool_var(master, value: bool) -> Any:
    try:
        return tk.BooleanVar(master=master, value=value)
    except Exception:

        class _LocalVar:
            def __init__(self, initial):
                self._value = bool(initial)

            def get(self):
                return self._value

            def set(self, new_value):
                self._value = bool(new_value)

        return _LocalVar(value)


def card(master, **kwargs) -> ctk.CTkFrame:
    return ctk.CTkFrame(
        master,
        fg_color=BG_CARD,
        corner_radius=12,
        border_width=1,
        border_color=BORDER_COLOR,
        **kwargs
    )


def section_title(master, text: str):
    label = ctk.CTkLabel(
        master,
        text=text,
        font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
        text_color=TEXT_PRIMARY
    )
    label.pack(anchor="w", padx=20, pady=(20, 10))
    return label


def apply_treeview_modern_style():
    mode = ctk.get_appearance_mode()
    is_dark = mode == "Dark"

    bg_color = BG_CARD[1] if is_dark else BG_CARD[0]
    fg_color = TEXT_PRIMARY[1] if is_dark else TEXT_PRIMARY[0]
    selected_bg = COLOR_PRIMARY[1] if is_dark else COLOR_PRIMARY[0]
    heading_bg = BG_SIDEBAR[1] if is_dark else BG_SIDEBAR[0]

    style = ttk.Style()
    style.theme_use("clam")

    style.configure(
        "Modern.Treeview",
        background=bg_color,
        foreground=fg_color,
        fieldbackground=bg_color,
        rowheight=36,
        borderwidth=0,
        font=(FONT_FAMILY, FONT_SIZE_MD)
    )
    style.map("Modern.Treeview", background=[("selected", selected_bg)], foreground=[("selected", "white")])
    style.configure(
        "Modern.Treeview.Heading",
        background=heading_bg,
        foreground=TEXT_SECONDARY[1] if is_dark else TEXT_SECONDARY[0],
        font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
        borderwidth=0,
        padding=8
    )
    style.map("Modern.Treeview.Heading", background=[("active", BG_HOVER[1] if is_dark else BG_HOVER[0])])
