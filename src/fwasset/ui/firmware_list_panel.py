from __future__ import annotations

import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from fwasset.core.asset_helpers import asset_dir_path, asset_flash_mode, asset_primary_file_path, asset_rom_pkg_files, asset_usb_flow
from fwasset.core.asset_index import AssetIndexError, hide_item, load_hidden_items, unhide_item
from fwasset.core.firmware_catalog import enabled_firmware_types
from fwasset.ui.tool_center_panel import ToolCenterPanel
from fwasset.core.services.scan_service import build_cached_scan_result, build_scan_result
from fwasset.core.settings import DEFAULT_ROOT
from fwasset.core.types import FirmwareAsset
from fwasset.ui.asset_tree import AssetTreeView
from fwasset.ui.base_panel import BaseFlashPanel
from fwasset.ui.design_tokens import (
    BG_CARD,
    BG_HOVER,
    BG_INPUT,
    BORDER_COLOR,
    COLOR_PRIMARY,
    FONT_FAMILY,
    FONT_SIZE_LG,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from fwasset.ui.operation_panels import get_panel
from fwasset.ui.operation_panels.disabled_panel import DisabledPanel
from fwasset.ui.panels.detail_panel import DetailPanel
from fwasset.ui.panels.header_bar import HeaderBar
from fwasset.ui.panels.log_panel import LogPanel
from fwasset.ui.shared_widgets import section_title, make_bool_var
from fwasset.ui.view_models.asset_filter_model import AssetFilterModel
from fwasset.ui.view_models.asset_selection_model import AssetSelectionModel
from fwasset.ui.view_models.tree_expansion_model import TreeExpansionModel


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
        self._has_index_assets = False
        self.asset_filter_model = AssetFilterModel()
        self.asset_selection_model = AssetSelectionModel()
        self.asset_tree: AssetTreeView | None = None
        self._tree_expansion = TreeExpansionModel()
        self._scan_cancel_event: threading.Event | None = None

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
        from fwasset.ui.design_tokens import BG_INPUT, BG_HOVER, COLOR_PRIMARY, FONT_FAMILY, FONT_SIZE_LG, TEXT_PRIMARY

        brand_frame = ctk.CTkFrame(parent, fg_color="transparent")
        brand_frame.pack(fill="x", padx=24, pady=(24, 12))

        left = ctk.CTkFrame(brand_frame, fg_color="transparent")
        left.pack(side="left")

        ctk.CTkLabel(left, text="⚡", font=(FONT_FAMILY, 24), text_color=COLOR_PRIMARY).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(left, text=title, font=(FONT_FAMILY, FONT_SIZE_LG, "bold"), text_color=TEXT_PRIMARY).pack(side="left")

        ctk.CTkButton(
            brand_frame, text="🔧 工具中心", width=100, height=32,
            fg_color=BG_INPUT, text_color=TEXT_PRIMARY, hover_color=BG_HOVER,
            command=self._open_tool_center,
        ).pack(side="right")

    def _open_tool_center(self):
        ToolCenterPanel(self.winfo_toplevel(), log_fn=self._log)

    def _make_bool_var(self, value: bool):
        return make_bool_var(self, value)

    def activate(self):
        super().activate()

    def deactivate(self):
        super().deactivate()

    def _build_sidebar(self):
        sidebar = self._build_sidebar_frame(width=760)
        self._build_brand_header_with_tools(sidebar, title="固件资源列表")

        search_sort_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        search_sort_frame.pack(fill="x", padx=20, pady=(0, 10))

        search_box = ctk.CTkEntry(
            search_sort_frame, height=36, corner_radius=8,
            placeholder_text="搜索 型号/版本/类型/目录",
            textvariable=self.search_var, fg_color=BG_CARD,
            border_width=1, border_color=BORDER_COLOR,
            font=(FONT_FAMILY, FONT_SIZE_MD),
        )
        search_box.pack(side="left", fill="x", expand=True, padx=(0, 8))

        quick_values = ["先选择固件类型", "全部类型", *self._type_label_to_key.keys()]
        self.type_quick_menu = ctk.CTkOptionMenu(
            search_sort_frame, values=quick_values, variable=self.type_quick_var,
            width=150, height=36, fg_color=BG_CARD, text_color=TEXT_PRIMARY,
            button_color=BG_CARD, button_hover_color=BG_HOVER,
            font=(FONT_FAMILY, FONT_SIZE_MD), command=self._select_single_type_filter,
        )
        self.type_quick_menu.pack(side="left", padx=(0, 8))

        self.sort_menu = ctk.CTkOptionMenu(
            search_sort_frame, values=["默认(名称)", "按型号", "按版本"],
            variable=self.sort_key_var, width=100, height=36, corner_radius=8,
            fg_color=BG_CARD, text_color=TEXT_PRIMARY,
            button_color=BG_CARD, button_hover_color=BG_HOVER,
            font=(FONT_FAMILY, FONT_SIZE_MD),
            command=lambda _value: self._filter_assets(),
        )
        self.sort_menu.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            search_sort_frame, text="清空", width=58, height=36,
            fg_color=BG_INPUT, text_color=TEXT_PRIMARY, hover_color=BG_HOVER,
            command=self._clear_type_filters,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkCheckBox(
            search_sort_frame, text="显示隐藏", variable=self.show_hidden_var,
            font=(FONT_FAMILY, FONT_SIZE_SM), text_color=TEXT_SECONDARY,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            search_sort_frame, text="扫描根目录", fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY, hover_color=BG_HOVER, width=96, height=36,
            command=self._on_scan_button_click,
        ).pack(side="right")
        self.scan_btn = search_sort_frame.winfo_children()[-1]

        self.asset_tree = AssetTreeView(
            sidebar,
            on_select_asset=self._select_asset,
            on_open_asset=self._open_asset_path,
            on_context_menu=self._show_hidden_context_menu,
            on_node_open=self._mark_tree_node_open,
            on_node_close=self._mark_tree_node_closed,
        )
        self.asset_tree.pack(fill="both", expand=True, padx=12, pady=(0, 8))

    def _select_all_type_filters(self):
        for var in self.type_filter_vars.values():
            var.set(True)
        self.type_quick_var.set("全部类型")
        self._tree_expansion.clear()
        self._filter_assets()

    def _clear_type_filters(self):
        for var in self.type_filter_vars.values():
            var.set(False)
        self.type_quick_var.set("先选择固件类型")
        self._tree_expansion.clear()
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
        self._tree_expansion.clear()
        self._filter_assets()

    def _build_main_view(self):
        main = self._build_main_container()
        main.grid_rowconfigure(1, weight=1)
        main.grid_rowconfigure(2, weight=0)
        self.header_bar = HeaderBar(main)
        self.header_bar.grid(row=0, column=0, sticky="ew", pady=(0, 24))
        cards_container = ctk.CTkFrame(main, fg_color="transparent")
        cards_container.grid(row=1, column=0, sticky="nsew", pady=(0, 24))
        cards_container.grid_columnconfigure(0, weight=1)
        cards_container.grid_columnconfigure(1, weight=0)
        cards_container.grid_rowconfigure(0, weight=1)

        self.detail_panel = DetailPanel(cards_container)
        self.detail_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        self.ops_card = ctk.CTkFrame(
            cards_container, fg_color=BG_CARD, corner_radius=12,
            border_width=1, border_color=BORDER_COLOR,
        )
        self.detail_panel.grid_forget()
        self.ops_card.grid(row=0, column=0, sticky="nsew")
        section_title(self.ops_card, "操作区")
        self.ops_body = ctk.CTkFrame(self.ops_card, fg_color="transparent")
        self.ops_body.pack(fill="both", expand=True, padx=0, pady=(0, 10))
        self._render_operation_panel(None)

        self.log_panel = LogPanel(main)
        self.log_panel.grid(row=2, column=0, sticky="ew")

    def _selected_types(self) -> set[str]:
        return {key for key, value in self.type_filter_vars.items() if bool(value.get())}

    def _selection_model(self) -> AssetSelectionModel:
        model = getattr(self, "asset_selection_model", None)
        if model is None:
            model = AssetSelectionModel()
            self.asset_selection_model = model
        return model

    @property
    def _selected_idx(self) -> int:
        return self._selection_model().selected_idx

    @_selected_idx.setter
    def _selected_idx(self, idx: int) -> None:
        self._selection_model().set_selected_idx(idx)

    @property
    def _hidden_items(self) -> dict[str, str]:
        return self._selection_model().hidden_items

    @_hidden_items.setter
    def _hidden_items(self, hidden_items: dict[str, str]) -> None:
        self._selection_model().replace_hidden_items(hidden_items)

    def _reload_hidden_items(self):
        try:
            self._hidden_items = load_hidden_items()
        except AssetIndexError as exc:
            self._hidden_items = {}
            if hasattr(self, "_log"):
                self._log(str(exc))

    def _is_asset_hidden(self, asset: FirmwareAsset) -> bool:
        return self._selection_model().is_asset_hidden(asset)

    def _asset_hidden_type(self, asset: FirmwareAsset) -> str:
        return self._selection_model().asset_hidden_type(asset)

    def _common_asset_path(self, assets: list[FirmwareAsset], indices: list[int]) -> str:
        return self._filter_model().common_asset_path(assets, indices)

    def _show_hidden_context_menu(self, event, item_path: str, hide_type: str):
        if not item_path:
            return
        menu = tk.Menu(self, tearoff=0)
        is_hidden = self._selection_model().is_item_hidden(item_path)
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

    def _on_scan_button_click(self):
        if self._scan_cancel_event is not None:
            self._scan()
            return
        self._choose_root_and_scan()

    def _set_scan_button_cancelling(self):
        if hasattr(self, 'scan_btn') and self.scan_btn:
            self.scan_btn.configure(text="取消中...", state="disabled")

    def _scan(self):
        if self._scan_cancel_event is not None:
            self._scan_cancel_event.set()
            self._set_scan_button_cancelling()
            return

        root = self.root_dir.get().strip()
        if not root:
            messagebox.showwarning("提示", "请先选择程序根目录")
            return

        cancel_event = threading.Event()
        self._scan_cancel_event = cancel_event
        if hasattr(self, 'scan_btn') and self.scan_btn:
            self.scan_btn.configure(state="normal")
            self.scan_btn.configure(text="取消扫描")

        def _work(log_fn):
            return build_scan_result(root, log_fn=log_fn, cancel_event=cancel_event)

        def _done(result):
            if self._scan_cancel_event is cancel_event:
                self._scan_cancel_event = None
            if hasattr(self, 'scan_btn') and self.scan_btn:
                self.scan_btn.configure(state="normal")
                self.scan_btn.configure(text="扫描根目录")
            if result.get("code") == "cancelled":
                self._log("扫描已取消")
                return
            if not result.get("ok"):
                messagebox.showerror("扫描失败", str(result.get("message", "未知错误")))
                return
            payload = result.get("payload", {}) or {}
            self._has_index_assets = bool(payload.get("assets", []))
            self._selection_model().clear_selection()
            self._tree_expansion.clear()
            self._filter_assets()
            if not self._has_index_assets:
                self._render_empty_list_hint("当前扫描没有发现程序资源。")

        self._run_task("扫描目录", _work, _done)

    def _load_cached_assets(self):
        def _work(log_fn):
            return build_cached_scan_result(log_fn=log_fn)

        def _done(result):
            if not result.get("ok"):
                self._log(str(result.get("message", "本地资产索引读取失败")))
                return
            payload = result.get("payload", {}) or {}
            self._has_index_assets = bool(payload.get("asset_count", 0) or payload.get("assets", []))
            self._selection_model().clear_selection()
            self._tree_expansion.clear()
            self._filter_assets()
            if not self._has_index_assets:
                self._render_empty_list_hint("本地暂无资产索引，请点击扫描根目录生成。")

        self._run_task("读取本地索引", _work, _done)

    def _filter_model(self) -> AssetFilterModel:
        model = getattr(self, "asset_filter_model", None)
        if model is None:
            model = AssetFilterModel()
            self.asset_filter_model = model
        return model

    def _sort_assets(self, items: list[FirmwareAsset]) -> list[FirmwareAsset]:
        return self._filter_model().sort_assets(
            items, sort_label=self.sort_key_var.get(), ascending=bool(self.sort_asc_var.get()),
        )

    def _filter_assets(self):
        keyword = self.search_var.get().strip()
        selected_types = self._selected_types()
        show_hidden = bool(self.show_hidden_var.get())
        if not selected_types:
            self.assets = []
            self._render_asset_tree()
            return

        try:
            queried = self._filter_model().query_filtered_assets(
                keyword=keyword, selected_types=selected_types,
                sort_label=self.sort_key_var.get(), ascending=bool(self.sort_asc_var.get()),
                show_hidden=show_hidden, is_hidden=self._is_asset_hidden,
            )
        except AssetIndexError as exc:
            self._log(str(exc))
            queried = []

        self.assets = queried
        if keyword:
            self._tree_expansion.expand_all_default(
                self.assets, self._filter_model(), self._hidden_items, self._is_asset_hidden,
            )
        self._render_asset_tree()

    def _render_asset_tree(self):
        self._ensure_default_tree_expanded()
        groups = self._build_tree_groups(self.assets)
        visible_asset_indices = self._visible_tree_asset_indices(groups)
        hidden_indices = {idx for idx, asset in enumerate(self.assets) if self._is_asset_hidden(asset)}
        if self.asset_tree is not None:
            self.asset_tree.populate(groups, self.assets, self._tree_expansion.expanded, -1, hidden_indices)
        if self.assets:
            next_idx = self._selection_model().clamped_selected_idx(len(self.assets))
            self._select_asset(next_idx)
        else:
            self._selection_model().clear_selection()
            self._clear_selection()
            if self._has_index_assets and not self._selected_types():
                self._render_empty_list_hint("请先在上方选择一种固件类型。")
            elif self._has_index_assets:
                self._render_empty_list_hint("当前筛选条件下没有匹配的程序。")

        if self.assets and not visible_asset_indices:
            self._render_empty_list_hint("当前树节点已折叠，展开系列或型号目录后查看程序。")

    def _tree_key(self, kind: str, *parts: object) -> str:
        return self._filter_model().tree_key(kind, *parts)

    def _is_tree_node_open(self, key: str) -> bool:
        return self._tree_expansion.is_open(key)

    def _toggle_tree_node(self, key: str):
        self._tree_expansion.toggle(key)
        self._render_asset_tree()

    def _mark_tree_node_open(self, key: str):
        self._tree_expansion.mark_open(key)

    def _mark_tree_node_closed(self, key: str):
        self._tree_expansion.mark_closed(key)

    def _ensure_default_tree_expanded(self):
        if self._tree_expansion.expanded or not self.assets:
            return
        self._tree_expansion.expand_all_default(
            self.assets, self._filter_model(), self._hidden_items, self._is_asset_hidden,
        )

    def _build_tree_groups(self, assets: list[FirmwareAsset]) -> list[dict]:
        return self._filter_model().build_tree_groups(
            assets, hidden_items=self._hidden_items, is_hidden=self._is_asset_hidden,
        )

    def _visible_tree_asset_indices(self, groups: list[dict]) -> list[int]:
        return self._filter_model().visible_tree_asset_indices(groups, self._tree_expansion.expanded)

    def _render_empty_list_hint(self, text: str):
        if self.asset_tree is not None and hasattr(self.asset_tree, "show_message"):
            self.asset_tree.show_message(text)

    def _apply_card_visual_state(self, idx: int, selected: bool):
        if idx < 0:
            return
        if self.asset_tree is not None and selected:
            self.asset_tree.focus_asset(idx)

    def _clear_selection(self):
        self.header_bar.clear()
        self.detail_panel.clear()
        self._render_operation_panel(None)

    def _select_asset(self, idx: int):
        if idx < 0 or idx >= len(self.assets):
            return
        previous_idx = self._selected_idx
        self._selection_model().set_selected_idx(idx)
        if previous_idx != idx:
            self._apply_card_visual_state(previous_idx, False)
            self._apply_card_visual_state(idx, True)

        asset = self.assets[idx]
        self.header_bar.update_from_asset(asset)
        self.detail_panel.update_from_asset(asset)
        self._render_operation_panel(asset)
        self._log(f"已选择: {asset.get('model', '')} {asset.get('version', '')} [{asset.get('firmware_label', '')}]")

    def _open_in_explorer(self, folder_path: str, model: str = "", version: str = ""):
        try:
            os.startfile(folder_path)
        except OSError as exc:
            messagebox.showerror("打开失败", f"打开目录失败: {exc}")
            return
        self._log(f"快速定位已打开: {model} {version} -> {folder_path}")

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
        selected = self._selection_model().selected_asset(self.assets)
        if selected is None:
            messagebox.showwarning("提示", "请先选择一个条目")
            return None
        return selected

    def _selected_flash_mode(self) -> str:
        selected = self._selection_model().selected_asset(self.assets)
        if selected is None:
            return ""
        return asset_flash_mode(selected)

    def _asset_rom_pkg_files(self, asset: FirmwareAsset) -> tuple[str, str]:
        return asset_rom_pkg_files(asset)

    def _asset_usb_flow(self, asset: FirmwareAsset) -> str:
        return asset_usb_flow(asset)

    def _reset_ops_body(self):
        for widget in self.ops_body.winfo_children():
            widget.destroy()

    def _render_operation_panel(self, asset: FirmwareAsset | None):
        self._reset_ops_body()
        if asset is None:
            ctk.CTkLabel(
                self.ops_body, text="选择资源后显示对应操作",
                font=(FONT_FAMILY, FONT_SIZE_LG), text_color=TEXT_PRIMARY,
            ).pack(anchor="w", padx=20, pady=20)
            return

        self._render_selected_detail_summary(asset)
        flash_mode = asset_flash_mode(asset)
        PanelClass = get_panel(flash_mode) or DisabledPanel
        panel = PanelClass(self.ops_body, asset=asset, log_fn=self._log, panel_host=self)
        panel.build()
        panel.pack(fill="both", expand=True)

    def _render_selected_detail_summary(self, asset: FirmwareAsset):
        summary = ctk.CTkFrame(self.ops_body, fg_color="transparent")
        summary.pack(fill="x", padx=20, pady=(12, 12))
        for label_text, value_text in [
            ("方式", asset_flash_mode(asset) or "-"),
            ("目录", str(asset.get("path", "") or "-")),
            ("文件", ", ".join(str(name) for name in asset.get("files", [])[:4]) or "-"),
        ]:
            row = ctk.CTkFrame(summary, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row, text=label_text, width=40, anchor="w",
                font=(FONT_FAMILY, FONT_SIZE_MD, "bold"), text_color=TEXT_PRIMARY,
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=value_text, anchor="w", justify="left", wraplength=360,
                font=(FONT_FAMILY, FONT_SIZE_MD), text_color=TEXT_PRIMARY,
            ).pack(side="left", fill="x", expand=True, padx=(8, 0))

    def _asset_path_text(self, asset: FirmwareAsset | None = None) -> str:
        selected = asset or self._selected_asset()
        if not selected:
            return ""
        return asset_dir_path(selected)

    def _primary_file_path_text(self, asset: FirmwareAsset | None = None) -> str:
        selected = asset or self._selected_asset()
        if not selected:
            return ""
        return asset_primary_file_path(selected)

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
        self._open_current_asset_dir()


HandcontrolPanel = FirmwareListPanel
