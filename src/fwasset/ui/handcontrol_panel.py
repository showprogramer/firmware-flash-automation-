from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from fwasset.core.services.flash_service import run_one_click
from fwasset.core.services.scan_service import build_scan_result
from fwasset.core.settings import DEFAULT_ROOT
from fwasset.core.sort_config import SortKey, apply_sort
from fwasset.core.usb_ops import clean_usb, copy_to_usb, eject_usb, format_usb
from fwasset.ui.base_panel import BaseFlashPanel
from fwasset.ui.design_tokens import (
    BG_CARD,
    BG_HOVER,
    BG_INPUT,
    BORDER_COLOR,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    FONT_FAMILY,
    FONT_SIZE_LG,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    FONT_SIZE_XL,
)
from fwasset.ui.shared_widgets import section_title


class HandcontrolPanel(BaseFlashPanel):
    mode_key = "handcontrol"

    def __init__(self, master, switch_view_cb):
        super().__init__(master, switch_view_cb)

        self.root_dir = tk.StringVar(value=DEFAULT_ROOT)
        self.search_var = tk.StringVar(value="")
        self.sort_key_var = tk.StringVar(value="默认(名称)")
        self.sort_asc_var = tk.BooleanVar(value=True)

        self.folders: list[dict] = []
        self._all_folders: list[dict] = []
        self._selected_idx = -1
        self._folder_card_widgets: list[dict] = []
        self.manual_open = False

        self._build_sidebar()
        self._build_main_view()

        self._refresh_usb()
        self.search_var.trace_add("write", lambda *_: self._filter_folders())

    def _build_sidebar(self):
        sidebar = self._build_sidebar_frame()
        self._build_brand_header(sidebar)
        self._build_mode_switch(sidebar)

        search_sort_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        search_sort_frame.pack(fill="x", padx=20, pady=(0, 16))

        search_box = ctk.CTkEntry(
            search_sort_frame,
            height=36,
            corner_radius=8,
            placeholder_text="搜索 型号/版本/路径",
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
            command=lambda _value: self._filter_folders(),
        )
        self.sort_menu.pack(side="right")

        self.list_scroll = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        self.list_scroll.pack(fill="both", expand=True, padx=12)

    def _build_main_view(self):
        main = self._build_main_container()
        self._build_header(main)
        self._build_dashboard_cards(main)
        self._build_log_panel(main)

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

        self.header_status_badge = ctk.CTkLabel(
            title_box,
            text="未选择",
            fg_color=TEXT_SECONDARY,
            corner_radius=6,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
            text_color="white",
            padx=12,
            pady=4,
        )
        self.header_status_badge.pack(side="left", padx=8)

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")
        ctk.CTkButton(
            actions,
            text="扫描根目录",
            fg_color=BG_CARD,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            border_width=1,
            border_color=BORDER_COLOR,
            command=self._choose_root_and_scan,
        ).pack(side="left", padx=8)

    def _build_dashboard_cards(self, parent):
        cards_container = ctk.CTkFrame(parent, fg_color="transparent")
        cards_container.grid(row=1, column=0, sticky="ew", pady=(0, 24))
        cards_container.grid_columnconfigure(0, weight=4)
        cards_container.grid_columnconfigure(1, weight=5)

        ops_card = ctk.CTkFrame(
            cards_container,
            fg_color=BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        ops_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        section_title(ops_card, "刷机与设备交互")
        self._build_usb_selector_row(ops_card)

        ctk.CTkButton(
            ops_card,
            text="一键智能刷机",
            height=48,
            corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            command=self._one_click,
        ).pack(fill="x", padx=20, pady=(10, 5))

        self.manual_btn = ctk.CTkButton(
            ops_card,
            text="▸ 展开手动分步操作",
            height=32,
            anchor="w",
            fg_color="transparent",
            text_color=TEXT_SECONDARY,
            hover_color=BG_HOVER,
            command=self._toggle_manual,
        )
        self.manual_btn.pack(fill="x", padx=20, pady=5)

        self.manual_frame = ctk.CTkFrame(ops_card, fg_color="transparent")
        for step, command in [
            ("1. 清理垃圾文件", self._clean_usb),
            ("2. 格式化 FAT32", self._format_usb),
            ("3. 复制文件到 U 盘", self._copy_to_usb),
            ("4. 安全弹出", self._eject_usb),
        ]:
            ctk.CTkButton(
                self.manual_frame,
                text=step,
                height=36,
                anchor="w",
                corner_radius=6,
                fg_color=BG_INPUT,
                text_color=TEXT_PRIMARY,
                hover_color=BG_HOVER,
                command=command,
            ).pack(fill="x", pady=2)

        detail_card = ctk.CTkFrame(
            cards_container,
            fg_color=BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        detail_card.grid(row=0, column=1, sticky="nsew", padx=(12, 0))

        section_title(detail_card, "资源详情")

        self.detail_values: dict[str, ctk.CTkLabel] = {}
        fields = [
            ("型号", "model"),
            ("版本", "version"),
            ("当前目录", "folder_name"),
            ("原始路径", "path"),
            ("ROM 文件", "rom_file"),
            ("PKG 文件", "pkg_file"),
            ("固件类型", "firmware_type"),
            ("可执行操作", "actions"),
        ]
        for label_text, key in fields:
            row = ctk.CTkFrame(detail_card, fg_color="transparent")
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
                font=(FONT_FAMILY, FONT_SIZE_MD),
                text_color=TEXT_PRIMARY,
            )
            value.pack(side="left", fill="x", expand=True, padx=(8, 0))
            self.detail_values[key] = value

        ctk.CTkButton(
            detail_card,
            text="下一个 ❯",
            height=36,
            corner_radius=6,
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            command=self._next_folder,
        ).pack(anchor="e", padx=20, pady=(12, 20))

    def _build_log_panel(self, parent):
        panel = ctk.CTkFrame(parent, corner_radius=12, fg_color=BG_CARD)
        panel.grid(row=2, column=0, sticky="nsew")
        section_title(panel, "运行日志")
        self.log_text = ctk.CTkTextbox(panel, font=("Consolas", FONT_SIZE_MD), fg_color=BG_INPUT, corner_radius=8)
        self.log_text.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    def _toggle_manual(self):
        if self.manual_open:
            self.manual_frame.pack_forget()
            self.manual_btn.configure(text="▸ 展开手动分步操作")
            self.manual_open = False
        else:
            self.manual_frame.pack(fill="x", padx=20, pady=(0, 10), after=self.manual_btn)
            self.manual_btn.configure(text="▾ 收起手动分步操作")
            self.manual_open = True

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
            selected = filedialog.askdirectory(initialdir=str(Path.cwd()))
            if selected:
                self.root_dir.set(selected)
                root = selected
            else:
                return

        def _work(log_fn):
            return build_scan_result(root, log_fn=log_fn)

        def _done(result):
            if not result.get("ok"):
                messagebox.showerror("扫描失败", str(result.get("message", "未知错误")))
                return
            payload = result.get("payload", {}) or {}
            self._all_folders = list(payload.get("folders", []))
            self._selected_idx = -1
            self._filter_folders()

        self._run_task("扫描目录", _work, _done)

    def _filter_folders(self):
        keyword = self.search_var.get().strip().lower()
        sort_by = self.sort_key_var.get()

        filtered = []
        for item in self._all_folders:
            if keyword:
                text = " ".join(
                    str(item.get(key, "") or "")
                    for key in ("model", "version", "label", "path", "rom_file", "pkg_file")
                ).lower()
                if keyword not in text:
                    continue
            filtered.append(item)

        sort_key = SortKey.PATH
        if sort_by == "按型号":
            sort_key = SortKey.MODEL
        elif sort_by == "按版本":
            sort_key = SortKey.VERSION

        self.folders = apply_sort(filtered, sort_key=sort_key, ascending=bool(self.sort_asc_var.get()))
        self._render_folder_cards()

    def _render_folder_cards(self):
        self._folder_card_widgets = []
        for widget in self.list_scroll.winfo_children():
            widget.destroy()

        for idx, item in enumerate(self.folders):
            self._create_sidebar_item(idx, item)

    def _selected_card_colors(self):
        return {
            "card_fg": COLOR_PRIMARY,
            "border_color": COLOR_PRIMARY_HOVER,
            "model_text": "white",
            "meta_text": "#EAF2FF",
            "name_text": "#D5E6FF",
        }

    def _unselected_card_colors(self):
        return {
            "card_fg": "transparent",
            "border_color": BORDER_COLOR,
            "model_text": TEXT_PRIMARY,
            "meta_text": TEXT_SECONDARY,
            "name_text": TEXT_SECONDARY,
        }

    def _apply_card_visual_state(self, idx: int, selected: bool):
        if idx < 0 or idx >= len(self._folder_card_widgets):
            return
        widgets = self._folder_card_widgets[idx]
        palette = self._selected_card_colors() if selected else self._unselected_card_colors()
        widgets["card"].configure(fg_color=palette["card_fg"], border_color=palette["border_color"])
        widgets["model_label"].configure(text_color=palette["model_text"])
        widgets["version_label"].configure(text_color=palette["meta_text"])
        widgets["name_label"].configure(text_color=palette["name_text"])

    def _create_sidebar_item(self, idx, item):
        is_selected = idx == self._selected_idx
        palette = self._selected_card_colors() if is_selected else self._unselected_card_colors()

        card_item = ctk.CTkFrame(
            self.list_scroll,
            fg_color=palette["card_fg"],
            corner_radius=10,
            height=68,
            cursor="hand2",
            border_width=1,
            border_color=palette["border_color"],
        )
        card_item.pack(fill="x", pady=4, padx=8)
        card_item.pack_propagate(False)

        dot = ctk.CTkFrame(card_item, width=10, height=10, corner_radius=5, fg_color=COLOR_PRIMARY)
        dot.pack(side="left", padx=16)

        text_area = ctk.CTkFrame(card_item, fg_color="transparent")
        text_area.pack(side="left", fill="both", expand=True, pady=12)

        row1 = ctk.CTkFrame(text_area, fg_color="transparent")
        row1.pack(fill="x")
        model_label = ctk.CTkLabel(
            row1,
            text=item.get("model", ""),
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
            text_color=palette["model_text"],
        )
        model_label.pack(side="left")
        version_label = ctk.CTkLabel(
            row1,
            text=f" • {item.get('version', '')}",
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=palette["meta_text"],
        )
        version_label.pack(side="left", padx=4)

        name = str(Path(item.get("path", "")).name)
        name_label = ctk.CTkLabel(
            text_area,
            text=name[:24] + "..." if len(name) > 24 else name,
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=palette["name_text"],
            anchor="w",
        )
        name_label.pack(fill="x", pady=(2, 0))

        for widget in [card_item, dot, text_area, row1, model_label, version_label, name_label]:
            widget.bind("<Button-1>", lambda _event, i=idx: self._select_folder(i))
            widget.bind("<Double-Button-1>", lambda _event, i=idx: self._open_folder_from_index(i))

        if not is_selected:
            card_item.bind("<Enter>", lambda _event, i=idx: self._apply_card_visual_state(i, True))
            card_item.bind("<Leave>", lambda _event, i=idx: self._apply_card_visual_state(i, i == self._selected_idx))

        self._folder_card_widgets.append(
            {
                "card": card_item,
                "model_label": model_label,
                "version_label": version_label,
                "name_label": name_label,
            }
        )

    def _select_folder(self, idx: int):
        if idx < 0 or idx >= len(self.folders):
            return
        previous_idx = self._selected_idx
        self._selected_idx = idx
        if previous_idx != idx:
            self._apply_card_visual_state(previous_idx, False)
            self._apply_card_visual_state(idx, True)

        info = self.folders[idx]
        self.header_model_label.configure(text=info.get("model", "-"))
        self.header_version_badge.configure(text=info.get("version", "-"))
        self.header_status_badge.configure(text="资源详情", fg_color=COLOR_PRIMARY)
        self._update_detail_panel(info)
        self._log(f"已选择: {info.get('model', '')} {info.get('version', '')}")

    def _update_detail_panel(self, info: dict):
        path_text = str(info.get("path", "") or "")
        folder_name = Path(path_text).name if path_text else "-"
        details = {
            "model": str(info.get("model", "") or "-"),
            "version": str(info.get("version", "") or "-"),
            "folder_name": folder_name or "-",
            "path": path_text or "-",
            "rom_file": str(info.get("rom_file", "") or "-"),
            "pkg_file": str(info.get("pkg_file", "") or "-"),
            # TODO: read the concrete firmware type from catalog/scan metadata
            # once the unified multi-firmware scanner is wired in.
            "firmware_type": "手控 UI",
            "actions": "扫描、双击打开目录、一键刷机、清理、格式化、复制、弹出",
        }
        for key, value in details.items():
            if key in self.detail_values:
                self.detail_values[key].configure(text=value)

    def _open_folder_from_index(self, idx: int):
        if idx < 0 or idx >= len(self.folders):
            return
        info = self.folders[idx]
        path_obj = Path(str(info.get("path", "")))
        if not path_obj.exists():
            messagebox.showerror("错误", f"路径不存在: {path_obj}")
            return
        try:
            os.startfile(str(path_obj.resolve()))
        except OSError as exc:
            messagebox.showerror("错误", f"打开目录失败: {exc}")

    def _current_info(self) -> dict | None:
        if self._selected_idx < 0:
            messagebox.showwarning("提示", "请先选择一个条目")
            return None
        return self.folders[self._selected_idx]

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
        info = self._current_info()
        drive = self.usb_drive.get().strip()
        if not info or not drive:
            return
        rom_path = str(Path(info["path"]) / info["rom_file"])
        pkg_path = str(Path(info["path"]) / info["pkg_file"])
        self._run_task("复制", lambda log_fn: copy_to_usb(rom_path, pkg_path, drive, log_fn))

    def _eject_usb(self):
        drive = self.usb_drive.get().strip()
        if not drive:
            return
        self._run_task("弹出", lambda log_fn: eject_usb(drive, log_fn))

    def _one_click(self):
        info = self._current_info()
        drive = self.usb_drive.get().strip()
        if not info or not drive:
            return
        rom_path = str(Path(info["path"]) / info["rom_file"])
        pkg_path = str(Path(info["path"]) / info["pkg_file"])
        self._run_task(
            "一键执行",
            lambda log_fn: run_one_click(drive, info["model"], info["version"], rom_path, pkg_path, log_fn=log_fn),
        )

    def _next_folder(self):
        if self._selected_idx + 1 < len(self.folders):
            self._select_folder(self._selected_idx + 1)
        else:
            messagebox.showinfo("提示", "已到末尾")
