from __future__ import annotations

import os
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from fwasset.core.firmware_catalog import enabled_firmware_types
from fwasset.core.services.flash_service import run_one_click
from fwasset.core.services.music_flash_service import run_music_flash
from fwasset.core.services.scan_service import build_scan_result
from fwasset.core.settings import DEFAULT_ROOT
from fwasset.core.sort_config import SortKey, apply_sort
from fwasset.core.types import FirmwareAsset
from fwasset.core.usb_ops import clean_usb, copy_to_usb, eject_usb, format_usb
from fwasset.ui.base_panel import BaseFlashPanel
from fwasset.ui.design_tokens import (
    BG_CARD,
    BG_HOVER,
    BG_INPUT,
    BORDER_COLOR,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    FONT_FAMILY,
    FONT_SIZE_LG,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    FONT_SIZE_XL,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from fwasset.ui.serial_control import SerialControl
from fwasset.ui.shared_widgets import section_title


class FirmwareListPanel(BaseFlashPanel):
    def __init__(self, master):
        super().__init__(master)
        self.root_dir = tk.StringVar(value=DEFAULT_ROOT)
        self.search_var = tk.StringVar(value="")
        self.sort_key_var = tk.StringVar(value="默认(名称)")
        self.sort_asc_var = tk.BooleanVar(value=True)
        self.type_filter_vars = {
            item["key"]: tk.BooleanVar(value=True)
            for item in enabled_firmware_types()
        }
        self.assets: list[FirmwareAsset] = []
        self.folders: list[dict] = []
        self._all_assets: list[FirmwareAsset] = []
        self._selected_idx = -1
        self._asset_card_widgets: list[dict] = []

        self.grid_columnconfigure(0, weight=0, minsize=440)
        self.grid_columnconfigure(1, weight=1)
        self._build_sidebar()
        self._build_main_view()
        self._refresh_usb()
        self.search_var.trace_add("write", lambda *_: self._filter_assets())

    def _make_bool_var(self, value: bool):
        try:
            return tk.BooleanVar(master=self, value=value)
        except Exception:
            class _LocalVar:
                def __init__(self, initial):
                    self._value = bool(initial)

                def get(self):
                    return self._value

                def set(self, new_value):
                    self._value = bool(new_value)

            return _LocalVar(value)

    def activate(self):
        super().activate()
        if hasattr(self, "serial_control") and self.serial_control is not None and self._selected_flash_mode() == "auto_serial":
            self.serial_control.activate()

    def deactivate(self):
        super().deactivate()
        if hasattr(self, "serial_control") and self.serial_control is not None:
            self.serial_control.deactivate()

    def _build_sidebar(self):
        sidebar = self._build_sidebar_frame(width=440)
        self._build_brand_header(sidebar, title="固件资源列表")

        search_sort_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        search_sort_frame.pack(fill="x", padx=20, pady=(0, 12))

        search_box = ctk.CTkEntry(
            search_sort_frame,
            height=36,
            corner_radius=8,
            placeholder_text="搜索 型号/版本/类型/目录",
            textvariable=self.search_var,
            fg_color=BG_CARD,
            border_width=1,
            border_color=BORDER_COLOR,
            font=(FONT_FAMILY, FONT_SIZE_MD),
        )
        search_box.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.sort_menu = ctk.CTkOptionMenu(
            search_sort_frame,
            values=["默认(名称)", "按型号", "按版本"],
            variable=self.sort_key_var,
            width=100,
            height=36,
            corner_radius=8,
            fg_color=BG_CARD,
            text_color=TEXT_PRIMARY,
            button_color=BG_CARD,
            button_hover_color=BG_HOVER,
            font=(FONT_FAMILY, FONT_SIZE_MD),
            command=lambda _value: self._filter_assets(),
        )
        self.sort_menu.pack(side="right")

        filter_card = ctk.CTkFrame(sidebar, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER_COLOR)
        filter_card.pack(fill="x", padx=20, pady=(0, 12))
        
        filter_header = ctk.CTkFrame(filter_card, fg_color="transparent")
        filter_header.pack(fill="x", padx=20, pady=(16, 8))
        
        ctk.CTkLabel(
            filter_header,
            text="固件类型筛选",
            font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(side="left")
        
        ctk.CTkButton(
            filter_header,
            text="清空",
            width=50,
            height=26,
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            command=self._clear_type_filters,
        ).pack(side="right")
        
        ctk.CTkButton(
            filter_header,
            text="全选",
            width=50,
            height=26,
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            command=self._select_all_type_filters,
        ).pack(side="right", padx=(0, 8))
        
        self.filter_frame = ctk.CTkScrollableFrame(filter_card, fg_color="transparent", height=180)
        self.filter_frame.pack(fill="x", padx=10, pady=(0, 12))
        self._render_type_filters()

        list_title = ctk.CTkFrame(sidebar, fg_color="transparent")
        list_title.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkLabel(
            list_title,
            text="资源条目",
            font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(side="left")
        ctk.CTkButton(
            list_title,
            text="扫描根目录",
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            width=96,
            command=self._choose_root_and_scan,
        ).pack(side="right")

        self.list_scroll = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        self.list_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _select_all_type_filters(self):
        for var in self.type_filter_vars.values():
            var.set(True)
        self._filter_assets()

    def _clear_type_filters(self):
        for var in self.type_filter_vars.values():
            var.set(False)
        self._filter_assets()

    def _build_main_view(self):
        main = self._build_main_container()
        self._build_header(main)
        cards_container = ctk.CTkFrame(main, fg_color="transparent")
        cards_container.grid(row=1, column=0, sticky="nsew", pady=(0, 24))
        cards_container.grid_columnconfigure(0, weight=5)
        cards_container.grid_columnconfigure(1, weight=4)
        cards_container.grid_rowconfigure(0, weight=1)

        self.detail_card = ctk.CTkFrame(
            cards_container,
            fg_color=BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.detail_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        section_title(self.detail_card, "资源详情")
        self.detail_values: dict[str, ctk.CTkLabel] = {}
        for label_text, key in [
            ("型号", "model"),
            ("版本", "version"),
            ("固件类型", "firmware_type"),
            ("刷写方式", "flash_mode"),
            ("目录名", "directory_name"),
            ("原始路径", "path"),
            ("文件清单", "files"),
            ("修改时间", "modified_time"),
        ]:
            row = ctk.CTkFrame(self.detail_card, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=4)
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
            value.pack(side="left", fill="x", expand=True, padx=(8, 0))
            self.detail_values[key] = value

        self.ops_card = ctk.CTkFrame(
            cards_container,
            fg_color=BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.ops_card.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        section_title(self.ops_card, "操作区")
        self.ops_body = ctk.CTkFrame(self.ops_card, fg_color="transparent")
        self.ops_body.pack(fill="both", expand=True, padx=0, pady=(0, 10))
        self.serial_control = None
        self._render_operation_panel(None)

        panel = ctk.CTkFrame(main, corner_radius=12, fg_color=BG_CARD)
        panel.grid(row=2, column=0, sticky="nsew")
        section_title(panel, "运行日志")
        self.log_text = ctk.CTkTextbox(panel, font=("Consolas", FONT_SIZE_MD), fg_color=BG_INPUT, corner_radius=8)
        self.log_text.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    def _build_header(self, parent):
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 24))
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left")
        self.header_model_label = ctk.CTkLabel(
            title_box,
            text="-",
            font=(FONT_FAMILY, FONT_SIZE_XL, "bold"),
            text_color=TEXT_PRIMARY,
        )
        self.header_model_label.pack(side="left", padx=(0, 12))
        self.header_version_badge = ctk.CTkLabel(
            title_box,
            text="-",
            fg_color=COLOR_PRIMARY,
            corner_radius=6,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
            text_color="white",
            padx=12,
            pady=4,
        )
        self.header_version_badge.pack(side="left")
        self.header_type_badge = ctk.CTkLabel(
            title_box,
            text="未选择",
            fg_color=TEXT_SECONDARY,
            corner_radius=6,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
            text_color="white",
            padx=12,
            pady=4,
        )
        self.header_type_badge.pack(side="left", padx=8)

    def _render_type_filters(self):
        for widget in self.filter_frame.winfo_children():
            widget.destroy()
        for item in enabled_firmware_types():
            var = self.type_filter_vars[item["key"]]
            ctk.CTkCheckBox(
                self.filter_frame,
                text=item["label"],
                variable=var,
                font=(FONT_FAMILY, FONT_SIZE_SM),
                command=self._filter_assets,
            ).pack(anchor="w", padx=8, pady=4)

    def _selected_types(self) -> set[str]:
        return {key for key, value in self.type_filter_vars.items() if bool(value.get())}

    def _choose_root_and_scan(self):
        initial_dir = self.root_dir.get().strip() or str(Path.cwd())
        selected = filedialog.askdirectory(initialdir=initial_dir)
        if not selected:
            return
        self.root_dir.set(selected)
        self._scan()

    def _scan(self):
        root = self.root_dir.get().strip()
        if not root:
            messagebox.showwarning("提示", "请先选择程序根目录")
            return

        def _work(log_fn):
            return build_scan_result(root, log_fn=log_fn)

        def _done(result):
            if not result.get("ok"):
                messagebox.showerror("扫描失败", str(result.get("message", "未知错误")))
                return
            payload = result.get("payload", {}) or {}
            self._all_assets = list(payload.get("assets", []))
            self._selected_idx = -1
            self._filter_assets()

        self._run_task("扫描目录", _work, _done)

    def _sort_assets(self, items: list[FirmwareAsset]) -> list[FirmwareAsset]:
        sort_key = SortKey.PATH
        if self.sort_key_var.get() == "按型号":
            sort_key = SortKey.MODEL
        elif self.sort_key_var.get() == "按版本":
            sort_key = SortKey.VERSION
        return apply_sort(items, sort_key=sort_key, ascending=bool(self.sort_asc_var.get()))

    def _filter_assets(self):
        keyword = self.search_var.get().strip().lower()
        selected_types = self._selected_types()
        filtered: list[FirmwareAsset] = []
        for item in self._all_assets:
            if item.get("firmware_type") not in selected_types:
                continue
            if keyword:
                haystack = " ".join(
                    [
                        str(item.get("model", "") or ""),
                        str(item.get("version", "") or ""),
                        str(item.get("firmware_label", "") or ""),
                        str(item.get("directory_name", "") or ""),
                        str(item.get("path", "") or ""),
                        str(item.get("flash_mode", "") or ""),
                    ]
                ).lower()
                if keyword not in haystack:
                    continue
            filtered.append(item)

        self.assets = self._sort_assets(filtered)
        self.folders = self.assets
        self._render_asset_cards()

    def _render_asset_cards(self):
        self._asset_card_widgets = []
        for widget in self.list_scroll.winfo_children():
            widget.destroy()
        for idx, item in enumerate(self.assets):
            self._create_sidebar_item(idx, item)
        if self.assets:
            next_idx = min(max(self._selected_idx, 0), len(self.assets) - 1)
            self._select_asset(next_idx)
        else:
            self._selected_idx = -1
            self._clear_selection()

    def _selected_card_colors(self):
        return {
            "card_fg": COLOR_PRIMARY,
            "border_color": COLOR_PRIMARY_HOVER,
            "title_text": "white",
            "meta_text": "#EAF2FF",
        }

    def _unselected_card_colors(self):
        return {
            "card_fg": "transparent",
            "border_color": BORDER_COLOR,
            "title_text": TEXT_PRIMARY,
            "meta_text": TEXT_SECONDARY,
        }

    def _apply_card_visual_state(self, idx: int, selected: bool):
        if idx < 0 or idx >= len(self._asset_card_widgets):
            return
        widgets = self._asset_card_widgets[idx]
        palette = self._selected_card_colors() if selected else self._unselected_card_colors()
        widgets["card"].configure(fg_color=palette["card_fg"], border_color=palette["border_color"])
        widgets["title_label"].configure(text_color=palette["title_text"])
        widgets["meta_label"].configure(text_color=palette["meta_text"])
        widgets["type_label"].configure(text_color=palette["meta_text"])

    def _create_sidebar_item(self, idx: int, item: FirmwareAsset):
        is_selected = idx == self._selected_idx
        palette = self._selected_card_colors() if is_selected else self._unselected_card_colors()
        card_item = ctk.CTkFrame(
            self.list_scroll,
            fg_color=palette["card_fg"],
            corner_radius=10,
            height=84,
            cursor="hand2",
            border_width=1,
            border_color=palette["border_color"],
        )
        card_item.pack(fill="x", pady=4, padx=8)
        card_item.pack_propagate(False)

        text_area = ctk.CTkFrame(card_item, fg_color="transparent")
        text_area.pack(fill="both", expand=True, padx=14, pady=10)

        row1 = ctk.CTkFrame(text_area, fg_color="transparent")
        row1.pack(fill="x")
        title_label = ctk.CTkLabel(
            row1,
            text=f"{item.get('model', '')} • {item.get('version', '') or '-'}",
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
            text_color=palette["title_text"],
        )
        title_label.pack(side="left")
        type_label = ctk.CTkLabel(
            row1,
            text=f"{item.get('firmware_label', '')} / {item.get('flash_mode', '')}",
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=palette["meta_text"],
        )
        type_label.pack(side="right")

        meta_label = ctk.CTkLabel(
            text_area,
            text=f"{item.get('directory_name', '')}  [{item.get('firmware_type', '')}]",
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=palette["meta_text"],
            anchor="w",
        )
        meta_label.pack(fill="x", pady=(4, 0))

        for widget in [card_item, text_area, row1, title_label, type_label, meta_label]:
            widget.bind("<Button-1>", lambda _event, i=idx: self._select_asset(i))
            widget.bind("<Double-Button-1>", lambda _event, i=idx: self._open_asset_path(i))

        self._asset_card_widgets.append(
            {
                "card": card_item,
                "title_label": title_label,
                "meta_label": meta_label,
                "type_label": type_label,
            }
        )

    def _clear_selection(self):
        self.header_model_label.configure(text="-")
        self.header_version_badge.configure(text="-")
        self.header_type_badge.configure(text="未选择", fg_color=TEXT_SECONDARY)
        for value in self.detail_values.values():
            value.configure(text="-")
        self._render_operation_panel(None)

    def _select_asset(self, idx: int):
        if idx < 0 or idx >= len(self.assets):
            return
        previous_idx = self._selected_idx
        self._selected_idx = idx
        if previous_idx != idx:
            self._apply_card_visual_state(previous_idx, False)
            self._apply_card_visual_state(idx, True)

        asset = self.assets[idx]
        self.header_model_label.configure(text=asset.get("model", "-"))
        self.header_version_badge.configure(text=asset.get("version", "-") or "-")
        self.header_type_badge.configure(text=asset.get("firmware_label", "未选择"), fg_color=COLOR_PRIMARY)
        self._update_detail_panel(asset)
        self._render_operation_panel(asset)
        self._log(f"已选择: {asset.get('model', '')} {asset.get('version', '')} [{asset.get('firmware_label', '')}]")

    def _update_detail_panel(self, asset: FirmwareAsset):
        modified_time = "-"
        if asset.get("modified_time"):
            modified_time = datetime.fromtimestamp(float(asset["modified_time"])).strftime("%Y-%m-%d %H:%M:%S")
        details = {
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

    def _open_asset_path(self, idx: int):
        if idx < 0 or idx >= len(self.assets):
            return
        path_obj = Path(str(self.assets[idx].get("path", "")))
        if not path_obj.exists():
            messagebox.showerror("错误", f"路径不存在: {path_obj}")
            return
        try:
            os.startfile(str(path_obj.resolve()))
        except OSError as exc:
            messagebox.showerror("错误", f"打开目录失败: {exc}")

    def _selected_asset(self) -> FirmwareAsset | None:
        if self._selected_idx < 0 or self._selected_idx >= len(self.assets):
            messagebox.showwarning("提示", "请先选择一个条目")
            return None
        return self.assets[self._selected_idx]

    def _selected_flash_mode(self) -> str:
        if self._selected_idx < 0 or self._selected_idx >= len(self.assets):
            return ""
        return str(self.assets[self._selected_idx].get("flash_mode", ""))

    def _asset_rom_pkg_files(self, asset: FirmwareAsset) -> tuple[str, str]:
        rom_file = next((name for name in asset.get("files", []) if name.lower().endswith(".rom")), "")
        pkg_file = next((name for name in asset.get("files", []) if name.lower().endswith(".pkg")), "")
        return rom_file, pkg_file

    def _reset_ops_body(self):
        if self.serial_control is not None:
            self.serial_control.deactivate()
            self.serial_control.destroy()
            self.serial_control = None
        for widget in self.ops_body.winfo_children():
            widget.destroy()

    def _render_operation_panel(self, asset: FirmwareAsset | None):
        self._reset_ops_body()
        if asset is None:
            ctk.CTkLabel(
                self.ops_body,
                text="选择资源后显示对应操作",
                font=(FONT_FAMILY, FONT_SIZE_MD),
                text_color=TEXT_SECONDARY,
            ).pack(anchor="w", padx=20, pady=20)
            return

        flash_mode = str(asset.get("flash_mode", ""))
        if flash_mode == "auto_usb":
            self._build_auto_usb_ops(asset)
        elif flash_mode == "auto_serial":
            self.serial_control = SerialControl(self.ops_body, log_fn=self._log)
            self.serial_control.pack(fill="both", expand=True)
            if self._polling_active:
                self.serial_control.activate()
        elif flash_mode == "tool_launch":
            self._render_placeholder_ops("该类型当前为工具启动模式，后续接入工具中心。")
        elif flash_mode == "manual_doc":
            self._render_placeholder_ops("该类型当前为说明模式，后续接入文档查看入口。")
        else:
            self._render_placeholder_ops("该类型当前不可自动化操作。")

    def _render_placeholder_ops(self, text: str):
        ctk.CTkLabel(
            self.ops_body,
            text=text,
            justify="left",
            wraplength=360,
            font=(FONT_FAMILY, FONT_SIZE_MD),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=20, pady=20)

    def _build_auto_usb_ops(self, asset: FirmwareAsset):
        self._build_usb_selector_row(self.ops_body)
        self._refresh_usb()
        rom_file, pkg_file = self._asset_rom_pkg_files(asset)
        if rom_file and pkg_file:
            ctk.CTkButton(
                self.ops_body,
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
                    self.ops_body,
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

        self.format_first = self._make_bool_var(True)
        self.eject_after = self._make_bool_var(True)
        options_row = ctk.CTkFrame(self.ops_body, fg_color="transparent")
        options_row.pack(fill="x", padx=20, pady=(10, 8))
        ctk.CTkCheckBox(options_row, text="格式化", variable=self.format_first, font=(FONT_FAMILY, FONT_SIZE_SM)).pack(side="left")
        ctk.CTkCheckBox(options_row, text="完成后弹出", variable=self.eject_after, font=(FONT_FAMILY, FONT_SIZE_SM)).pack(side="left", padx=10)
        ctk.CTkButton(
            self.ops_body,
            text="执行目录刷机流程",
            height=48,
            corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            command=self._run_directory_flash,
        ).pack(fill="x", padx=20, pady=(8, 12))
        ctk.CTkLabel(
            self.ops_body,
            text="该资源按目录复制到 U 盘，适用于音乐/蓝牙类资源。",
            wraplength=360,
            justify="left",
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=20, pady=(0, 12))

    def _clean_usb(self):
        drive = self.usb_drive.get().strip()
        if not drive:
            return
        self._run_task("清理", lambda log_fn: clean_usb(drive, log_fn))

    def _format_usb(self):
        drive = self.usb_drive.get().strip()
        if not drive or not messagebox.askyesno("格式化", f"确认格式化 {drive}?"):
            return
        self._run_task("格式化", lambda log_fn: format_usb(drive, log_fn))

    def _copy_to_usb(self):
        asset = self._selected_asset()
        drive = self.usb_drive.get().strip()
        if not asset or not drive:
            return
        rom_file, pkg_file = self._asset_rom_pkg_files(asset)
        if not rom_file or not pkg_file:
            return
        rom_path = str(Path(asset["path"]) / rom_file)
        pkg_path = str(Path(asset["path"]) / pkg_file)
        self._run_task("复制", lambda log_fn: copy_to_usb(rom_path, pkg_path, drive, log_fn))

    def _eject_usb(self):
        drive = self.usb_drive.get().strip()
        if not drive:
            return
        self._run_task("弹出", lambda log_fn: eject_usb(drive, log_fn))

    def _one_click_handcontrol(self):
        asset = self._selected_asset()
        drive = self.usb_drive.get().strip()
        if not asset or not drive:
            return
        rom_file, pkg_file = self._asset_rom_pkg_files(asset)
        if not rom_file or not pkg_file:
            return
        rom_path = str(Path(asset["path"]) / rom_file)
        pkg_path = str(Path(asset["path"]) / pkg_file)
        self._run_task(
            "一键执行",
            lambda log_fn: run_one_click(drive, asset["model"], asset["version"], rom_path, pkg_path, log_fn=log_fn),
        )

    def _run_directory_flash(self):
        asset = self._selected_asset()
        drive = self.usb_drive.get().strip()
        if not asset or not drive:
            return
        format_first = bool(getattr(self, "format_first", self._make_bool_var(True)).get())
        eject_after = bool(getattr(self, "eject_after", self._make_bool_var(True)).get())
        self._run_task(
            "目录刷机",
            lambda log_fn: run_music_flash(asset["path"], drive, format_first=format_first, eject_after=eject_after, log_fn=log_fn),
            lambda result: self._log(f"结果: {result.get('message')}"),
        )


HandcontrolPanel = FirmwareListPanel
