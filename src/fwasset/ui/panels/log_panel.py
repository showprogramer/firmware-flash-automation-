from __future__ import annotations

import customtkinter as ctk

from fwasset.ui.design_tokens import (
    BG_CARD,
    BG_INPUT,
    BG_HOVER,
    FONT_FAMILY,
    FONT_SIZE_MD,
    TEXT_PRIMARY,
)
from fwasset.ui.shared_widgets import section_title


class LogPanel(ctk.CTkFrame):
    """Collapsible log panel extracted from FirmwareListPanel."""

    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=12, fg_color=BG_CARD, **kwargs)
        self._collapsed = True
        section_title(self, "运行日志")
        self.log_text = ctk.CTkTextbox(
            self,
            font=("Consolas", FONT_SIZE_MD),
            fg_color=BG_INPUT,
            corner_radius=8,
        )
        self.log_toggle_btn = ctk.CTkButton(
            self,
            text="展开日志",
            width=96,
            height=30,
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            command=self.toggle,
        )
        self.log_toggle_btn.pack(anchor="e", padx=20, pady=(0, 10))
        self._apply_collapsed_state()

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self._apply_collapsed_state()

    def toggle(self) -> None:
        self.set_collapsed(not self._collapsed)

    def write(self, message: str) -> None:
        self.log_text.insert("end", message.rstrip("\n") + "\n")
        self.log_text.see("end")

    def _apply_collapsed_state(self) -> None:
        if self._collapsed:
            if hasattr(self.log_text, "pack_forget"):
                self.log_text.pack_forget()
            self.log_toggle_btn.configure(text="展开日志")
        else:
            self.log_text.pack(fill="both", expand=True, padx=20, pady=(0, 20))
            self.log_toggle_btn.configure(text="折叠日志")