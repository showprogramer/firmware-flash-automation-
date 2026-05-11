from __future__ import annotations

import os
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from fwasset.core.asset_index import AssetIndexError, hide_item, load_hidden_items, unhide_item
from fwasset.core.firmware_catalog import enabled_firmware_types, load_firmware_catalog
from fwasset.core.tool_discovery import discover_tool_path, launch_tool
from fwasset.ui.tool_center_panel import ToolCenterPanel
from fwasset.core.services.flash_service import run_one_click
from fwasset.core.services.music_flash_service import run_music_flash
from fwasset.core.services.scan_service import build_cached_scan_result, build_scan_result
from fwasset.core.settings import DEFAULT_ROOT
from fwasset.core.sort_config import SortKey, apply_sort
from fwasset.core.types import FirmwareAsset
from fwasset.core.usb_ops import clean_usb, copy_to_usb, eject_usb, format_usb
from fwasset.ui.asset_tree import AssetTreeView
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
        self.show_hidden_var = tk.BooleanVar(value=False)
        self.type_quick_var = tk.StringVar(value="先选择固件类型")
        self._type_label_to_key = {
            item["label"]: item["key"]
            for item in enabled_firmware_types()
        }
        self.type_filter_vars = {
            item["key"]: tk.BooleanVar(value=False)
            for item in enabled_firmware_types()
        }
        self.assets: list[FirmwareAsset] = []
        self.folders: list[dict] = []
        self._all_assets: list[FirmwareAsset] = []
        self._selected_idx = -1
        self._asset_card_widgets: list[dict] = []
        self.asset_tree: AssetTreeView | None = None
        self._empty_list_hint = None
        self._tree_expanded: set[str] = set()
        self._hidden_items: dict[str, str] = {}
        self._log_collapsed = True
        self.detail_values: dict[str, ctk.CTkLabel] = {}
        self._status_hint_text = "Select a firmware version on the left; key details stay here and actions stay on the right."

        self.grid_columnconfigure(0, weight=8, minsize=760)
        self.grid_columnconfigure(1, weight=0, minsize=320)
        self._reload_hidden_items()
        self._build_sidebar()
        self._build_main_view()
        self._refresh_usb()
        self.search_var.trace_add("write", lambda *_: self._filter_assets())
        self.show_hidden_var.trace_add("write", lambda *_: self._filter_assets())
        self.after(100, self._load_cached_assets)

    def _build_brand_header_with_tools(self, parent, title: str = "程序资产管理系统"):
        """构建带工具中心按钮的品牌标题栏."""
        from fwasset.ui.design_tokens import BG_SIDEBAR, BG_INPUT, BG_HOVER, COLOR_PRIMARY, FONT_FAMILY, FONT_SIZE_LG, TEXT_PRIMARY
        
        brand_frame = ctk.CTkFrame(parent, fg_color="transparent")
        brand_frame.pack(fill="x", padx=24, pady=(24, 12))
        
        # 左侧图标和标题
        left = ctk.CTkFrame(brand_frame, fg_color="transparent")
        left.pack(side="left")
        
        ctk.CTkLabel(
            left,
            text="⚡",
            font=(FONT_FAMILY, 24),
            text_color=COLOR_PRIMARY,
        ).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(
            left,
            text=title,
            font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(side="left")
        
        # 右侧工具中心按钮
        ctk.CTkButton(
            brand_frame,
            text="🔧 工具中心",
            width=100,
            height=32,
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            command=self._open_tool_center,
        ).pack(side="right")
    
    def _open_tool_center(self):
        """打开工具中心窗口."""
        ToolCenterPanel(self.winfo_toplevel(), log_fn=self._log)

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
        sidebar = self._build_sidebar_frame(width=760)
        self._build_brand_header_with_tools(sidebar, title="固件资源列表")

        search_sort_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        search_sort_frame.pack(fill="x", padx=20, pady=(0, 10))

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

        quick_values = ["先选择固件类型", "全部类型", *self._type_label_to_key.keys()]
        self.type_quick_menu = ctk.CTkOptionMenu(
            search_sort_frame,
            values=quick_values,
            variable=self.type_quick_var,
            width=150,
            height=36,
            fg_color=BG_CARD,
            text_color=TEXT_PRIMARY,
            button_color=BG_CARD,
            button_hover_color=BG_HOVER,
            font=(FONT_FAMILY, FONT_SIZE_MD),
            command=self._select_single_type_filter,
        )
        self.type_quick_menu.pack(side="left", padx=(0, 8))

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
        self.sort_menu.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            search_sort_frame,
            text="清空",
            width=58,
            height=36,
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            command=self._clear_type_filters,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkCheckBox(
            search_sort_frame,
            text="显示隐藏",
            variable=self.show_hidden_var,
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=TEXT_SECONDARY,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            search_sort_frame,
            text="扫描根目录",
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            width=96,
            height=36,
            command=self._choose_root_and_scan,
        ).pack(side="right")

        self.asset_tree = AssetTreeView(
            sidebar,
            on_select_asset=self._select_asset,
            on_open_asset=self._open_asset_path,
            on_context_menu=self._show_hidden_context_menu,
            on_node_open=self._mark_tree_node_open,
            on_node_close=self._mark_tree_node_closed,
        )
        self.asset_tree.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.list_scroll = self.asset_tree.frame

    def _select_all_type_filters(self):
        for var in self.type_filter_vars.values():
            var.set(True)
        self.type_quick_var.set("全部类型")
        self._tree_expanded.clear()
        self._filter_assets()

    def _clear_type_filters(self):
        for var in self.type_filter_vars.values():
            var.set(False)
        self.type_quick_var.set("先选择固件类型")
        self._tree_expanded.clear()
        self._filter_assets()

    def _select_single_type_filter(self, label: str):
        if label == "先选择固件类型":
            self._clear_type_filters()
            return
        if label == "全部类型":
            self._select_all_type_filters()
            return
        if label not in self._type_label_to_key:
            return
        selected_key = self._type_label_to_key[label]
        for key, var in self.type_filter_vars.items():
            var.set(key == selected_key)
        self._tree_expanded.clear()
        self._filter_assets()

    def _build_main_view(self):
        main = self._build_main_container()
        main.grid_rowconfigure(1, weight=1)
        main.grid_rowconfigure(2, weight=0)
        self._build_header(main)
        cards_container = ctk.CTkFrame(main, fg_color="transparent")
        cards_container.grid(row=1, column=0, sticky="nsew", pady=(0, 24))
        cards_container.grid_columnconfigure(0, weight=1)
        cards_container.grid_columnconfigure(1, weight=0)
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
            ("系列", "series"),
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
        self.detail_card.grid_forget()
        self.ops_card.grid(row=0, column=0, sticky="nsew")
        section_title(self.ops_card, "操作区")
        self.ops_body = ctk.CTkFrame(self.ops_card, fg_color="transparent")
        self.ops_body.pack(fill="both", expand=True, padx=0, pady=(0, 10))
        self.serial_control = None
        self._render_operation_panel(None)

        panel = ctk.CTkFrame(main, corner_radius=12, fg_color=BG_CARD)
        panel.grid(row=2, column=0, sticky="ew")
        self.log_panel = panel
        section_title(panel, "运行日志")
        self.log_text = ctk.CTkTextbox(panel, font=("Consolas", FONT_SIZE_MD), fg_color=BG_INPUT, corner_radius=8)
        self.log_toggle_btn = ctk.CTkButton(
            panel,
            text="展开日志",
            width=96,
            height=30,
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            command=self._toggle_log_panel,
        )
        self.log_toggle_btn.pack(anchor="e", padx=20, pady=(0, 10))
        self._set_log_collapsed(True)

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
        if not hasattr(self, "filter_frame"):
            return
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

    def _reload_hidden_items(self):
        try:
            self._hidden_items = load_hidden_items()
        except AssetIndexError as exc:
            self._hidden_items = {}
            if hasattr(self, "_log"):
                self._log(str(exc))

    def _is_asset_hidden(self, asset: FirmwareAsset) -> bool:
        asset_path = str(asset.get("path", "") or "")
        model_path = str(asset.get("model_directory_path", "") or "")
        if asset_path in self._hidden_items or model_path in self._hidden_items:
            return True
        return any(
            hide_type == "firmware_type" and bool(hidden_path) and asset_path.startswith(hidden_path)
            for hidden_path, hide_type in self._hidden_items.items()
        )

    def _asset_hidden_type(self, asset: FirmwareAsset) -> str:
        asset_path = str(asset.get("path", "") or "")
        model_path = str(asset.get("model_directory_path", "") or "")
        if asset_path in self._hidden_items:
            return "asset"
        if model_path in self._hidden_items:
            return "model_directory"
        for hidden_path, hide_type in self._hidden_items.items():
            if hide_type == "firmware_type" and bool(hidden_path) and asset_path.startswith(hidden_path):
                return "firmware_type"
        return ""

    def _common_asset_path(self, assets: list[FirmwareAsset], indices: list[int]) -> str:
        paths = [str(assets[idx].get("path", "") or "") for idx in indices if idx < len(assets)]
        paths = [path for path in paths if path]
        if not paths:
            return ""
        if len(paths) == 1:
            return paths[0]
        try:
            return os.path.commonpath(paths)
        except ValueError:
            return paths[0]

    def _set_log_collapsed(self, collapsed: bool):
        self._log_collapsed = collapsed
        if collapsed:
            if hasattr(self.log_text, "pack_forget"):
                self.log_text.pack_forget()
            self.log_toggle_btn.configure(text="展开日志")
            return
        self.log_text.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.log_toggle_btn.configure(text="折叠日志")

    def _toggle_log_panel(self):
        self._set_log_collapsed(not self._log_collapsed)

    def _update_sidebar_status(self, asset: FirmwareAsset | None):
        if not hasattr(self, "sidebar_status_label"):
            return
        if asset is None:
            self.sidebar_status_label.configure(text=self._status_hint_text)
            return
        files = ", ".join(str(name) for name in asset.get("files", [])[:3]) or "-"
        status = (
            f"{asset.get('model', '-') or '-'} / {asset.get('version', '-') or '-'} | "
            f"{asset.get('firmware_label', '-') or '-'} | {asset.get('flash_mode', '-') or '-'}\n"
            f"{asset.get('path', '-') or '-'}\n"
            f"{files}"
        )
        self.sidebar_status_label.configure(text=status)

    def _show_hidden_context_menu(self, event, item_path: str, hide_type: str):
        if not item_path:
            return
        menu = tk.Menu(self, tearoff=0)
        is_hidden = item_path in self._hidden_items
        label = "恢复此条目" if is_hidden else "隐藏此条目"
        command = (lambda: self._unhide_tree_item(item_path)) if is_hidden else (lambda: self._hide_tree_item(item_path, hide_type))
        menu.add_command(label=label, command=command)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _hide_tree_item(self, item_path: str, hide_type: str):
        hide_item(item_path, hide_type=hide_type)  # type: ignore[arg-type]
        self._reload_hidden_items()
        self._filter_assets()

    def _unhide_tree_item(self, item_path: str):
        unhide_item(item_path)
        self._reload_hidden_items()
        self._filter_assets()

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
            self._tree_expanded.clear()
            self._filter_assets()

        self._run_task("扫描目录", _work, _done)

    def _load_cached_assets(self):
        def _work(log_fn):
            return build_cached_scan_result(log_fn=log_fn)

        def _done(result):
            if not result.get("ok"):
                self._log(str(result.get("message", "本地资产索引读取失败")))
                return
            payload = result.get("payload", {}) or {}
            self._all_assets = list(payload.get("assets", []))
            self._selected_idx = -1
            self._tree_expanded.clear()
            self._filter_assets()
            if not self._all_assets:
                self._render_empty_list_hint("本地暂无资产索引，请点击扫描根目录生成。")

        self._run_task("读取本地索引", _work, _done)

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
        show_hidden = bool(self.show_hidden_var.get())
        filtered: list[FirmwareAsset] = []
        for item in self._all_assets:
            if item.get("firmware_type") not in selected_types:
                continue
            if not show_hidden and self._is_asset_hidden(item):
                continue
            if keyword:
                haystack = " ".join(
                    [
                        str(item.get("model", "") or ""),
                        str(item.get("series", "") or ""),
                        str(item.get("version", "") or ""),
                        str(item.get("firmware_label", "") or ""),
                        str(item.get("model_directory_name", "") or ""),
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
        if keyword:
            self._expand_matching_tree_nodes(self.assets)
        self._render_asset_tree()

    def _render_asset_cards(self):
        self._render_asset_tree()

    def _render_asset_tree(self):
        self._asset_card_widgets = []
        self._ensure_default_tree_expanded()
        groups = self._build_tree_groups(self.assets)
        visible_asset_indices = self._visible_tree_asset_indices(groups)
        self._asset_card_widgets = [{"asset_idx": idx} for idx in visible_asset_indices]
        hidden_indices = {idx for idx, asset in enumerate(self.assets) if self._is_asset_hidden(asset)}
        if self.asset_tree is not None:
            self.asset_tree.populate(groups, self.assets, self._tree_expanded, -1, hidden_indices)
        if self.assets:
            next_idx = min(max(self._selected_idx, 0), len(self.assets) - 1)
            self._select_asset(next_idx)
        else:
            self._selected_idx = -1
            self._clear_selection()
            if self._all_assets and not self._selected_types():
                self._render_empty_list_hint("请先在上方选择一种固件类型。")
            elif self._all_assets:
                self._render_empty_list_hint("当前筛选条件下没有匹配的程序。")

        if self.assets and not visible_asset_indices:
            self._render_empty_list_hint("当前树节点已折叠，展开系列或型号目录后查看程序。")

    def _tree_key(self, kind: str, *parts: object) -> str:
        return "|".join([kind, *[str(part) for part in parts]])

    def _is_tree_node_open(self, key: str) -> bool:
        return key in self._tree_expanded

    def _toggle_tree_node(self, key: str):
        if key in self._tree_expanded:
            self._tree_expanded.remove(key)
        else:
            self._tree_expanded.add(key)
        self._render_asset_tree()

    def _mark_tree_node_open(self, key: str):
        self._tree_expanded.add(key)

    def _mark_tree_node_closed(self, key: str):
        self._tree_expanded.discard(key)

    def _ensure_default_tree_expanded(self):
        if self._tree_expanded or not self.assets:
            return
        self._expand_matching_tree_nodes(self.assets)

    def _expand_matching_tree_nodes(self, assets: list[FirmwareAsset]):
        for series_node in self._build_tree_groups(assets):
            self._tree_expanded.add(self._tree_key("series", series_node["series"]))
            for model_node in series_node["models"]:
                self._tree_expanded.add(self._tree_key("model", series_node["series"], model_node["path"]))
                for type_node in model_node["types"]:
                    self._tree_expanded.add(self._tree_key("type", model_node["path"], type_node["firmware_type"]))

    def _build_tree_groups(self, assets: list[FirmwareAsset]) -> list[dict]:
        series_map: dict[str, dict] = {}
        for idx, asset in enumerate(assets):
            series = str(asset.get("series", "") or "未知系列")
            model_path = str(asset.get("model_directory_path", "") or asset.get("path", ""))
            model_name = str(asset.get("model_directory_name", "") or asset.get("model", "") or model_path)
            firmware_type = str(asset.get("firmware_type", "") or "unknown")
            firmware_label = str(asset.get("firmware_label", "") or firmware_type)
            hidden = self._is_asset_hidden(asset)
            series_node = series_map.setdefault(series, {"series": series, "models": {}})
            model_node = series_node["models"].setdefault(
                model_path,
                {"name": model_name, "path": model_path, "types": {}, "hidden": False},
            )
            model_node["hidden"] = bool(model_node["hidden"] or self._hidden_items.get(model_path) == "model_directory")
            type_node = model_node["types"].setdefault(
                firmware_type,
                {"firmware_type": firmware_type, "label": firmware_label, "asset_indices": [], "hidden": False},
            )
            type_node["hidden"] = bool(type_node["hidden"] or hidden)
            type_node["asset_indices"].append(idx)

        out: list[dict] = []
        for series_name in sorted(series_map.keys(), key=str.casefold):
            series_node = series_map[series_name]
            series_key = self._tree_key("series", series_name)
            models = []
            for model_path, model_node in sorted(series_node["models"].items(), key=lambda item: item[1]["name"].casefold()):
                model_key = self._tree_key("model", series_name, model_path)
                types = []
                for _firmware_type, type_node in sorted(model_node["types"].items(), key=lambda item: item[1]["label"].casefold()):
                    type_node["key"] = self._tree_key("type", model_path, type_node["firmware_type"])
                    type_node["version_count"] = len(
                        {str(assets[idx].get("version", "") or "-") for idx in type_node["asset_indices"]}
                    )
                    type_node["hide_path"] = self._common_asset_path(assets, type_node["asset_indices"])
                    types.append(type_node)
                models.append(
                    {
                        "key": model_key,
                        "name": model_node["name"],
                        "path": model_path,
                        "types": types,
                        "type_count": len(types),
                        "hidden": bool(model_node.get("hidden")),
                    }
                )
            out.append({"key": series_key, "series": series_name, "models": models, "model_count": len(models)})
        return out

    def _visible_tree_asset_indices(self, groups: list[dict]) -> list[int]:
        visible: list[int] = []
        for series_node in groups:
            if not self._is_tree_node_open(str(series_node["key"])):
                continue
            for model_node in series_node["models"]:
                if not self._is_tree_node_open(str(model_node["key"])):
                    continue
                for type_node in model_node["types"]:
                    if self._is_tree_node_open(str(type_node["key"])):
                        visible.extend(type_node["asset_indices"])
        return visible

    def _create_tree_header(
        self,
        level: int,
        key: str,
        text: str,
        is_open: bool,
        hide_path: str = "",
        hide_type: str = "asset",
        hidden: bool = False,
    ):
        padx = 8 + level * 16
        header = ctk.CTkFrame(
            self.list_scroll,
            fg_color=BG_INPUT if level == 0 else ("#F3F4F6" if hidden else "transparent"),
            corner_radius=8,
            height=34,
            cursor="hand2",
            border_width=1 if level == 0 else 0,
            border_color=BORDER_COLOR,
        )
        header.pack(fill="x", pady=(8 if level == 0 else 3, 2), padx=(padx, 8))
        header.pack_propagate(False)
        label = ctk.CTkLabel(
            header,
            text=f"{'▾' if is_open else '▸'} {text}",
            font=(FONT_FAMILY, FONT_SIZE_MD if level == 0 else FONT_SIZE_SM, "bold" if level < 2 else "normal"),
            text_color=TEXT_PRIMARY if level < 2 else TEXT_SECONDARY,
            anchor="w",
        )
        label.pack(fill="x", expand=True, padx=10)
        for widget in [header, label]:
            widget.bind("<Button-1>", lambda _event, node_key=key: self._toggle_tree_node(node_key))
            if hide_path:
                widget.bind(
                    "<Button-3>",
                    lambda event, path=hide_path, kind=hide_type: self._show_hidden_context_menu(event, path, kind),
                )

    def _render_empty_list_hint(self, text: str):
        if self.asset_tree is not None:
            if hasattr(self.asset_tree, "show_message"):
                self.asset_tree.show_message(text)
            return
        ctk.CTkLabel(
            self.list_scroll,
            text=text,
            font=(FONT_FAMILY, FONT_SIZE_MD),
            text_color=TEXT_SECONDARY,
            wraplength=360,
            justify="left",
        ).pack(anchor="w", padx=18, pady=18)

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
        if idx < 0:
            return
        if self.asset_tree is not None:
            if selected:
                self.asset_tree.focus_asset(idx)
            return
        widgets = next((item for item in self._asset_card_widgets if item.get("asset_idx") == idx), None)
        if widgets is None:
            return
        palette = self._selected_card_colors() if selected else self._unselected_card_colors()
        widgets["card"].configure(fg_color=palette["card_fg"], border_color=palette["border_color"])
        widgets["title_label"].configure(text_color=palette["title_text"])
        widgets["meta_label"].configure(text_color=palette["meta_text"])
        widgets["type_label"].configure(text_color=palette["meta_text"])

    def _create_sidebar_item(self, idx: int, item: FirmwareAsset, indent: int = 8):
        is_selected = idx == self._selected_idx
        is_hidden = self._is_asset_hidden(item)
        palette = self._selected_card_colors() if is_selected else self._unselected_card_colors()
        if is_hidden and not is_selected:
            palette = {**palette, "title_text": TEXT_SECONDARY, "meta_text": TEXT_SECONDARY, "border_color": "#D1D5DB"}
        card_item = ctk.CTkFrame(
            self.list_scroll,
            fg_color=palette["card_fg"],
            corner_radius=10,
            height=84,
            cursor="hand2",
            border_width=1,
            border_color=palette["border_color"],
        )
        card_item.pack(fill="x", pady=4, padx=(indent, 8))
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
            widget.bind(
                "<Button-3>",
                lambda event, path=str(item.get("path", "") or ""), kind="asset": self._show_hidden_context_menu(event, path, kind),
            )

        self._asset_card_widgets.append(
            {
                "card": card_item,
                "asset_idx": idx,
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
        self._update_sidebar_status(None)
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
        self._update_sidebar_status(asset)
        self._render_operation_panel(asset)
        self._log(f"已选择: {asset.get('model', '')} {asset.get('version', '')} [{asset.get('firmware_label', '')}]")

    def _update_detail_panel(self, asset: FirmwareAsset):
        modified_time = "-"
        if asset.get("modified_time"):
            modified_time = datetime.fromtimestamp(float(asset["modified_time"])).strftime("%Y-%m-%d %H:%M:%S")
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
                font=(FONT_FAMILY, FONT_SIZE_LG),
                text_color=TEXT_PRIMARY,
            ).pack(anchor="w", padx=20, pady=20)
            return

        self._render_selected_detail_summary(asset)
        flash_mode = str(asset.get("flash_mode", ""))
        if flash_mode == "auto_usb":
            self._build_auto_usb_ops(asset)
        elif flash_mode == "auto_serial":
            self.serial_control = SerialControl(self.ops_body, log_fn=self._log)
            self.serial_control.pack(fill="both", expand=True)
            if self._polling_active:
                self.serial_control.activate()
        elif flash_mode == "tool_launch":
            self._build_tool_launch_ops(asset)
        elif flash_mode == "manual_doc":
            self._build_manual_doc_ops(asset)
        else:
            self._build_disabled_ops(asset)

    def _render_selected_detail_summary(self, asset: FirmwareAsset):
        summary = ctk.CTkFrame(self.ops_body, fg_color="transparent")
        summary.pack(fill="x", padx=20, pady=(12, 12))
        fields = [
            ("方式", str(asset.get("flash_mode", "") or "-")),
            ("目录", str(asset.get("path", "") or "-")),
            ("文件", ", ".join(str(name) for name in asset.get("files", [])[:4]) or "-"),
        ]
        for label_text, value_text in fields:
            row = ctk.CTkFrame(summary, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row,
                text=label_text,
                width=40,
                anchor="w",
                font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
                text_color=TEXT_PRIMARY,
            ).pack(side="left")
            ctk.CTkLabel(
                row,
                text=value_text,
                anchor="w",
                justify="left",
                wraplength=360,
                font=(FONT_FAMILY, FONT_SIZE_MD),
                text_color=TEXT_PRIMARY,
            ).pack(side="left", fill="x", expand=True, padx=(8, 0))

    def _render_placeholder_ops(self, text: str):
        ctk.CTkLabel(
            self.ops_body,
            text=text,
            justify="left",
            wraplength=360,
            font=(FONT_FAMILY, FONT_SIZE_MD),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=20, pady=20)

    def _asset_path_text(self, asset: FirmwareAsset | None = None) -> str:
        selected = asset or self._selected_asset()
        if not selected:
            return ""
        return str(selected.get("path", "") or "")

    def _primary_file_path_text(self, asset: FirmwareAsset | None = None) -> str:
        selected = asset or self._selected_asset()
        if not selected:
            return ""
        base_path = Path(str(selected.get("path", "") or ""))
        files = [str(name) for name in selected.get("files", []) if str(name).strip()]
        preferred_exts = (".bin", ".hex", ".rom", ".pkg", ".zip")
        primary = next((name for name in files if name.lower().endswith(preferred_exts)), "")
        if not primary and files:
            primary = files[0]
        return str(base_path / primary) if primary else str(base_path)

    def _copy_text_to_clipboard(self, text: str, label: str):
        if not text:
            messagebox.showwarning("提示", f"没有可复制的{label}")
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception as exc:
            messagebox.showerror("复制失败", str(exc))
            return
        self._log(f"已复制{label}: {text}")

    def _copy_asset_dir_path(self):
        asset = self._selected_asset()
        if asset:
            self._copy_text_to_clipboard(self._asset_path_text(asset), "目录路径")

    def _copy_primary_file_path(self):
        asset = self._selected_asset()
        if asset:
            self._copy_text_to_clipboard(self._primary_file_path_text(asset), "主文件路径")

    def _open_current_asset_dir(self):
        self._open_asset_path(self._selected_idx)

    def _launch_tool_and_open_asset_dir(self):
        self._launch_current_tool()
        self._open_current_asset_dir()

    def _build_handoff_actions(self, asset: FirmwareAsset, include_tool_combo: bool = False):
        action_frame = ctk.CTkFrame(self.ops_body, fg_color="transparent")
        action_frame.pack(fill="x", padx=20, pady=(0, 12))

        for title, command in [
            ("打开程序目录", self._open_current_asset_dir),
            ("复制目录路径", self._copy_asset_dir_path),
            ("复制主文件路径", self._copy_primary_file_path),
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
                command=self._launch_tool_and_open_asset_dir,
            ).pack(fill="x", pady=(6, 0))

    def _build_tool_launch_ops(self, asset: FirmwareAsset):
        """构建工具启动模式的操作面板."""
        fw_type = str(asset.get("firmware_type", ""))
        tool_name = str(asset.get("tool_name", "")) or "烧录工具"
        tool_dir = str(asset.get("tool_dir", ""))
        
        # 获取当前工具路径
        catalog = load_firmware_catalog()
        tool_path = ""
        dir_keywords: list[str] = []
        for item in catalog.get("firmware_types", []):
            if item.get("key") == fw_type:
                tool_path = item.get("tool_path", "")
                tool_dir = item.get("tool_dir", tool_dir)
                dir_keywords = item.get("dir_keywords", [])
                break
        
        # 如果没有配置路径，尝试自动发现
        if not tool_path:
            tool_path = discover_tool_path(
                fw_type,
                tool_name,
                tool_dir=tool_dir,
                dir_keywords=dir_keywords,
            )
        
        # 保存工具路径到实例变量
        self._current_tool_path = tool_path
        
        # 显示当前工具信息
        info_frame = ctk.CTkFrame(self.ops_body, fg_color="transparent")
        info_frame.pack(fill="x", padx=20, pady=(16, 8))
        
        ctk.CTkLabel(
            info_frame,
            text=f"工具类型: {tool_name}",
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w")
        
        path_text = tool_path if tool_path else "未配置工具路径"
        path_color = TEXT_SECONDARY if tool_path else "#E74C3C"
        self.tool_path_label = ctk.CTkLabel(
            info_frame,
            text=f"路径: {path_text}",
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=path_color,
            wraplength=360,
        )
        self.tool_path_label.pack(anchor="w", pady=(4, 0))
        
        # 按钮区域
        btn_frame = ctk.CTkFrame(self.ops_body, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(8, 12))
        
        # 打开烧录工具按钮
        ctk.CTkButton(
            btn_frame,
            text="🚀 打开烧录工具",
            height=48,
            corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            state="normal" if tool_path else "disabled",
            command=self._launch_current_tool,
        ).pack(fill="x", pady=(0, 8))

        self._build_handoff_actions(asset, include_tool_combo=True)
        
        if not tool_path:
            # 显示配置提示
            ctk.CTkLabel(
                self.ops_body,
                text="提示: 将烧录工具放在程序同目录的 tools 文件夹中，程序会自动发现。",
                wraplength=360,
                justify="left",
                font=(FONT_FAMILY, FONT_SIZE_SM),
                text_color=TEXT_SECONDARY,
            ).pack(anchor="w", padx=20, pady=(0, 12))

    def _build_manual_doc_ops(self, asset: FirmwareAsset):
        ctk.CTkLabel(
            self.ops_body,
            text="该类型需要按说明人工处理。",
            justify="left",
            wraplength=360,
            font=(FONT_FAMILY, FONT_SIZE_MD),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=20, pady=(16, 12))
        ctk.CTkButton(
            self.ops_body,
            text="查看说明",
            height=40,
            corner_radius=8,
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            command=lambda: self._show_manual_doc(asset),
        ).pack(fill="x", padx=20, pady=(0, 12))
        self._build_handoff_actions(asset)

    def _build_disabled_ops(self, asset: FirmwareAsset):
        ctk.CTkLabel(
            self.ops_body,
            text=f"{asset.get('firmware_label', '该类型')}当前不可自动化操作。",
            justify="left",
            wraplength=360,
            font=(FONT_FAMILY, FONT_SIZE_MD),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=20, pady=(16, 12))
        ctk.CTkButton(
            self.ops_body,
            text="暂不可操作",
            height=40,
            corner_radius=8,
            fg_color=BG_INPUT,
            text_color=TEXT_SECONDARY,
            hover_color=BG_INPUT,
            state="disabled",
        ).pack(fill="x", padx=20, pady=(0, 12))
        self._build_handoff_actions(asset)

    def _show_manual_doc(self, asset: FirmwareAsset):
        message = (
            f"固件类型: {asset.get('firmware_label', '-')}\n"
            f"型号: {asset.get('model', '-')}\n"
            f"版本: {asset.get('version', '-')}\n"
            f"目录: {asset.get('path', '-')}\n\n"
            "当前类型暂未接入自动烧录工具，请按对应工艺说明处理。"
        )
        messagebox.showinfo("操作说明", message)
    
    def _launch_current_tool(self):
        """启动当前选中的工具."""
        tool_path = getattr(self, "_current_tool_path", "")
        if not tool_path:
            messagebox.showwarning("提示", "工具路径未配置\n\n请将烧录工具放在程序同目录的 tools 文件夹中，或手动配置工具路径。")
            return
        
        result = launch_tool(tool_path)
        if result.get("ok"):
            self._log(f"✓ {result.get('message')}")
        else:
            messagebox.showerror("启动失败", result.get("message", ""))
            self._log(f"✗ {result.get('message')}")

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
