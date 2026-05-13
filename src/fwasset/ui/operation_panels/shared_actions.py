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
    TEXT_PRIMARY,
)

if TYPE_CHECKING:
    from fwasset.ui.operation_panels.host_types import PanelHost


def build_handoff_actions(
    panel, asset: FirmwareAsset, panel_host: PanelHost, include_tool_combo: bool = False
):
    """构建通用的交接操作按钮组（打开目录、复制路径等）。

    Args:
        panel: 放置按钮的父级 CTkFrame。
        asset: 当前选中的固件资产。
        panel_host: 提供 _open_current_asset_dir, _copy_asset_dir_path,
                     _copy_primary_file_path, _launch_tool_and_open_asset_dir 的宿主。
        include_tool_combo: 是否显示"打开工具 + 打开程序目录"组合按钮。
    """
    action_frame = ctk.CTkFrame(panel, fg_color="transparent")
    action_frame.pack(fill="x", padx=20, pady=(0, 12))

    for title, command in [
        ("打开程序目录", panel_host._open_current_asset_dir),
        ("复制目录路径", panel_host._copy_asset_dir_path),
        ("复制主文件路径", panel_host._copy_primary_file_path),
    ]:
        ctk.CTkButton(
            action_frame,
            text=title,
            height=36,
            corner_radius=6,
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            command=command,
        ).pack(fill="x", pady=3)

    if include_tool_combo:
        ctk.CTkButton(
            action_frame,
            text="打开工具 + 打开程序目录",
            height=40,
            corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            command=panel_host._launch_tool_and_open_asset_dir,
        ).pack(fill="x", pady=(6, 0))