from __future__ import annotations

import customtkinter as ctk

from fwasset.ui.design_tokens import BG_INPUT, FONT_FAMILY, FONT_SIZE_MD, TEXT_SECONDARY
from fwasset.ui.operation_panels.base import BaseOperationPanel
from fwasset.ui.operation_panels.registry import register
from fwasset.ui.operation_panels.shared_actions import build_handoff_actions


@register("disabled")
class DisabledPanel(BaseOperationPanel):
    """flash_mode 为空或未知时的默认操作面板。"""

    def build(self):
        ctk.CTkLabel(
            self,
            text=f"{self.asset.get('firmware_label', '该类型')}当前不可自动化操作。",
            justify="left",
            wraplength=360,
            font=(FONT_FAMILY, FONT_SIZE_MD),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=20, pady=(16, 12))
        ctk.CTkButton(
            self,
            text="暂不可操作",
            height=40,
            corner_radius=8,
            fg_color=BG_INPUT,
            text_color=TEXT_SECONDARY,
            hover_color=BG_INPUT,
            state="disabled",
        ).pack(fill="x", padx=20, pady=(0, 12))
        build_handoff_actions(self, self.asset, self._panel_host)