from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from fwasset.core.asset_helpers import asset_rom_pkg_files, asset_usb_flow
from fwasset.core.services.flash_service import run_one_click
from fwasset.core.services.music_flash_service import run_music_flash
from fwasset.core.types import FirmwareAsset
from fwasset.core.usb_ops import clean_usb, copy_to_usb, eject_usb, format_usb
from fwasset.ui.design_tokens import (
    BG_HOVER,
    BG_INPUT,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    FONT_FAMILY,
    FONT_SIZE_LG,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from fwasset.ui.operation_panels.base import BaseOperationPanel
from fwasset.ui.operation_panels.registry import register
from fwasset.ui.shared_widgets import make_bool_var


@register("auto_usb")
class AutoUsbPanel(BaseOperationPanel):
    """auto_usb 类型操作面板：U 盘刷机流程。"""

    def build(self):
        self._panel_host._build_usb_selector_row(self)
        self._panel_host._refresh_usb()
        usb_flow = asset_usb_flow(self.asset)
        if usb_flow == "directory_copy":
            self._build_directory_copy_usb_ops()
            return

        rom_file, pkg_file = asset_rom_pkg_files(self.asset)
        if usb_flow == "paired_files" and rom_file and pkg_file:
            ctk.CTkButton(
                self,
                text="一键智能刷机",
                height=48,
                corner_radius=8,
                font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
                fg_color=COLOR_PRIMARY,
                hover_color=COLOR_PRIMARY_HOVER,
                command=self._one_click_handcontrol,
            ).pack(fill="x", padx=20, pady=(10, 8))
            for title, command in [
                ("1. 清理垃圾文件", self._clean_usb),
                ("2. 格式化 FAT32", self._format_usb),
                ("3. 复制文件到 U 盘", self._copy_to_usb),
                ("4. 安全弹出", self._eject_usb),
            ]:
                ctk.CTkButton(
                    self,
                    text=title,
                    height=36,
                    anchor="w",
                    corner_radius=6,
                    fg_color=BG_INPUT,
                    text_color=TEXT_PRIMARY,
                    hover_color=BG_HOVER,
                    command=command,
                ).pack(fill="x", padx=20, pady=3)
            return

        if usb_flow == "paired_files":
            missing = []
            if not rom_file:
                missing.append("ROM")
            if not pkg_file:
                missing.append("PKG")
            ctk.CTkLabel(
                self,
                text=f"当前手控资源缺少 {' / '.join(missing)} 文件，无法执行手控刷机。",
                wraplength=360,
                justify="left",
                font=(FONT_FAMILY, FONT_SIZE_MD),
                text_color=TEXT_SECONDARY,
            ).pack(anchor="w", padx=20, pady=(16, 12))
            return

        ctk.CTkLabel(
            self,
            text="当前 USB 流程未配置，无法确定刷写方式。",
            wraplength=360,
            justify="left",
            font=(FONT_FAMILY, FONT_SIZE_MD),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=20, pady=(16, 12))

    def _build_directory_copy_usb_ops(self):
        """构建目录复制刷机操作区。"""
        self.format_first = make_bool_var(self, True)
        self.eject_after = make_bool_var(self, True)
        options_row = ctk.CTkFrame(self, fg_color="transparent")
        options_row.pack(fill="x", padx=20, pady=(10, 8))
        ctk.CTkCheckBox(
            options_row, text="格式化", variable=self.format_first, font=(FONT_FAMILY, FONT_SIZE_SM)
        ).pack(side="left")
        ctk.CTkCheckBox(
            options_row, text="完成后弹出", variable=self.eject_after, font=(FONT_FAMILY, FONT_SIZE_SM)
        ).pack(side="left", padx=10)
        ctk.CTkButton(
            self,
            text="执行目录刷机流程",
            height=48,
            corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            command=self._run_directory_flash,
        ).pack(fill="x", padx=20, pady=(8, 12))
        ctk.CTkLabel(
            self,
            text="该资源按目录复制到 U 盘，适用于音乐/蓝牙类资源。",
            wraplength=360,
            justify="left",
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=20, pady=(0, 12))

    # -- USB 操作方法 --

    def _clean_usb(self):
        drive = self._panel_host.usb_drive.get().strip()
        if not drive:
            return
        self._panel_host._run_task("清理", lambda log_fn: clean_usb(drive, log_fn))

    def _format_usb(self):
        drive = self._panel_host.usb_drive.get().strip()
        if not drive or not messagebox.askyesno("格式化", f"确认格式化 {drive}?"):
            return
        self._panel_host._run_task("格式化", lambda log_fn: format_usb(drive, log_fn))

    def _copy_to_usb(self):
        asset = self._panel_host._selected_asset()
        drive = self._panel_host.usb_drive.get().strip()
        if not asset or not drive:
            return
        rom_file, pkg_file = asset_rom_pkg_files(asset)
        if not rom_file or not pkg_file:
            return
        rom_path = str(Path(asset["path"]) / rom_file)
        pkg_path = str(Path(asset["path"]) / pkg_file)
        self._panel_host._run_task("复制", lambda log_fn: copy_to_usb(rom_path, pkg_path, drive, log_fn))

    def _eject_usb(self):
        drive = self._panel_host.usb_drive.get().strip()
        if not drive:
            return
        self._panel_host._run_task("弹出", lambda log_fn: eject_usb(drive, log_fn))

    def _one_click_handcontrol(self):
        asset = self._panel_host._selected_asset()
        drive = self._panel_host.usb_drive.get().strip()
        if not asset or not drive:
            return
        rom_file, pkg_file = asset_rom_pkg_files(asset)
        if not rom_file or not pkg_file:
            return
        rom_path = str(Path(asset["path"]) / rom_file)
        pkg_path = str(Path(asset["path"]) / pkg_file)
        self._panel_host._run_task(
            "一键执行",
            lambda log_fn: run_one_click(drive, asset["model"], asset["version"], rom_path, pkg_path, log_fn=log_fn),
        )

    def _run_directory_flash(self):
        asset = self._panel_host._selected_asset()
        drive = self._panel_host.usb_drive.get().strip()
        if not asset or not drive:
            return
        format_first = bool(getattr(self, "format_first", make_bool_var(self, True)).get())
        eject_after = bool(getattr(self, "eject_after", make_bool_var(self, True)).get())
        self._panel_host._run_task(
            "目录刷机",
            lambda log_fn: run_music_flash(
                asset["path"], drive, format_first=format_first, eject_after=eject_after, log_fn=log_fn
            ),
            lambda result: self._log(f"结果: {result.get('message')}"),
        )