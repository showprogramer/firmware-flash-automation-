from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from fwasset.ui.design_tokens import BG_HOVER, BG_INPUT, FONT_FAMILY, FONT_SIZE_MD, TEXT_SECONDARY
from fwasset.ui.operation_panels.base import BaseOperationPanel
from fwasset.ui.operation_panels.registry import register
from fwasset.ui.operation_panels.shared_actions import build_handoff_actions


@register("manual_doc")
class ManualDocPanel(BaseOperationPanel):
    """manual_doc 类型操作面板：显示说明提示。"""

    def build(self):
        ctk.CTkLabel(
            self,
            text="该类型需要按说明人工处理。",
            justify="left",
            wraplength=360,
            font=(FONT_FAMILY, FONT_SIZE_MD),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=20, pady=(16, 12))
        ctk.CTkButton(
            self,
            text="查看说明",
            height=40,
            corner_radius=8,
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            command=lambda: self._show_manual_doc(self.asset),
        ).pack(fill="x", padx=20, pady=(0, 12))
        build_handoff_actions(self, self.asset, self._panel_host)

    def _show_manual_doc(self, asset):
        message = (
            f"固件类型: {asset.get('firmware_label', '-')}\n"
            f"型号: {asset.get('model', '-')}\n"
            f"版本: {asset.get('version', '-')}\n"
            f"目录: {asset.get('path', '-')}\n\n"
            "当前类型暂未接入自动烧录工具，请按对应工艺说明处理。"
        )
        messagebox.showinfo("操作说明", message)