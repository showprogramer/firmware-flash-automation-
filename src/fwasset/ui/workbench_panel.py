import threading
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

from fwasset.core.services.scan_service import build_cached_scan_result, build_scan_result
from fwasset.core.settings import DEFAULT_ROOT
from fwasset.ui.base_panel import BaseFlashPanel
from fwasset.ui.design_tokens import (
    BG_CARD,
    BG_SIDEBAR,
    COLOR_PRIMARY,
    FONT_FAMILY,
    FONT_SIZE_LG,
    FONT_SIZE_MD,
    RADIUS_LG,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XL,
    TEXT_PRIMARY,
    apply_ttk_theme
)
from fwasset.ui.panels.data_grid_panel import DataGridPanel
from fwasset.ui.panels.log_panel import LogPanel
from fwasset.ui.tool_center_panel import ToolCenterPanel
from fwasset.ui.view_models.scheme_workbench_model import (
    SchemeWorkbenchModel,
    WorkbenchSelection,
    ModuleCardData,
    ModuleVariant,
)
from fwasset.ui.view_models.scan_state_model import ScanStateModel

from fwasset.ui.operation_panels.registry import get_panel

class WorkbenchPanel(BaseFlashPanel):
    def __init__(self, master):
        super().__init__(master)
        
        apply_ttk_theme()  # Apply custom ttk styling
        
        self.root_dir = tk.StringVar(value=DEFAULT_ROOT)
        self.search_var = tk.StringVar(value="")
        
        self.workbench_model = SchemeWorkbenchModel()
        self.scan_state_model = ScanStateModel()
        self.current_selection = WorkbenchSelection()
        
        # Details operation panel container reference
        self.active_operation_panel = None
        self._ops_container = None
        
        self.grid_columnconfigure(0, weight=1, minsize=260)  # Left Sidebar
        self.grid_columnconfigure(1, weight=4, minsize=600)  # Right Main Area
        
        self._build_sidebar()
        self._build_main_view()
        
        self.search_var.trace_add("write", lambda *_: self._on_search_changed())
        
        self.after(100, self._load_cached_assets)

    # --- Sidebar ---
    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, fg_color=BG_SIDEBAR, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(2, weight=1)
        
        # Model Selector
        top_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky="ew", padx=SPACE_MD, pady=SPACE_MD)
        top_frame.grid_columnconfigure(0, weight=1)
        
        self.model_combo = ctk.CTkComboBox(
            top_frame,
            values=[],
            command=self._on_model_changed,
            font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
            height=40,
        )
        self.model_combo.grid(row=0, column=0, sticky="ew")
        
        # Search Bar
        search_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        search_frame.grid(row=1, column=0, sticky="ew", padx=SPACE_MD, pady=(0, SPACE_MD))
        search_frame.grid_columnconfigure(0, weight=1)
        
        search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=self.search_var,
            placeholder_text="🔍 智能搜索关键字...",
            height=36,
            font=(FONT_FAMILY, FONT_SIZE_MD)
        )
        search_entry.grid(row=0, column=0, sticky="ew")

        # Tree Frame
        self.tree_scroll = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        self.tree_scroll.grid(row=2, column=0, sticky="nsew", padx=SPACE_MD)
        self.tree_scroll.grid_columnconfigure(0, weight=1)
        
        # Bottom controls
        bottom_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        bottom_frame.grid(row=3, column=0, sticky="ew", padx=SPACE_MD, pady=SPACE_MD)
        bottom_frame.grid_columnconfigure(0, weight=1)
        bottom_frame.grid_columnconfigure(1, weight=1)
        
        self.scan_btn = ctk.CTkButton(
            bottom_frame,
            text="扫描目录",
            command=self._on_scan_button_click,
            fg_color=COLOR_PRIMARY,
            height=36
        )
        self.scan_btn.grid(row=0, column=0, sticky="ew", padx=(0, SPACE_SM))
        
        tools_btn = ctk.CTkButton(
            bottom_frame,
            text="工具中心",
            command=self._open_tool_center,
            fg_color="transparent",
            border_width=1,
            text_color=TEXT_PRIMARY,
            height=36
        )
        tools_btn.grid(row=0, column=1, sticky="ew", padx=(SPACE_SM, 0))

    # --- Main View ---
    def _build_main_view(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=SPACE_LG, pady=SPACE_LG)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)  # Grid gets most space
        
        # Header
        self.main_header = ctk.CTkFrame(main, fg_color=BG_CARD, corner_radius=RADIUS_LG, height=60)
        self.main_header.grid(row=0, column=0, sticky="ew", pady=(0, SPACE_LG))
        self.main_header.grid_propagate(False)
        self.main_header.grid_columnconfigure(0, weight=1)
        
        self.header_title = ctk.CTkLabel(
            self.main_header,
            text="请选择左侧分类进行过滤",
            font=(FONT_FAMILY, 20, "bold")
        )
        self.header_title.grid(row=0, column=0, sticky="w", padx=SPACE_LG, pady=15)
        
        self.header_badge = ctk.CTkLabel(
            self.main_header,
            text="",
            font=(FONT_FAMILY, FONT_SIZE_MD),
            text_color=COLOR_PRIMARY
        )
        self.header_badge.grid(row=0, column=1, sticky="e", padx=SPACE_LG, pady=15)

        # Data Grid Container
        self.grid_panel = DataGridPanel(main, self._on_grid_selection_changed, self._log)
        self.grid_panel.grid(row=1, column=0, sticky="nsew", pady=(0, SPACE_LG))
        
        # Operations Footer (Bottom section where actions appear when a row is selected)
        self.operations_frame = ctk.CTkFrame(main, fg_color=BG_CARD, corner_radius=RADIUS_LG, height=110)
        self.operations_frame.grid(row=2, column=0, sticky="ew", pady=(0, SPACE_LG))
        self.operations_frame.grid_propagate(False)
        self.operations_frame.grid_columnconfigure(0, weight=1)
        self.operations_frame.grid_rowconfigure(0, weight=1)
        
        # Initial empty state for operations
        self.ops_placeholder = ctk.CTkLabel(
            self.operations_frame, 
            text="展开模块并选择具体变体以查看操作",
            text_color="gray",
            font=(FONT_FAMILY, FONT_SIZE_MD)
        )
        self.ops_placeholder.grid(row=0, column=0)
        
        # Log Panel
        self.log_panel = LogPanel(main, height=120)
        self.log_panel.grid(row=3, column=0, sticky="ew")

    # --- Interaction Logic ---
    def _open_tool_center(self):
        ToolCenterPanel(self.winfo_toplevel(), log_fn=self._log)

    def _on_model_changed(self, choice: str):
        self.current_selection.model_name = choice
        self.current_selection.node_type = "all"
        self._refresh_sidebar_tree()
        self._refresh_main_grid()

    def _on_search_changed(self):
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
        all_btn = ctk.CTkButton(
            self.tree_scroll,
            text="📁 全部程序与模块",
            anchor="w",
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
            fg_color="transparent",
            text_color=COLOR_PRIMARY,
            hover_color=BG_CARD,
            command=self._select_all_modules
        )
        all_btn.grid(row=row_idx, column=0, sticky="ew", pady=(0, SPACE_MD))
        row_idx += 1
        
        # Common Modules Section
        if tree_data["common"]:
            common_title = ctk.CTkLabel(self.tree_scroll, text="── 通用模块 ──", font=(FONT_FAMILY, FONT_SIZE_MD, "bold"), text_color="gray")
            common_title.grid(row=row_idx, column=0, sticky="w", pady=(SPACE_SM, SPACE_SM))
            row_idx += 1
            
            for fw_label, count in tree_data["common"].items():
                if search_kw and search_kw not in fw_label.lower():
                    continue
                    
                btn = ctk.CTkButton(
                    self.tree_scroll,
                    text=f"├ {fw_label} ({count})",
                    anchor="w",
                    fg_color="transparent",
                    text_color=TEXT_PRIMARY,
                    hover_color=BG_CARD,
                    command=lambda lbl=fw_label: self._select_common_module(lbl)
                )
                btn.grid(row=row_idx, column=0, sticky="ew", pady=2)
                row_idx += 1

        # Custom Schemes Section
        if tree_data["custom"]:
            custom_title = ctk.CTkLabel(self.tree_scroll, text="── 定制方案 ──", font=(FONT_FAMILY, FONT_SIZE_MD, "bold"), text_color="gray")
            custom_title.grid(row=row_idx, column=0, sticky="w", pady=(SPACE_LG, SPACE_SM))
            row_idx += 1
            
            for scheme in tree_data["custom"]:
                if search_kw and search_kw not in scheme.lower():
                    continue
                    
                btn = ctk.CTkButton(
                    self.tree_scroll,
                    text=f"├ {scheme}",
                    anchor="w",
                    fg_color="transparent",
                    text_color=TEXT_PRIMARY,
                    hover_color=BG_CARD,
                    command=lambda s=scheme: self._select_custom_scheme(s)
                )
                btn.grid(row=row_idx, column=0, sticky="ew", pady=2)
                row_idx += 1

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
            self.ops_placeholder.configure(text="展开模块并选择具体变体以查看操作")
            self.ops_placeholder.grid(row=0, column=0)
            return

        self.ops_placeholder.grid_remove()

        # Load operation panel based on flash mode
        asset = variant.asset
        flash_mode = str(asset.get("flash_mode", "disabled"))
        PanelClass = get_panel(flash_mode)
        if PanelClass is None:
            self.ops_placeholder.configure(text=f"暂不支持的操作模式: {flash_mode}")
            self.ops_placeholder.grid(row=0, column=0)
            return

        # Single reusable container for the current selection's actions.
        # 不再在顶部堆"目录路径"标签（用户嫌杂）；双击行即可开目录。
        self._ops_container = ctk.CTkFrame(self.operations_frame, fg_color="transparent")
        self._ops_container.pack(fill="both", expand=True, padx=SPACE_LG, pady=SPACE_MD)

        self.active_operation_panel = PanelClass(
            self._ops_container, asset=asset, log_fn=self._log, panel_host=self
        )
        self.active_operation_panel.pack(fill="both", expand=True)
        self.active_operation_panel.build()

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
        import os, subprocess
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
            from tkinter import filedialog
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
        self.model_combo.configure(values=models)

        if models:
            if not self.current_selection.model_name or self.current_selection.model_name not in models:
                self.model_combo.set(models[0])
                self._on_model_changed(models[0])
            else:
                self._refresh_sidebar_tree()
                self._refresh_main_grid()
