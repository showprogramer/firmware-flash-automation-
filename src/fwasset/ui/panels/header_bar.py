from __future__ import annotations

from fwasset.core.types import FirmwareAsset
import customtkinter as ctk

from fwasset.ui.design_tokens import (
    COLOR_PRIMARY,
    FONT_FAMILY,
    FONT_SIZE_MD,
    FONT_SIZE_XL,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class HeaderBar(ctk.CTkFrame):
    """Header bar with model/version/type badges extracted from FirmwareListPanel."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        title_box = ctk.CTkFrame(self, fg_color="transparent")
        title_box.pack(side="left")
        self.model_label = ctk.CTkLabel(
            title_box,
            text="-",
            font=(FONT_FAMILY, FONT_SIZE_XL, "bold"),
            text_color=TEXT_PRIMARY,
        )
        self.model_label.pack(side="left", padx=(0, 12))
        self.version_badge = ctk.CTkLabel(
            title_box,
            text="-",
            fg_color=COLOR_PRIMARY,
            corner_radius=6,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
            text_color="white",
            padx=12,
            pady=4,
        )
        self.version_badge.pack(side="left")
        self.type_badge = ctk.CTkLabel(
            title_box,
            text="未选择",
            fg_color=TEXT_SECONDARY,
            corner_radius=6,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
            text_color="white",
            padx=12,
            pady=4,
        )
        self.type_badge.pack(side="left", padx=8)

    def update_from_asset(self, asset: FirmwareAsset | None) -> None:
        if asset is None:
            self.clear()
            return
        self.model_label.configure(text=str(asset.get("model", "-") or "-"))
        self.version_badge.configure(text=str(asset.get("version", "-") or "-"))
        self.type_badge.configure(
            text=str(asset.get("firmware_label", "未选择")),
            fg_color=COLOR_PRIMARY,
        )

    def clear(self) -> None:
        self.model_label.configure(text="-")
        self.version_badge.configure(text="-")
        self.type_badge.configure(text="未选择", fg_color=TEXT_SECONDARY)