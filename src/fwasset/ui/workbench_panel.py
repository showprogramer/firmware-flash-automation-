from __future__ import annotations

import os
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from fwasset.core.services.scan_service import build_cached_scan_result, build_scan_result
from fwasset.core.settings import DEFAULT_ROOT
from fwasset.ui.base_panel import BaseFlashPanel
from fwasset.ui.design_tokens import (
    BG_CARD,
    BG_HOVER,
    BG_INPUT,
    BG_SIDEBAR,
    BORDER_COLOR,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    FONT_FAMILY,
    FONT_SIZE_LG,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    RADIUS_SM,
    RADIUS_LG,
    SIDEBAR_WIDTH,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XL,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
    TEXT_ON_PRIMARY,
    apply_ttk_theme,
)
from fwasset.ui.operation_panels.registry import get_panel
from fwasset.ui.panels.data_grid_panel import DataGridPanel
from fwasset.ui.panels.log_panel import LogPanel
from fwasset.ui.view_models.scheme_workbench_model import (
    SchemeWorkbenchModel,
    WorkbenchSelection,
    ModuleCardData,
    ModuleVariant,
)
from fwasset.ui.view_models.scan_state_model import ScanStateModel


# 纯函数助手移至 workbench_helpers（CTk/Qt 双壳共用）；此处 re-export 保持旧导入路径。
from fwasset.ui.workbench_helpers import (  # noqa: F401  (re-export for tests/back-compat)
    MODEL_CHIP_LIMIT,
    flash_mode_label,
    model_chip_values,
)

SEARCH_REFRESH_DEBOUNCE_MS = 180


