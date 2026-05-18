from __future__ import annotations

from typing import Any

import tkinter as tk

import customtkinter as ctk
from fwasset.ui.design_tokens import (
    BG_CARD, BG_HOVER, BORDER_COLOR, FONT_FAMILY, FONT_SIZE_MD,
    RADIUS_LG, SPACE_LG, SPACE_MD, TEXT_PRIMARY, TEXT_SECONDARY,
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
        corner_radius=RADIUS_LG,
        border_width=0,
        **kwargs
    )


def section_title(master, text: str):
    label = ctk.CTkLabel(
        master,
        text=text,
        font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
        text_color=TEXT_SECONDARY
    )
    label.pack(anchor="w", padx=SPACE_LG, pady=(SPACE_LG, SPACE_MD))
    return label