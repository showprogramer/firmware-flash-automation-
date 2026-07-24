from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from fwasset.core.firmware_catalog import load_firmware_catalog
from fwasset.core.tool_discovery import discover_tool_path, launch_tool
from fwasset.ui.design_tokens import (
    COLOR_DANGER,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    FONT_FAMILY,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    HEIGHT_MD,
    RADIUS_SM,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from fwasset.ui.operation_panels.base import BaseOperationPanel
from fwasset.ui.operation_panels.registry import register


@register("tool_launch")
class ToolLaunchPanel(BaseOperationPanel):
    """tool_launch 类型操作面板：展示并启动外部烧录工具。"""

    def build(self):
        fw_type = str(self.asset.get("firmware_type", ""))
        tool_name = str(self.asset.get("tool_name", "")) or "烧录工具"
        tool_dir = str(self.asset.get("tool_dir", ""))

        catalog = load_firmware_catalog()
        tool_path = ""
        dir_keywords: list[str] = []
        for item in catalog.get("firmware_types", []):
            if item.get("key") == fw_type:
                tool_path = item.get("tool_path", "")
                tool_dir = item.get("tool_dir", tool_dir)
                dir_keywords = item.get("dir_keywords", [])
                break

        if not tool_path:
            tool_path = discover_tool_path(
                fw_type,
                tool_name,
                tool_dir=tool_dir,
                dir_keywords=dir_keywords,
            )

        self._current_tool_path = tool_path

        action_row = ctk.CTkFrame(self, fg_color="transparent")
        action_row.pack(fill="x", padx=SPACE_LG, pady=(SPACE_SM, SPACE_SM))
        action_row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            action_row,
            text=tool_name,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=(0, SPACE_MD))

        path_text = tool_path if tool_path else "未配置工具路径"
        path_color = TEXT_SECONDARY if tool_path else COLOR_DANGER

        ctk.CTkButton(
            action_row,
            text="打开烧录工具",
            width=150,
            height=HEIGHT_MD,
            corner_radius=RADIUS_SM,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            state="normal" if tool_path else "disabled",
            command=self._launch_current_tool,
        ).grid(row=0, column=1, sticky="e")

        self.tool_path_label = ctk.CTkLabel(
            self,
            text=path_text,
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=path_color,
            wraplength=760,
        )
        self.tool_path_label.pack(anchor="w", padx=SPACE_LG, pady=(0, SPACE_SM))

        # 精简操作区：不再渲染复制路径 / U 盘那一排（双击行即可开目录）。

        if not tool_path:
            ctk.CTkLabel(
                self,
                text="提示: 将烧录工具放在程序同目录的 tools 文件夹中，程序会自动发现。",
                wraplength=360,
                justify="left",
                font=(FONT_FAMILY, FONT_SIZE_SM),
                text_color=TEXT_SECONDARY,
            ).pack(anchor="w", padx=SPACE_LG, pady=(0, SPACE_MD))

    def _launch_current_tool(self):
        """启动当前选中的工具。"""
        tool_path = getattr(self, "_current_tool_path", "")
        if not tool_path:
            messagebox.showwarning(
                "提示",
                "工具路径未配置\n\n请将烧录工具放在程序同目录的 tools 文件夹中，或手动配置工具路径。",
            )
            return

        result = launch_tool(tool_path)
        if result.get("ok"):
            self._log(f"✓ {result.get('message')}")
        else:
            messagebox.showerror("启动失败", result.get("message", ""))
            self._log(f"✗ {result.get('message')}")

    def _launch_tool_and_open_asset_dir(self):
        self._launch_current_tool()
        self._panel_host._open_current_asset_dir()