class WorkbenchPanel(BaseFlashPanel):
    def __init__(self, master):
        super().__init__(master)

        apply_ttk_theme()  # Apply custom ttk styling

        self.root_dir = tk.StringVar(value=DEFAULT_ROOT)
        self.search_var = tk.StringVar(value="")

        self.workbench_model = SchemeWorkbenchModel()
        self.scan_state_model = ScanStateModel()
        self.current_selection = WorkbenchSelection()
        self._available_models: list[str] = []
        self._model_buttons: dict[str, ctk.CTkButton] = {}
        self._more_model_combo: ctk.CTkComboBox | None = None

        # Details operation panel container reference
        self.active_operation_panel = None
        self._ops_container = None

        self.grid_columnconfigure(0, weight=0, minsize=SIDEBAR_WIDTH)  # Left Sidebar
        self.grid_columnconfigure(1, weight=4, minsize=600)  # Right Main Area

        self._build_sidebar()
        self._build_main_view()

        self.search_var.trace_add("write", lambda *_: self._on_search_changed())

        # Auto-refresh U盘列表 on startup so the global selector shows current
        # drives without requiring the user to click 「刷新」. Idempotent — the
        # 「刷新」 button remains for re-scanning after a drive is plugged in.
        self.after(100, self._refresh_usb)
        self.after(100, self._load_cached_assets)

    # --- Sidebar ---
    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=SIDEBAR_WIDTH, fg_color=BG_SIDEBAR, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(1, weight=1)

        nav_header = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav_header.grid(row=0, column=0, sticky="ew", padx=SPACE_LG, pady=(SPACE_LG, SPACE_MD))
        ctk.CTkLabel(
            nav_header,
            text="程序资产",
            anchor="w",
            font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            nav_header,
            text="通用模块与定制方案",
            anchor="w",
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=TEXT_TERTIARY,
        ).pack(anchor="w", pady=(2, 0))

        # Tree Frame
        self.tree_scroll = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        self.tree_scroll.grid(row=1, column=0, sticky="nsew", padx=SPACE_SM)
        self.tree_scroll.grid_columnconfigure(0, weight=1)

        # Bottom controls
        bottom_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        bottom_frame.grid(row=2, column=0, sticky="ew", padx=SPACE_LG, pady=SPACE_LG)
        bottom_frame.grid_columnconfigure(0, weight=1)

        self.scan_btn = ctk.CTkButton(
            bottom_frame,
            text="扫描目录",
            command=self._on_scan_button_click,
            fg_color=COLOR_PRIMARY,
            height=36,
            corner_radius=RADIUS_SM,
        )
        self.scan_btn.grid(row=0, column=0, sticky="ew")

    # --- Main View ---
    def _build_main_view(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=SPACE_LG, pady=SPACE_LG)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)  # Grid gets most space

        # Header
        self.main_header = ctk.CTkFrame(
            main,
            fg_color=BG_CARD,
            corner_radius=RADIUS_LG,
            border_width=1,
            border_color=BORDER_COLOR,
            height=118,
        )
        self.main_header.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_LG))
        self.main_header.grid_propagate(False)
        self.main_header.grid_columnconfigure(0, weight=1)
        self.main_header.grid_rowconfigure(1, weight=1)

        self.header_title = ctk.CTkLabel(
            self.main_header,
            text="请选择左侧分类进行过滤",
            font=(FONT_FAMILY, 20, "bold"),
            text_color=TEXT_PRIMARY,
        )
        self.header_title.grid(row=0, column=0, sticky="w", padx=SPACE_LG, pady=(SPACE_LG, SPACE_SM))

        self.header_badge = ctk.CTkLabel(
            self.main_header,
            text="",
            font=(FONT_FAMILY, FONT_SIZE_MD),
            text_color=COLOR_PRIMARY
        )
        self.header_badge.grid(row=0, column=1, sticky="e", padx=SPACE_LG, pady=(SPACE_LG, SPACE_SM))

        filter_row = ctk.CTkFrame(self.main_header, fg_color="transparent")
        filter_row.grid(row=1, column=0, columnspan=2, sticky="ew", padx=SPACE_LG, pady=(0, SPACE_LG))
        filter_row.grid_columnconfigure(1, weight=1)
        filter_row.grid_columnconfigure(2, weight=2)

        ctk.CTkLabel(
            filter_row,
            text="型号",
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
            text_color=TEXT_SECONDARY,
        ).grid(row=0, column=0, sticky="w", padx=(0, SPACE_SM))

        self.model_chip_frame = ctk.CTkFrame(filter_row, fg_color="transparent")
        self.model_chip_frame.grid(row=0, column=1, sticky="ew", padx=(0, SPACE_LG))
        for column in range(MODEL_CHIP_LIMIT + 1):
            self.model_chip_frame.grid_columnconfigure(column, weight=1)

        self.model_hint = ctk.CTkLabel(
            self.model_chip_frame,
            text="扫描后显示可选型号",
            anchor="w",
            font=(FONT_FAMILY, FONT_SIZE_MD),
            text_color=TEXT_TERTIARY,
        )
        self.model_hint.grid(row=0, column=0, sticky="w")

        search_entry = ctk.CTkEntry(
            filter_row,
            textvariable=self.search_var,
            placeholder_text="搜索模块 / 版本 / 方案 / 平台",
            height=36,
            corner_radius=RADIUS_SM,
            border_color=BORDER_COLOR,
            fg_color=BG_INPUT,
            font=(FONT_FAMILY, FONT_SIZE_MD),
        )
        search_entry.grid(row=0, column=2, sticky="ew")

        # U盘选择器（顶部紧凑版）：手控 UI 等 auto_usb 流程通过
        # `panel_host.get_global_usb_drive()` 拿盘符，这里给用户一个常驻入口。
        # 放在搜索框右侧；不与操作区集成（保持 Step C 操作区精简原则）。
        ctk.CTkLabel(
            filter_row,
            text="U 盘",
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
            text_color=TEXT_SECONDARY,
        ).grid(row=0, column=3, sticky="w", padx=(SPACE_LG, SPACE_SM))

        self.usb_menu = ctk.CTkComboBox(
            filter_row,
            variable=self.usb_drive,
            values=[""],
            width=110,
            height=36,
            corner_radius=RADIUS_SM,
            border_color=BORDER_COLOR,
            fg_color=BG_INPUT,
            font=(FONT_FAMILY, FONT_SIZE_MD),
        )
        self.usb_menu.grid(row=0, column=4, sticky="ew", padx=(0, SPACE_SM))

        ctk.CTkButton(
            filter_row,
            text="刷新",
            width=60,
            height=36,
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            command=self._refresh_usb,
        ).grid(row=0, column=5, sticky="e")

        # Data Grid Container
        self.grid_panel = DataGridPanel(
            main,
            self._on_grid_selection_changed,
            self._log,
            on_right_click=self._on_grid_right_click,
        )
        self.grid_panel.grid(row=1, column=0, sticky="nsew", pady=(0, SPACE_LG))

        # Operations Footer (Bottom section where actions appear when a row is selected)
        self.operations_frame = ctk.CTkFrame(
            main,
            fg_color=BG_CARD,
            corner_radius=RADIUS_LG,
            border_width=1,
            border_color=BORDER_COLOR,
            height=104,
        )
        self.operations_frame.grid(row=2, column=0, sticky="ew", pady=(0, SPACE_LG))
        self.operations_frame.grid_propagate(False)
        self.operations_frame.grid_columnconfigure(0, weight=1)
        self.operations_frame.grid_rowconfigure(1, weight=1)

        self.selection_summary = ctk.CTkLabel(
            self.operations_frame,
            text="未选择变体",
            anchor="w",
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=TEXT_SECONDARY,
        )
        self.selection_summary.grid(row=0, column=0, sticky="ew", padx=SPACE_LG, pady=(SPACE_SM, 0))

        # Initial empty state for operations
        self.ops_placeholder = ctk.CTkLabel(
            self.operations_frame,
            text="展开模块并选择具体变体以查看操作",
            text_color="gray",
            font=(FONT_FAMILY, FONT_SIZE_MD)
        )
        self.ops_placeholder.grid(row=1, column=0)

        # Log Panel
        self.log_panel = LogPanel(main, height=88)
        self.log_panel.grid(row=3, column=0, sticky="ew")

    # --- Interaction Logic ---
    def _on_model_changed(self, choice: str):
        if not choice or choice == "更多型号":
            return
        self.current_selection.model_name = choice
        self.current_selection.node_type = "all"
        self._refresh_model_selector()
        self._refresh_sidebar_tree()
        self._refresh_main_grid()

    def _refresh_model_selector(self, models: list[str] | None = None) -> None:
        if models is not None:
            self._available_models = models
        for widget in self.model_chip_frame.winfo_children():
            if widget is self.model_hint:
                continue
            widget.destroy()
        self._model_buttons.clear()
        self._more_model_combo = None

        chips, overflow = model_chip_values(self._available_models, self.current_selection.model_name)
        if not chips:
            self.model_hint.grid(row=0, column=0, sticky="w")
            return

        self.model_hint.grid_remove()
        for col, model in enumerate(chips):
            selected = model == self.current_selection.model_name
            button = ctk.CTkButton(
                self.model_chip_frame,
                text=model,
                height=32,
                corner_radius=RADIUS_SM,
                border_width=0 if selected else 1,
                border_color=BORDER_COLOR,
                font=(FONT_FAMILY, FONT_SIZE_MD, "bold" if selected else "normal"),
                fg_color=COLOR_PRIMARY if selected else "transparent",
                hover_color=COLOR_PRIMARY_HOVER if selected else BG_HOVER,
                text_color=TEXT_ON_PRIMARY if selected else TEXT_PRIMARY,
                command=lambda value=model: self._on_model_changed(value),
            )
            button.grid(row=0, column=col, sticky="ew", padx=(0, SPACE_SM))
            self._model_buttons[model] = button

        if overflow:
            combo = ctk.CTkComboBox(
                self.model_chip_frame,
                values=overflow,
                command=self._on_model_changed,
                height=32,
                corner_radius=RADIUS_SM,
                border_color=BORDER_COLOR,
                fg_color=BG_INPUT,
                font=(FONT_FAMILY, FONT_SIZE_MD),
                dropdown_font=(FONT_FAMILY, FONT_SIZE_MD),
            )
            combo.set("更多型号")
            combo.grid(row=0, column=len(chips), sticky="ew")
            self._more_model_combo = combo

    def _on_search_changed(self):
        # Debounce: rapid typing previously rebuilt the sidebar on every keystroke
        # (each rebuild destroys every child widget). Coalesce bursts of edits into
        # one rebuild at the end of typing.
        if getattr(self, "_search_after_id", None) is not None:
            try:
                self.after_cancel(self._search_after_id)
            except Exception:  # noqa: BLE001
                # Cancel may raise if the widget was destroyed mid-burst.
                pass
            self._search_after_id = None

        def _delayed_refresh():
            # Widget may have been torn down while the timer was pending.
            try:
                if not self.winfo_exists():
                    return
            except Exception:  # noqa: BLE001
                return
            self._search_after_id = None
            self._refresh_sidebar_tree()
            self._refresh_main_grid()

        try:
            self._search_after_id = self.after(SEARCH_REFRESH_DEBOUNCE_MS, _delayed_refresh)
        except Exception:  # noqa: BLE001
            # If scheduling itself fails (e.g. widget already gone), fall back
            # to an immediate refresh so the user still sees results.
            self._search_after_id = None
            self._refresh_sidebar_tree()
            self._refresh_main_grid()

    def _refresh_sidebar_tree(self):
        for widget in self.tree_scroll.winfo_children():
            widget.destroy()

        model_name = self.current_selection.model_name
        if not model_name:
            return

        tree_data = self.workbench_model.build_sidebar_tree(model_name)
        search_kw = self.search_var.get().lower().strip()

        row_idx = 0

        # Root Node - Show all modules
        all_btn = self._nav_button(
            text="全部程序与模块",
            selected=self.current_selection.node_type == "all",
            command=self._select_all_modules,
            bold=True,
        )
        all_btn.grid(row=row_idx, column=0, sticky="ew", pady=(0, SPACE_SM))
        row_idx += 1

        # Common Modules Section
        if tree_data["common"]:
            common_title = self._nav_section_label("通用模块")
            common_title.grid(row=row_idx, column=0, sticky="w", pady=(SPACE_SM, SPACE_SM))
            row_idx += 1

            for fw_label, count in tree_data["common"].items():
                if search_kw and search_kw not in fw_label.lower():
                    continue

                btn = self._nav_button(
                    text=f"{fw_label} ({count})",
                    selected=(
                        self.current_selection.node_type == "common_type"
                        and self.current_selection.common_type == fw_label
                    ),
                    command=lambda lbl=fw_label: self._select_common_module(lbl),
                )
                btn.grid(row=row_idx, column=0, sticky="ew", pady=1)
                row_idx += 1

        # Custom Schemes Section
        if tree_data["custom"]:
            custom_title = self._nav_section_label("定制方案")
            custom_title.grid(row=row_idx, column=0, sticky="w", pady=(SPACE_LG, SPACE_SM))
            row_idx += 1

            for scheme in tree_data["custom"]:
                if search_kw and search_kw not in scheme.lower():
                    continue

                btn = self._nav_button(
                    text=scheme,
                    selected=(
                        self.current_selection.node_type == "custom_scheme"
                        and self.current_selection.scheme_name == scheme
                    ),
                    command=lambda s=scheme: self._select_custom_scheme(s),
                )
                btn.grid(row=row_idx, column=0, sticky="ew", pady=1)
                row_idx += 1

    def _nav_section_label(self, text: str) -> ctk.CTkLabel:
        return ctk.CTkLabel(
            self.tree_scroll,
            text=text,
            anchor="w",
            font=(FONT_FAMILY, FONT_SIZE_SM, "bold"),
            text_color=TEXT_TERTIARY,
        )

    def _nav_button(self, text: str, selected: bool, command, bold: bool = False) -> ctk.CTkButton:
        return ctk.CTkButton(
            self.tree_scroll,
            text=text,
            anchor="w",
            height=34,
            corner_radius=RADIUS_SM,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold" if bold or selected else "normal"),
            fg_color=BG_HOVER if selected else "transparent",
            hover_color=BG_HOVER,
            text_color=COLOR_PRIMARY if selected else TEXT_PRIMARY,
            command=command,
        )

    def _select_all_modules(self):
        self.current_selection.node_type = "all"
        self._refresh_main_grid()

    def _select_common_module(self, fw_label: str):
        self.current_selection.node_type = "common_type"
        self.current_selection.common_type = fw_label
        self._refresh_main_grid()

    def _select_custom_scheme(self, scheme_name: str):
        self.current_selection.node_type = "custom_scheme"
        self.current_selection.scheme_name = scheme_name
        self._refresh_main_grid()

    def _refresh_main_grid(self):
        model_name = self.current_selection.model_name
        node_type = self.current_selection.node_type
        search_kw = self.search_var.get().lower().strip()

        if not model_name or not node_type:
            self.header_title.configure(text="请选择左侧分类进行过滤")
            self.header_badge.configure(text="")
            return

        cards_data: list[ModuleCardData] = []

        if node_type == "all":
            self.header_title.configure(text=f"全部模块 ({model_name})")
            self.header_badge.configure(text="全部")
            cards_data = self.workbench_model.get_all_modules(model_name, search_kw)
        elif node_type == "common_type":
            fw_label = self.current_selection.common_type
            self.header_title.configure(text=f"通用模块: {fw_label}")
            self.header_badge.configure(text="通用模块")
            cards_data = self.workbench_model.get_common_modules(model_name, fw_label, search_kw)

        elif node_type == "custom_scheme":
            scheme_name = self.current_selection.scheme_name
            self.header_title.configure(text=f"定制方案: {scheme_name}")
            self.header_badge.configure(text="整机七程序")
            # 定制方案走"整机七程序固定层级"可展开树（多变体收在模块行下）
            rows = self.workbench_model.get_scheme_module_tree(model_name, scheme_name, search_kw)
            self.grid_panel.populate_tree(rows)
            self._on_grid_selection_changed(None)
            return

        # 通用类型 / 全部：扁平卡片，每张包成单变体模块行后同走树渲染
        self.grid_panel.populate(cards_data)

        # Clear operations area since selection changed
        self._on_grid_selection_changed(None)

    def _on_grid_selection_changed(self, variant: "ModuleVariant | None"):
        # Tear down the whole previous operation container before rebuilding,
        # otherwise每次选行都会叠加旧面板。
        if self.active_operation_panel is not None:
            self.active_operation_panel.destroy()
            self.active_operation_panel = None
        if self._ops_container is not None:
            self._ops_container.destroy()
            self._ops_container = None

        # 选中多变体父模块行（无具体变体）→ 提示展开后再选
        if not variant:
            self.selection_summary.configure(text="未选择变体")
            self.ops_placeholder.configure(text="展开模块并选择具体变体以查看操作")
            self.ops_placeholder.grid(row=1, column=0)
            return

        self.ops_placeholder.grid_remove()

        # Load operation panel based on flash mode
        asset = variant.asset
        flash_mode = str(asset.get("flash_mode", "disabled"))
        self.selection_summary.configure(text=self._format_selection_summary(variant, flash_mode))
        PanelClass = get_panel(flash_mode)
        if PanelClass is None:
            self.ops_placeholder.configure(text=f"暂不支持的操作模式: {flash_mode}")
            self.ops_placeholder.grid(row=1, column=0)
            return

        # Single reusable container for the current selection's actions.
        # 不再在顶部堆"目录路径"标签（用户嫌杂）；双击行即可开目录。
        self._ops_container = ctk.CTkFrame(self.operations_frame, fg_color="transparent")
        self._ops_container.grid(row=1, column=0, sticky="nsew", padx=SPACE_LG, pady=(0, SPACE_SM))

        self.active_operation_panel = PanelClass(
            self._ops_container, asset=asset, log_fn=self._log, panel_host=self
        )
        self.active_operation_panel.pack(fill="both", expand=True)
        self.active_operation_panel.build()

    # --- 右键菜单（设为平台默认） ---
    def _on_grid_right_click(self, variant: ModuleVariant, x_root: int, y_root: int):
        menu = tk.Menu(self, tearoff=0)

        asset = variant.asset
        is_common = variant.source_kind == "common" and str(asset.get("category", "")) == "common"
        if is_common:
            platforms = self.workbench_model.platform_names(self.current_selection.model_name)
            current_defaults = set(self.workbench_model.default_platforms_for(asset))
            if not platforms:
                menu.add_command(label="设为平台默认（未找到平台配置）", state="disabled")
            elif len(platforms) == 1:
                p = platforms[0]
                if p in current_defaults:
                    menu.add_command(label=f"✓ 已是「{p}」默认程序", state="disabled")
                else:
                    menu.add_command(
                        label=f"设为「{p}」默认程序",
                        command=lambda: self._set_default_variant(p, variant),
                    )
            else:
                submenu = tk.Menu(menu, tearoff=0)
                for p in platforms:
                    if p in current_defaults:
                        submenu.add_command(label=f"✓ {p}（当前默认）", state="disabled")
                    else:
                        submenu.add_command(
                            label=p,
                            command=lambda name=p: self._set_default_variant(name, variant),
                        )
                menu.add_cascade(label="设为平台默认", menu=submenu)
            menu.add_separator()

        menu.add_command(label="打开目录", command=self._open_current_asset_dir)
        menu.add_command(label="复制目录路径", command=self._copy_asset_dir_path)

        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()

    def _set_default_variant(self, platform_name: str, variant: ModuleVariant):
        asset = variant.asset
        module = str(asset.get("firmware_label", "")) or str(asset.get("firmware_type", ""))
        shown = variant.name or str(asset.get("directory_name", ""))
        confirmed = messagebox.askyesno(
            title="设为平台默认",
            message=(
                f"将「{module} / {shown}」设为平台「{platform_name}」的默认程序？\n\n"
                "定制方案缺少该模块时，将使用此程序补齐。"
            ),
            parent=self.winfo_toplevel(),
        )
        if not confirmed:
            return
        result = self.workbench_model.set_default_variant(
            self.current_selection.model_name, platform_name, asset, log_fn=self._log
        )
        if not result["ok"]:
            self._log(result["message"])
            messagebox.showerror(title="设置失败", message=result["message"], parent=self.winfo_toplevel())
            return
        # 平台配置已就地重载，刷新表格让 ★默认 徽章与回源立即生效
        self._refresh_main_grid()

    def _format_selection_summary(self, variant: ModuleVariant, flash_mode: str) -> str:
        asset = variant.asset
        module = str(asset.get("firmware_label", "")) or str(asset.get("firmware_type", ""))
        version = variant.version or str(asset.get("version", "")) or "-"
        return (
            f"已选：{module}"
            f" / {variant.name or str(asset.get('directory_name', ''))}"
            f" · {version}"
            f" · {variant.source_label}"
            f" · {flash_mode_label(flash_mode)}"
        )

    # --- PanelHost Interface Implementations ---
    def _selected_asset(self) -> dict | None:
        data = self.grid_panel.get_selected_data()
        if data:
            return data.asset
        return None

    def _open_current_asset_dir(self):
        data = self.grid_panel.get_selected_data()
        if not data:
            return
        path = str(data.asset.get("path", ""))
        if not path or not os.path.exists(path):
            self._log("无法打开目录：路径不存在")
            return
        try:
            if os.name == "nt":
                os.startfile(path)
            elif os.name == "posix":
                subprocess.run(["xdg-open", path], check=False)
        except Exception as e:
            self._log(f"打开目录失败: {e}")

    def _copy_asset_dir_path(self):
        data = self.grid_panel.get_selected_data()
        if not data:
            return
        self._copy_to_clipboard(str(data.asset.get("path", "")))

    def _copy_primary_file_path(self):
        data = self.grid_panel.get_selected_data()
        if not data:
            return
        asset = data.asset
        files = list(asset.get("files", []))
        path = str(asset.get("path", ""))
        if files:
            from pathlib import Path as _P
            self._copy_to_clipboard(str(_P(path) / files[0]))
        else:
            self._copy_to_clipboard(path)

    def _launch_tool_and_open_asset_dir(self):
        # 委托给当前面板的工具启动，再打开目录
        panel = self.active_operation_panel
        if panel is not None and hasattr(panel, "_launch_current_tool"):
            panel._launch_current_tool()
        self._open_current_asset_dir()

    def _copy_to_clipboard(self, text: str):
        if not text:
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self._log(f"已复制: {text}")
        except Exception as exc:
            self._log(f"复制失败: {exc}")

    def get_global_usb_drive(self) -> str:
        return self.usb_drive.get()

    # --- Scanning and Loading Logic ---
    def _scan_state(self) -> ScanStateModel:
        return self.scan_state_model

    @property
    def _scan_cancel_event(self) -> threading.Event | None:
        return self._scan_state().cancel_event

    @_scan_cancel_event.setter
    def _scan_cancel_event(self, event: threading.Event | None) -> None:
        self._scan_state().replace(event)

    def _on_scan_button_click(self):
        if self._scan_cancel_event is not None:
            self._scan_cancel_event.set()
            self._log("正在取消扫描，请稍候...")
            self.scan_btn.configure(text="取消中...", state="disabled")
            return
        self._start_scan()

    def _start_scan(self):
        root = self.root_dir.get().strip()
        if not root:
            initial_dir = str(Path.cwd())
            new_dir = filedialog.askdirectory(
                title="选择固件所在的根目录",
                initialdir=initial_dir,
                parent=self.winfo_toplevel(),
            )
            if not new_dir:
                return
            root = new_dir
            self.root_dir.set(root)

        cancel_event = threading.Event()
        self._scan_cancel_event = cancel_event
        self.scan_btn.configure(text="取消扫描")
        self._log(f"开始扫描目录: {root}")

        def run_scan():
            result = build_scan_result(root, log_fn=self._log, cancel_event=cancel_event)
            self.after(0, lambda: self._handle_scan_result(result))

        threading.Thread(target=run_scan, daemon=True).start()

    def _load_cached_assets(self):
        result = build_cached_scan_result(log_fn=self._log)
        self._handle_scan_result(result)

    def _handle_scan_result(self, result: dict):
        self._scan_cancel_event = None
        self.scan_btn.configure(text="扫描目录", state="normal")

        if not result["ok"]:
            self._log(f"加载失败: {result['message']}")
            return

        payload = result["payload"]
        if "asset_count" in payload:
            self._log(f"已加载上次扫描的索引，共有 {payload['asset_count']} 个项目")
        else:
            assets = payload.get("assets", [])
            errors = payload.get("errors", [])
            self._log(f"扫描完成，共找到 {len(assets)} 个项目")
            if errors:
                self._log(f"扫描过程中有 {len(errors)} 个错误")

        root = self.root_dir.get().strip()
        root_dir = Path(root) if root else Path(".")
        db_path = None

        self.workbench_model.bind(db_path, root_dir)

        models = self.workbench_model.load_all_models()
        self._refresh_model_selector(models)

        if models:
            if not self.current_selection.model_name or self.current_selection.model_name not in models:
                self._on_model_changed(models[0])
            else:
                self._refresh_model_selector()
                self._refresh_sidebar_tree()
                self._refresh_main_grid()
