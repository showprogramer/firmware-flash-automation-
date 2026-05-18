from __future__ import annotations

import hashlib
import tkinter as tk
from tkinter import ttk
from typing import Callable

import customtkinter as ctk

from fwasset.core.types import FirmwareAsset
from fwasset.ui.design_tokens import (
    BG_CARD,
    BG_SIDEBAR,
    COLOR_PRIMARY,
    FONT_FAMILY,
    FONT_SIZE_MD,
    HEIGHT_LG,
    RADIUS_SM,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


def _resolve(token):
    """Resolve a customtkinter light/dark color tuple to a single color string."""
    if isinstance(token, tuple):
        return token[ctk.AppearanceModeTracker.get_mode()]
    return token


class AssetTreeView:
    """High-density firmware asset tree backed by ttk.Treeview."""

    def __init__(
        self,
        master,
        *,
        on_select_asset: Callable[[int], None],
        on_open_asset: Callable[[int], None],
        on_context_menu: Callable[[object, str, str], None],
        on_node_open: Callable[[str], None],
        on_node_close: Callable[[str], None],
    ):
        self._on_select_asset = on_select_asset
        self._on_open_asset = on_open_asset
        self._on_context_menu = on_context_menu
        self._on_node_open = on_node_open
        self._on_node_close = on_node_close
        self._asset_by_iid: dict[str, int] = {}
        self._context_by_iid: dict[str, tuple[str, str]] = {}
        self._node_key_by_iid: dict[str, str] = {}
        self._iid_by_asset_idx: dict[int, str] = {}

        self.frame = ctk.CTkFrame(master, corner_radius=0, fg_color=BG_SIDEBAR)
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(0, weight=1)

        self._configure_style()
        columns = ("program_dir", "version")
        self.tree = ttk.Treeview(
            self.frame,
            columns=columns,
            show="tree headings",
            selectmode="browse",
            style="Asset.Treeview",
        )
        self.tree.heading("#0", text="系列 / 型号", anchor="w")
        self.tree.heading("program_dir", text="程序目录", anchor="w")
        self.tree.heading("version", text="版本", anchor="w")
        self.tree.column("#0", width=300, minwidth=200, stretch=True)
        self.tree.column("program_dir", width=240, minwidth=150, stretch=True)
        self.tree.column("version", width=120, minwidth=80, stretch=False)
        self.tree.tag_configure("group", foreground=_resolve(TEXT_PRIMARY), font=(FONT_FAMILY, FONT_SIZE_MD, "bold"))
        self.tree.tag_configure("hidden", foreground=_resolve(TEXT_SECONDARY))

        y_scroll = ttk.Scrollbar(self.frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=y_scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")

        self.tree.bind("<<TreeviewSelect>>", self._handle_select)
        self.tree.bind("<<TreeviewOpen>>", self._handle_open_node)
        self.tree.bind("<<TreeviewClose>>", self._handle_close_node)
        self.tree.bind("<Double-Button-1>", self._handle_double_click)
        self.tree.bind("<Button-3>", self._handle_context_menu)

    def _configure_style(self):
        try:
            style = ttk.Style(self.frame)
            style.configure(
                "Asset.Treeview",
                rowheight=36,
                font=(FONT_FAMILY, FONT_SIZE_MD),
                background=_resolve(BG_CARD),
                fieldbackground=_resolve(BG_CARD),
                foreground=_resolve(TEXT_PRIMARY),
            )
            style.configure("Asset.Treeview.Heading", font=(FONT_FAMILY, FONT_SIZE_MD, "bold"))
            style.map("Asset.Treeview", background=[("selected", _resolve(COLOR_PRIMARY))], foreground=[("selected", "white")])
        except tk.TclError:
            pass

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def focus_asset(self, idx: int):
        iid = self._iid_by_asset_idx.get(idx)
        if not iid:
            return
        try:
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.tree.see(iid)
        except tk.TclError:
            return

    def clear(self):
        self._asset_by_iid.clear()
        self._context_by_iid.clear()
        self._node_key_by_iid.clear()
        self._iid_by_asset_idx.clear()
        children = self.tree.get_children("")
        if children:
            self.tree.delete(*children)

    def show_message(self, text: str):
        self.clear()
        self.tree.insert("", "end", text=text, values=("", ""), tags=("group",))

    def populate(
        self,
        groups: list[dict],
        assets: list[FirmwareAsset],
        expanded_keys: set[str],
        selected_idx: int,
        hidden_indices: set[int] | None = None,
    ):
        self.clear()
        hidden_indices = hidden_indices or set()
        for series_node in groups:
            series_key = str(series_node["key"])
            series_iid = self._iid(series_key)
            self._insert_node(
                "",
                series_iid,
                series_key,
                text=f"{series_node['series']}  ({series_node['model_count']} 个目录)",
                values=("", ""),
                open_node=series_key in expanded_keys,
            )
            for model_node in series_node["models"]:
                for type_node in model_node["types"]:
                    for idx in type_node["asset_indices"]:
                        asset = assets[idx]
                        asset_iid = self._iid(f"asset|{idx}|{asset.get('path', '')}")
                        self._asset_by_iid[asset_iid] = idx
                        self._iid_by_asset_idx[idx] = asset_iid
                        tags = ("hidden",) if idx in hidden_indices else ()
                        self._context_by_iid[asset_iid] = (str(asset.get("path", "") or ""), "asset")
                        self.tree.insert(
                            series_iid,
                            "end",
                            iid=asset_iid,
                            text=str(asset.get("model", "") or asset.get("directory_name", "") or "-"),
                            values=(
                                asset.get("directory_name", "") or "-",
                                asset.get("version", "") or "-",
                            ),
                            tags=tags,
                        )
        self.focus_asset(selected_idx)

    def _insert_node(
        self,
        parent: str,
        iid: str,
        node_key: str,
        *,
        text: str,
        values: tuple,
        open_node: bool,
        context: tuple[str, str] | None = None,
        tags: tuple[str, ...] = ("group",),
    ):
        self._node_key_by_iid[iid] = node_key
        if context is not None:
            self._context_by_iid[iid] = context
        if self.tree.exists(iid):
            try:
                self.tree.delete(iid)
            except tk.TclError:
                pass
        self.tree.insert(parent, "end", iid=iid, text=text, values=values, open=open_node, tags=tags)

    def _selected_iid(self) -> str:
        selected = self.tree.selection()
        if selected:
            return str(selected[0])
        return str(self.tree.focus() or "")

    def _row_iid_from_event(self, event) -> str:
        try:
            iid = str(self.tree.identify_row(event.y))
        except Exception:
            iid = ""
        return iid or self._selected_iid()

    def _handle_select(self, _event):
        idx = self._asset_by_iid.get(self._selected_iid())
        if idx is not None:
            self._on_select_asset(idx)

    def _handle_open_node(self, _event):
        key = self._node_key_by_iid.get(self._selected_iid())
        if key:
            self._on_node_open(key)

    def _handle_close_node(self, _event):
        key = self._node_key_by_iid.get(self._selected_iid())
        if key:
            self._on_node_close(key)

    def _handle_double_click(self, event):
        idx = self._asset_by_iid.get(self._row_iid_from_event(event))
        if idx is not None:
            self._on_open_asset(idx)

    def _handle_context_menu(self, event):
        iid = self._row_iid_from_event(event)
        if iid:
            self.tree.selection_set(iid)
        path, hide_type = self._context_by_iid.get(iid, ("", "asset"))
        if path:
            self._on_context_menu(event, path, hide_type)

    @staticmethod
    def _iid(value: str) -> str:
        digest = hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()[:16]
        return f"asset_tree_{digest}"