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
    FONT_SIZE_LG,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    HEIGHT_LG,
    RADIUS_SM,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
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

        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(fill="x", padx=SPACE_LG, pady=(SPACE_LG, SPACE_SM))

        ctk.CTkLabel(
            info_frame,
            text=f"工具类型: {tool_name}",
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
        ).pack(anchor="w")

        path_text = tool_path if tool_path else "未配置工具路径"
        path_color = TEXT_SECONDARY if tool_path else COLOR_DANGER
        self.tool_path_label = ctk.CTkLabel(
            info_frame,
            text=f"路径: {path_text}",
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=path_color,
            wraplength=360,
        )
        self.tool_path_label.pack(anchor="w", pady=(SPACE_SM, 0))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=SPACE_LG, pady=(SPACE_SM, SPACE_MD))

        ctk.CTkButton(
            btn_frame,
            text="打开烧录工具",
            height=HEIGHT_LG,
            corner_radius=RADIUS_SM,
            font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            state="normal" if tool_path else "disabled",
            command=self._launch_current_tool,
        ).pack(fill="x", pady=(0, SPACE_SM))

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