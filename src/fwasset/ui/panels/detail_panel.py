from __future__ import annotations

from datetime import datetime

import customtkinter as ctk

from fwasset.core.types import FirmwareAsset
from fwasset.ui.design_tokens import (
    BG_CARD,
    FONT_FAMILY,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    RADIUS_LG,
    SPACE_LG,
    SPACE_SM,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from fwasset.ui.shared_widgets import section_title

DETAIL_FIELDS = [
    ("系列", "series"),
    ("型号", "model"),
    ("版本", "version"),
    ("固件类型", "firmware_type"),
    ("刷写方式", "flash_mode"),
    ("目录名", "directory_name"),
    ("原始路径", "path"),
    ("文件清单", "files"),
    ("修改时间", "modified_time"),
]


class DetailPanel(ctk.CTkFrame):
    """Resource detail card extracted from FirmwareListPanel."""

    def __init__(self, master, **kwargs):
        fg = kwargs.pop("fg_color", BG_CARD)
        super().__init__(master, fg_color=fg, corner_radius=RADIUS_LG, **kwargs)
        section_title(self, "资源详情")
        self.detail_values: dict[str, ctk.CTkLabel] = {}
        for label_text, key in DETAIL_FIELDS:
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=SPACE_LG, pady=SPACE_SM)
            ctk.CTkLabel(
                row,
                text=label_text,
                width=88,
                anchor="w",
                font=(FONT_FAMILY, FONT_SIZE_SM),
                text_color=TEXT_SECONDARY,
            ).pack(side="left")
            value = ctk.CTkLabel(
                row,
                text="-",
                anchor="w",
                justify="left",
                wraplength=520,
                font=(FONT_FAMILY, FONT_SIZE_MD),
                text_color=TEXT_PRIMARY,
            )
            value.pack(side="left", fill="x", expand=True, padx=(SPACE_SM, 0))
            self.detail_values[key] = value

    def update_from_asset(self, asset: FirmwareAsset | None) -> None:
        if asset is None:
            self.clear()
            return
        modified_time = "-"
        if asset.get("modified_time"):
            try:
                modified_time = datetime.fromtimestamp(float(asset["modified_time"])).strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, OSError, OverflowError):
                modified_time = "-"
        details = {
            "series": str(asset.get("series", "") or "-"),
            "model": str(asset.get("model", "") or "-"),
            "version": str(asset.get("version", "") or "-"),
            "firmware_type": str(asset.get("firmware_label", "") or "-"),
            "flash_mode": str(asset.get("flash_mode", "") or "-"),
            "directory_name": str(asset.get("directory_name", "") or "-"),
            "path": str(asset.get("path", "") or "-"),
            "files": "\n".join(asset.get("files", [])[:8]) or "-",
            "modified_time": modified_time,
        }
        for key, value in details.items():
            self.detail_values[key].configure(text=value)

    def clear(self) -> None:
        for value in self.detail_values.values():
            value.configure(text="-")