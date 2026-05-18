from __future__ import annotations

from pathlib import Path
from tkinter import messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk

from fwasset.core.types import FirmwareAsset
from fwasset.ui.design_tokens import (
    BG_HOVER,
    BG_INPUT,
    FONT_FAMILY,
    FONT_SIZE_MD,
    HEIGHT_MD,
    HEIGHT_LG,
    RADIUS_SM,
    SPACE_MD,
    SPACE_SM,
    TEXT_PRIMARY,
)

if TYPE_CHECKING:
    from fwasset.ui.operation_panels.host_types import PanelHost


def build_handoff_actions(
    panel, asset: FirmwareAsset, panel_host: PanelHost, include_tool_combo: bool = False
):
    """构建通用的交接操作按钮组（打开目录、复制路径等）。"""
    action_frame = ctk.CTkFrame(panel, fg_color="transparent")
    action_frame.pack(fill="x", padx=20, pady=(0, SPACE_MD))

    for title, command in [
        ("打开程序目录", panel_host._open_current_asset_dir),
        ("复制目录路径", panel_host._copy_asset_dir_path),
        ("复制主文件路径", panel_host._copy_primary_file_path),
    ]:
        ctk.CTkButton(
            action_frame,
            text=title,
            height=HEIGHT_MD,
            corner_radius=RADIUS_SM,
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            command=command,
        ).pack(fill="x", pady=SPACE_SM)

    if include_tool_combo:
        ctk.CTkButton(
            action_frame,
            text="打开工具 + 打开程序目录",
            height=HEIGHT_LG,
            corner_radius=RADIUS_SM,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            command=panel_host._launch_tool_and_open_asset_dir,
        ).pack(fill="x", pady=(SPACE_SM, 0))