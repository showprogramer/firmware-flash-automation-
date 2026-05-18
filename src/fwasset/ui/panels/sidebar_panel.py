from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from fwasset.ui.asset_tree import AssetTreeView
from fwasset.ui.design_tokens import (
    BG_CARD,
    BG_HOVER,
    BG_INPUT,
    BG_SIDEBAR,
    BORDER_COLOR,
    COLOR_PRIMARY,
    FONT_FAMILY,
    FONT_SIZE_LG,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    HEIGHT_LG,
    HEIGHT_MD,
    ICON_LG,
    RADIUS_SM,
    SIDEBAR_WIDTH,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XL,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class SidebarPanel(ctk.CTkFrame):
    """Left-side search/filter controls and asset tree."""

    def __init__(
        self,
        master,
        *,
        search_var,
        sort_key_var,
        show_hidden_var,
        type_quick_var,
        type_label_to_key: dict[str, str],
        on_open_tool_center: Callable[[], None],
        on_select_single_type_filter: Callable[[str], None],
        on_filter_assets: Callable[[], None],
        on_clear_type_filters: Callable[[], None],
        on_scan_button_click: Callable[[], None],
        on_select_asset: Callable[[int], None],
        on_open_asset: Callable[[int], None],
        on_context_menu: Callable[[object, str, str], None],
        on_node_open: Callable[[str], None],
        on_node_close: Callable[[str], None],
        width: int = SIDEBAR_WIDTH,
        **kwargs,
    ) -> None:
        super().__init__(master, width=width, corner_radius=0, fg_color=BG_SIDEBAR, **kwargs)
        self.grid_propagate(False)
        self._build_brand_header(on_open_tool_center)
        self._build_search_controls(
            search_var=search_var,
            sort_key_var=sort_key_var,
            show_hidden_var=show_hidden_var,
            type_quick_var=type_quick_var,
            type_label_to_key=type_label_to_key,
            on_select_single_type_filter=on_select_single_type_filter,
            on_filter_assets=on_filter_assets,
            on_clear_type_filters=on_clear_type_filters,
            on_scan_button_click=on_scan_button_click,
        )
        self.asset_tree = AssetTreeView(
            self,
            on_select_asset=on_select_asset,
            on_open_asset=on_open_asset,
            on_context_menu=on_context_menu,
            on_node_open=on_node_open,
            on_node_close=on_node_close,
        )
        self.asset_tree.pack(fill="both", expand=True, padx=SPACE_SM, pady=(0, SPACE_SM))

    def _build_brand_header(self, on_open_tool_center: Callable[[], None]) -> None:
        brand_frame = ctk.CTkFrame(self, fg_color="transparent")
        brand_frame.pack(fill="x", padx=SPACE_XL, pady=(SPACE_LG, SPACE_SM))

        left = ctk.CTkFrame(brand_frame, fg_color="transparent")
        left.pack(side="left")
        ctk.CTkLabel(left, text="⚡", font=(FONT_FAMILY, ICON_LG), text_color=COLOR_PRIMARY).pack(side="left", padx=(0, SPACE_SM))
        ctk.CTkLabel(left, text="固件资源列表", font=(FONT_FAMILY, FONT_SIZE_LG, "bold"), text_color=TEXT_PRIMARY).pack(side="left")

        ctk.CTkButton(
            brand_frame,
            text="工具中心",
            width=100,
            height=HEIGHT_MD,
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            corner_radius=RADIUS_SM,
            command=on_open_tool_center,
        ).pack(side="right")

    def _build_search_controls(
        self,
        *,
        search_var,
        sort_key_var,
        show_hidden_var,
        type_quick_var,
        type_label_to_key: dict[str, str],
        on_select_single_type_filter: Callable[[str], None],
        on_filter_assets: Callable[[], None],
        on_clear_type_filters: Callable[[], None],
        on_scan_button_click: Callable[[], None],
    ) -> None:
        search_sort_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_sort_frame.pack(fill="x", padx=SPACE_LG, pady=(0, SPACE_SM))

        search_box = ctk.CTkEntry(
            search_sort_frame,
            height=HEIGHT_LG,
            corner_radius=RADIUS_SM,
            placeholder_text="搜索 型号/版本/类型/目录",
            textvariable=search_var,
            fg_color=BG_CARD,
            border_width=1,
            border_color=BORDER_COLOR,
            font=(FONT_FAMILY, FONT_SIZE_MD),
        )
        search_box.pack(side="left", fill="x", expand=True, padx=(0, SPACE_SM))

        quick_values = ["先选择固件类型", "全部类型", *type_label_to_key.keys()]
        self.type_quick_menu = ctk.CTkOptionMenu(
            search_sort_frame,
            values=quick_values,
            variable=type_quick_var,
            width=150,
            height=HEIGHT_LG,
            fg_color=BG_CARD,
            text_color=TEXT_PRIMARY,
            button_color=BG_CARD,
            button_hover_color=BG_HOVER,
            font=(FONT_FAMILY, FONT_SIZE_MD),
            command=on_select_single_type_filter,
        )
        self.type_quick_menu.pack(side="left", padx=(0, SPACE_SM))

        self.sort_menu = ctk.CTkOptionMenu(
            search_sort_frame,
            values=["默认(名称)", "按型号", "按版本"],
            variable=sort_key_var,
            width=100,
            height=HEIGHT_LG,
            corner_radius=RADIUS_SM,
            fg_color=BG_CARD,
            text_color=TEXT_PRIMARY,
            button_color=BG_CARD,
            button_hover_color=BG_HOVER,
            font=(FONT_FAMILY, FONT_SIZE_MD),
            command=lambda _value: on_filter_assets(),
        )
        self.sort_menu.pack(side="left", padx=(0, SPACE_SM))

        ctk.CTkButton(
            search_sort_frame,
            text="清空",
            width=58,
            height=HEIGHT_LG,
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            corner_radius=RADIUS_SM,
            command=on_clear_type_filters,
        ).pack(side="left", padx=(0, SPACE_SM))
        ctk.CTkCheckBox(
            search_sort_frame,
            text="显示隐藏",
            variable=show_hidden_var,
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=TEXT_SECONDARY,
        ).pack(side="left", padx=(0, SPACE_SM))
        self.scan_btn = ctk.CTkButton(
            search_sort_frame,
            text="扫描根目录",
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            width=96,
            height=HEIGHT_LG,
            corner_radius=RADIUS_SM,
            command=on_scan_button_click,
        )
        self.scan_btn.pack(side="right")