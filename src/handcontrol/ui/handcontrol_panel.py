from __future__ import annotations

import queue
import threading
import tkinter as tk
import os
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from handcontrol.core.excel_ops import load_excel_row, read_all_excel_rows
from handcontrol.core.services.excel_service import delete_record, update_record_fields, write_record
from handcontrol.core.services.flash_service import run_one_click
from handcontrol.core.services.scan_service import build_scan_result
from handcontrol.core.settings import DEFAULT_EXCEL, DEFAULT_ROOT, EXCEL_SHEET
from handcontrol.core.sort_config import SortKey, apply_sort
from handcontrol.core.usb_ops import clean_usb, copy_to_usb, eject_usb, format_usb, get_usb_drives
from handcontrol.ui.design_tokens import (
    BG_APP, BG_CARD, BG_HOVER, BG_INPUT, BG_SIDEBAR, BORDER_COLOR,
    COLOR_DANGER, COLOR_PRIMARY, COLOR_PRIMARY_HOVER, COLOR_SUCCESS, COLOR_WARNING,
    FONT_FAMILY, FONT_SIZE_LG, FONT_SIZE_MD, FONT_SIZE_SM, FONT_SIZE_XL,
    TEXT_PRIMARY, TEXT_SECONDARY
)
from handcontrol.ui.shared_widgets import card, section_title


class HandcontrolPanel(ctk.CTkFrame):
    def __init__(self, master, switch_view_cb):
        super().__init__(master, fg_color=BG_APP)
        self.switch_view_cb = switch_view_cb
        
        # Observable Variables
        self.root_dir = tk.StringVar(value=DEFAULT_ROOT)
        self.excel_path = tk.StringVar(value=DEFAULT_EXCEL)
        self.usb_drive = tk.StringVar(value="")
        self.search_var = tk.StringVar(value="")
        self.status_filter_var = tk.StringVar(value="全部状态")
        self.sort_key_var = tk.StringVar(value="默认(名称)")
        self.sort_asc_var = tk.BooleanVar(value=True)

        self.field_logo = tk.StringVar()
        self.field_language = tk.StringVar()
        self.field_salesman = tk.StringVar()
        self.field_attachment = tk.StringVar()
        self.review_status = tk.StringVar(value="测试通过")
        self.preview_search_var = tk.StringVar(value="")

        # Data State
        self.folders: list[dict] = []
        self._all_folders: list[dict] = []
        self._folder_status_map: dict[tuple[str, str], str] = {}
        self._preview_rows: list[dict] = []
        self._editing_preview_key: tuple[str, str] | None = None
        self._selected_idx = -1
        self._folder_card_widgets: list[dict] = []
        self._task_queue: queue.Queue = queue.Queue()
        self._busy = False
        self._polling_active = False
        self.manual_open = False

        # UI Layout
        self.grid_columnconfigure(0, weight=0, minsize=320)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_view()
        
        # Initial Actions
        self._refresh_usb()
        self._refresh_preview()
        
        # Traces
        self.search_var.trace_add("write", lambda *_: self._filter_folders())
        self.preview_search_var.trace_add("write", lambda *_: self._render_preview_rows())

    def activate(self):
        self.sync_mode_switch("handcontrol")
        if self._polling_active:
            return
        self._polling_active = True
        self._poll_task_queue()

    def deactivate(self):
        self._polling_active = False

    def sync_mode_switch(self, mode: str):
        if hasattr(self, "mode_switch"):
            self.mode_switch.set("音乐模式" if mode == "music" else "手控模式")

    # ==========================================
    # 🗂️ 左侧：全高侧边栏
    # ==========================================
    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=320, corner_radius=0, fg_color=BG_SIDEBAR)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        
        # Logo 与 标题
        brand_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand_frame.pack(fill="x", padx=24, pady=(32, 16))
        ctk.CTkLabel(brand_frame, text="⚡", font=(FONT_FAMILY, 24), text_color=COLOR_PRIMARY).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(brand_frame, text="设备管理终端", font=(FONT_FAMILY, FONT_SIZE_LG, "bold"), text_color=TEXT_PRIMARY).pack(side="left")

        # 模式切换
        mode_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        mode_frame.pack(fill="x", padx=20, pady=(0, 20))
        self.mode_switch = ctk.CTkSegmentedButton(
            mode_frame,
            values=["手控模式", "音乐模式"],
            command=self._on_mode_change,
            font=(FONT_FAMILY, FONT_SIZE_MD)
        )
        self.mode_switch.pack(fill="x")
        self.mode_switch.set("手控模式")

        # 搜索与排序
        search_sort_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        search_sort_frame.pack(fill="x", padx=20, pady=(0, 16))

        search_box = ctk.CTkEntry(
            search_sort_frame, height=36, corner_radius=8,
            placeholder_text="🔍 搜索 型号/版本/路径", textvariable=self.search_var,
            fg_color=BG_CARD, border_width=1, border_color=BORDER_COLOR,
            font=(FONT_FAMILY, FONT_SIZE_MD)
        )
        search_box.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.sort_menu = ctk.CTkOptionMenu(
            search_sort_frame, values=["默认(名称)", "按型号", "按版本", "按状态"],
            variable=self.sort_key_var,
            width=100, height=36, corner_radius=8,
            fg_color=BG_CARD, text_color=TEXT_PRIMARY, 
            button_color=BG_CARD, button_hover_color=BG_HOVER,
            font=(FONT_FAMILY, FONT_SIZE_MD),
            command=lambda _: self._filter_folders()
        )
        self.sort_menu.pack(side="right")

        # 列表区域
        self.list_scroll = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        self.list_scroll.pack(fill="both", expand=True, padx=12)

        # 底部状态图例
        legend_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        legend_frame.pack(fill="x", padx=20, pady=20)
        for color, lbl in [(COLOR_WARNING, "待确认"), (COLOR_SUCCESS, "通过"), (TEXT_SECONDARY, "未操作")]:
            row = ctk.CTkFrame(legend_frame, fg_color="transparent")
            row.pack(side="left", expand=True)
            ctk.CTkFrame(row, width=10, height=10, corner_radius=5, fg_color=color).pack(side="left", padx=6)
            ctk.CTkLabel(row, text=lbl, font=(FONT_FAMILY, FONT_SIZE_SM), text_color=TEXT_SECONDARY).pack(side="left")

    # ==========================================
    # 🖥️ 右侧：主视图区域
    # ==========================================
    def _build_main_view(self):
        main = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew", padx=32, pady=32)
        
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1) 
        
        self._build_header(main)
        self._build_dashboard_cards(main)
        self._build_data_panel(main)

    def _build_header(self, parent):
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 24))
        
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left")
        
        self.header_model_label = ctk.CTkLabel(title_box, text="-", font=(FONT_FAMILY, FONT_SIZE_XL, "bold"), text_color=TEXT_PRIMARY)
        self.header_model_label.pack(side="left", padx=(0, 12))
        
        self.header_version_badge = ctk.CTkLabel(
            title_box, text="-", fg_color=COLOR_PRIMARY, corner_radius=6,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"), text_color="white", padx=12, pady=4
        )
        self.header_version_badge.pack(side="left")

        self.header_status_badge = ctk.CTkLabel(
            title_box, text="未选择", fg_color=TEXT_SECONDARY, corner_radius=6,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"), text_color="white", padx=12, pady=4
        )
        self.header_status_badge.pack(side="left", padx=8)

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")
        
        ctk.CTkButton(actions, text="📁 扫描根目录", fg_color=BG_CARD, text_color=TEXT_PRIMARY, hover_color=BG_HOVER, border_width=1, border_color=BORDER_COLOR, command=self._choose_root_and_scan).pack(side="left", padx=8)
        ctk.CTkButton(actions, text="📊 明细表.xlsx", fg_color=BG_CARD, text_color=TEXT_PRIMARY, hover_color=BG_HOVER, border_width=1, border_color=BORDER_COLOR, command=self._browse_excel).pack(side="left")

    def _build_dashboard_cards(self, parent):
        cards_container = ctk.CTkFrame(parent, fg_color="transparent")
        cards_container.grid(row=1, column=0, sticky="ew", pady=(0, 24))
        cards_container.grid_columnconfigure(0, weight=4) 
        cards_container.grid_columnconfigure(1, weight=5) 
        
        # -- 卡片 1: 刷机操作 --
        ops_card = ctk.CTkFrame(cards_container, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER_COLOR)
        ops_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        
        section_title(ops_card, "⚡ 刷机与设备交互")
        
        usb_row = ctk.CTkFrame(ops_card, fg_color="transparent")
        usb_row.pack(fill="x", padx=20, pady=10)
        self.usb_menu = ctk.CTkComboBox(usb_row, variable=self.usb_drive, values=[""], width=120, height=36, corner_radius=6)
        self.usb_menu.pack(side="left", padx=(0, 10))
        ctk.CTkButton(usb_row, text="刷新", width=60, height=36, fg_color=BG_INPUT, text_color=TEXT_PRIMARY, hover_color=BG_HOVER, command=self._refresh_usb).pack(side="left", padx=4)
        
        ctk.CTkButton(ops_card, text="🚀 一键智能刷机", height=48, corner_radius=8, font=(FONT_FAMILY, FONT_SIZE_LG, "bold"), fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER, command=self._one_click).pack(fill="x", padx=20, pady=(10, 5))
        
        self.manual_btn = ctk.CTkButton(ops_card, text="▸ 展开手动分步操作", height=32, anchor="w", fg_color="transparent", text_color=TEXT_SECONDARY, hover_color=BG_HOVER, command=self._toggle_manual)
        self.manual_btn.pack(fill="x", padx=20, pady=5)
        
        self.manual_frame = ctk.CTkFrame(ops_card, fg_color="transparent")
        for step, cmd in [
            ("1. 清理垃圾文件", self._clean_usb),
            ("2. 格式化 FAT32", self._format_usb),
            ("3. 复制文件到 U 盘", self._copy_to_usb),
            ("4. 安全弹出", self._eject_usb)
        ]:
            ctk.CTkButton(self.manual_frame, text=step, height=36, anchor="w", corner_radius=6, fg_color=BG_INPUT, text_color=TEXT_PRIMARY, hover_color=BG_HOVER, command=cmd).pack(fill="x", pady=2)

        # -- 卡片 2: 台账表单 --
        form_card = ctk.CTkFrame(cards_container, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER_COLOR)
        form_card.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        
        section_title(form_card, "📝 审核台账填写")
        
        grid_frame = ctk.CTkFrame(form_card, fg_color="transparent")
        grid_frame.pack(fill="x", padx=20, pady=(0, 10))
        grid_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        self._create_input_field(grid_frame, 0, 0, "LOGO类型", ["中性", "通用", "定制"], self.field_logo)
        self._create_input_field(grid_frame, 0, 1, "业务负责人", [], self.field_salesman)
        self._create_input_field(grid_frame, 0, 2, "UI 附图", ["定制", "可通用", "无"], self.field_attachment)
        self._create_input_field(grid_frame, 1, 0, "支持语言", ["中文", "中、英", "中、英、越", "英文"], self.field_language, colspan=2)
        # 版本号回填或显示，暂时复用原来的
        ctk.CTkLabel(grid_frame, text="操作选项", font=(FONT_FAMILY, FONT_SIZE_SM), text_color=TEXT_SECONDARY).grid(row=2, column=2, sticky="w", padx=10, pady=(5, 0))
        ctk.CTkButton(grid_frame, text="下一个 ❯", height=36, corner_radius=6, fg_color=BG_INPUT, text_color=TEXT_PRIMARY, hover_color=BG_HOVER, command=self._next_folder).grid(row=3, column=2, sticky="ew", padx=10, pady=(4, 15))

        action_row = ctk.CTkFrame(form_card, fg_color="transparent")
        action_row.pack(fill="x", padx=20, pady=(10, 20))
        # 备注暂时用 entry
        self.remark_entry = ctk.CTkEntry(action_row, placeholder_text="添加备注 (可选)...", height=42, corner_radius=8, border_width=1, border_color=BORDER_COLOR)
        self.remark_entry.pack(side="left", fill="x", expand=True, padx=(0, 12))
        
        self.status_dropdown = ctk.CTkComboBox(action_row, values=["✅ 测试通过", "⏳ 待确认", "❌ 测试失败"], width=130, height=42, corner_radius=8, variable=self.review_status)
        self.status_dropdown.pack(side="left", padx=(0, 12))
        
        ctk.CTkButton(action_row, text="💾 保存台账", height=42, corner_radius=8, width=120, font=(FONT_FAMILY, FONT_SIZE_MD, "bold"), fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS[1], command=self._save_review_fields).pack(side="right")

    def _build_data_panel(self, parent):
        panel = ctk.CTkTabview(parent, corner_radius=12, fg_color=BG_CARD, segmented_button_selected_color=COLOR_PRIMARY, segmented_button_selected_hover_color=COLOR_PRIMARY_HOVER, segmented_button_unselected_color=BG_INPUT)
        panel.grid(row=2, column=0, sticky="nsew")
        
        tab_ledger = panel.add("📑 台账数据预览")
        tab_log = panel.add("💻 运行控制台")
        
        tab_ledger.grid_columnconfigure(0, weight=1)
        tab_ledger.grid_rowconfigure(1, weight=1)
        
        toolbar = ctk.CTkFrame(tab_ledger, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(5, 15))
        ctk.CTkEntry(toolbar, placeholder_text="搜索记录...", width=250, height=36, textvariable=self.preview_search_var).pack(side="left")
        ctk.CTkButton(toolbar, text="🗑 删除选中", fg_color=COLOR_DANGER, width=100, height=36, command=self._delete_selected_preview).pack(side="right")
        ctk.CTkButton(toolbar, text="🔄 刷新", fg_color=BG_INPUT, text_color=TEXT_PRIMARY, hover_color=BG_HOVER, width=80, height=36, command=self._refresh_preview).pack(side="right", padx=8)
        
        tree_frame = ctk.CTkFrame(tab_ledger, fg_color="transparent")
        tree_frame.grid(row=1, column=0, sticky="nsew")
        
        cols = ("序号", "型号", "logo", "业务员", "语言", "版本号", "完成日期", "附图", "备注")
        widths = (50, 90, 80, 80, 120, 90, 100, 80, 180)
        self.preview_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", style="Modern.Treeview")
        for col, w in zip(cols, widths):
            self.preview_tree.heading(col, text=col)
            self.preview_tree.column(col, width=w, anchor="w")
            
        sb_y = ctk.CTkScrollbar(tree_frame, orientation="vertical", command=self.preview_tree.yview)
        self.preview_tree.configure(yscrollcommand=sb_y.set)
        self.preview_tree.pack(side="left", fill="both", expand=True)
        sb_y.pack(side="right", fill="y")
        self.preview_tree.bind("<Double-1>", self._on_preview_double_click)
        
        self.log_text = ctk.CTkTextbox(tab_log, font=("Consolas", FONT_SIZE_MD), fg_color=BG_INPUT, corner_radius=8)
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

    def _create_input_field(self, parent, row, col, label, opts, variable, colspan=1):
        ctk.CTkLabel(parent, text=label, font=(FONT_FAMILY, FONT_SIZE_SM), text_color=TEXT_SECONDARY).grid(row=row*2, column=col, columnspan=colspan, sticky="w", padx=10, pady=(5, 0))
        if opts:
            widget = ctk.CTkComboBox(parent, values=opts, height=36, corner_radius=6, variable=variable)
        else:
            widget = ctk.CTkEntry(parent, height=36, corner_radius=6, border_width=1, border_color=BORDER_COLOR, textvariable=variable)
        widget.grid(row=row*2+1, column=col, columnspan=colspan, sticky="ew", padx=10, pady=(4, 15))

    # ==========================================
    # 🧠 核心逻辑：排序与过滤
    # ==========================================
    def _filter_folders(self):
        keyword = self.search_var.get().strip().lower()
        sort_by = self.sort_key_var.get()
        
        filtered = []
        for item in self._all_folders:
            if keyword:
                text = " ".join(str(item.get(k, "") or "") for k in ("model", "version", "label", "path", "rom_file", "pkg_file")).lower()
                if keyword not in text:
                    continue
            filtered.append(item)

        sort_key = SortKey.PATH
        if sort_by == "按型号":
            sort_key = SortKey.MODEL
        elif sort_by == "按版本":
            sort_key = SortKey.VERSION
        elif sort_by == "按状态":
            sort_key = SortKey.STATUS

        filtered = apply_sort(filtered, sort_key=sort_key, ascending=True, status_map=self._folder_status_map)

        self.folders = filtered
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
        widgets["card"].configure(
            fg_color=palette["card_fg"],
            border_color=palette["border_color"],
        )
        widgets["model_label"].configure(text_color=palette["model_text"])
        widgets["version_label"].configure(text_color=palette["meta_text"])
        widgets["name_label"].configure(text_color=palette["name_text"])

    def _create_sidebar_item(self, idx, item):
        status = self._folder_status(item)
        if status.startswith("待确认"):
            dot_color = COLOR_WARNING
        elif status.startswith("测试通过"):
            dot_color = COLOR_SUCCESS
        else:
            dot_color = TEXT_SECONDARY
            
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

        dot = ctk.CTkFrame(card_item, width=10, height=10, corner_radius=5, fg_color=dot_color)
        dot.pack(side="left", padx=16)
        
        text_area = ctk.CTkFrame(card_item, fg_color="transparent")
        text_area.pack(side="left", fill="both", expand=True, pady=12)
        
        row1 = ctk.CTkFrame(text_area, fg_color="transparent")
        row1.pack(fill="x")
        model_label = ctk.CTkLabel(row1, text=item.get("model", ""), font=(FONT_FAMILY, FONT_SIZE_MD, "bold"), text_color=palette["model_text"])
        model_label.pack(side="left")
        version_label = ctk.CTkLabel(row1, text=f" • {item.get('version', '')}", font=(FONT_FAMILY, FONT_SIZE_SM), text_color=palette["meta_text"])
        version_label.pack(side="left", padx=4)
        
        name = str(Path(item.get("path", "")).name)
        name_label = ctk.CTkLabel(
            text_area,
            text=name[:24]+"..." if len(name)>24 else name,
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=palette["name_text"],
            anchor="w",
        )
        name_label.pack(fill="x", pady=(2,0))

        # 绑定事件
        for w in [card_item, dot, text_area, row1, model_label, version_label, name_label]:
            w.bind("<Button-1>", lambda _e, i=idx: self._select_folder(i))
            w.bind("<Double-Button-1>", lambda _e, i=idx: self._open_folder_from_index(i))
        
        if not is_selected:
            card_item.bind("<Enter>", lambda _e, i=idx: self._apply_card_visual_state(i, True))
            card_item.bind("<Leave>", lambda _e, i=idx: self._apply_card_visual_state(i, i == self._selected_idx))

        self._folder_card_widgets.append(
            {
                "card": card_item,
                "model_label": model_label,
                "version_label": version_label,
                "name_label": name_label,
            }
        )

    # ==========================================
    # 🔌 业务逻辑：桥接原有功能
    # ==========================================
    def _on_mode_change(self, mode):
        if mode == "音乐模式":
            self.switch_view_cb("music")
        else:
            self.switch_view_cb("handcontrol")

    def _toggle_manual(self):
        if self.manual_open:
            self.manual_frame.pack_forget()
            self.manual_btn.configure(text="▸ 展开手动分步操作")
            self.manual_open = False
        else:
            self.manual_frame.pack(fill="x", padx=20, pady=(0, 10), after=self.manual_btn)
            self.manual_btn.configure(text="▾ 收起手动分步操作")
            self.manual_open = True

    def _log(self, message: str):
        if hasattr(self, "log_text"):
            self.log_text.insert("end", f"[{Path(__file__).name}] {message or ''}\n")
            self.log_text.see("end")

    def _run_task(self, name: str, fn, on_done=None):
        if self._busy:
            self._log("已有任务执行中，请稍后")
            return
        self._busy = True
        def worker():
            try:
                result = fn(self._log)
                self._task_queue.put(("done", name, result, on_done))
            except Exception as exc:
                self._task_queue.put(("fail", name, str(exc), on_done))
        threading.Thread(target=worker, daemon=True).start()

    def _poll_task_queue(self):
        if not self._polling_active:
            return
        try:
            while True:
                kind, name, payload, on_done = self._task_queue.get_nowait()
                self._busy = False
                if kind == "done":
                    if callable(on_done): on_done(payload)
                    self._log(f"{name}完成")
                else:
                    self._log(f"{name}失败: {payload}")
                    messagebox.showerror(f"{name}失败", str(payload))
        except queue.Empty: pass
        self.after(120, self._poll_task_queue)

    def _browse_excel(self):
        selected = filedialog.askopenfilename(
            initialdir=str(Path(self.excel_path.get() or str(Path.cwd())).parent),
            filetypes=[("Excel", "*.xlsx *.xls"), ("All", "*.*")],
        )
        if selected:
            self.excel_path.set(selected)
            self._refresh_preview()

    def _refresh_usb(self):
        drives = get_usb_drives()
        if not drives: drives = [""]
        self.usb_menu.configure(values=drives)
        if self.usb_drive.get() not in drives:
            self.usb_drive.set(drives[0])
        self._log(f"U盘刷新: {', '.join([d for d in drives if d]) or '未发现'}")

    def _preview_key(self, model: str, version: str) -> tuple[str, str]:
        return (str(model or "").strip().upper(), str(version or "").strip().upper())

    def _folder_status(self, item: dict) -> str:
        return str(self._folder_status_map.get(self._preview_key(item.get("model", ""), item.get("version", "")), "") or "")

    def _status_value_from_remark(self, remark: str) -> str:
        value = str(remark or "").strip()
        if "失败" in value:
            return "测试失败"
        if "待确认" in value:
            return "待确认"
        if "通过" in value:
            return "测试通过"
        return "测试通过"

    def _apply_review_form_values(self, *, logo: str = "", salesman: str = "", language: str = "", attachment: str = "", remark: str = ""):
        self.field_logo.set(logo or "")
        self.field_language.set(language or "")
        self.field_salesman.set(salesman or "")
        self.field_attachment.set(attachment or "")
        self.review_status.set(self._status_value_from_remark(remark))
        self.remark_entry.delete(0, "end")
        self.remark_entry.insert(0, remark or "")

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
            # 自动弹出选择框
            selected = filedialog.askdirectory(initialdir=str(Path.cwd()))
            if selected: self.root_dir.set(selected)
            else: return

        def _work(log_fn):
            return build_scan_result(self.root_dir.get(), self.excel_path.get(), EXCEL_SHEET, log_fn=log_fn)

        def _done(result):
            if not result.get("ok"):
                messagebox.showerror("扫描失败", str(result.get("message", "未知错误")))
                return
            payload = result.get("payload", {}) or {}
            self._all_folders = list(payload.get("folders", []))
            raw_status = payload.get("status_map", {}) or {}
            self._folder_status_map = { self._preview_key(k[0], k[1]): v for k, v in raw_status.items() if isinstance(k, tuple) }
            self._filter_folders()

        self._run_task("扫描目录", _work, _done)

    def _select_folder(self, idx: int):
        if idx < 0 or idx >= len(self.folders): return
        self._editing_preview_key = None
        previous_idx = self._selected_idx
        self._selected_idx = idx
        if previous_idx != idx:
            self._apply_card_visual_state(previous_idx, False)
            self._apply_card_visual_state(idx, True)
        info = self.folders[idx]
        
        # 更新 Header
        self.header_model_label.configure(text=info.get('model', '-'))
        self.header_version_badge.configure(text=info.get('version', '-'))
        status = self._folder_status(info)
        if status.startswith("待确认"):
            self.header_status_badge.configure(text="⏳ 待确认", fg_color=COLOR_WARNING)
        elif status.startswith("测试通过"):
            self.header_status_badge.configure(text="✅ 通过", fg_color=COLOR_SUCCESS)
        else:
            self.header_status_badge.configure(text="未操作", fg_color=TEXT_SECONDARY)

        # 加载数据
        existing = load_excel_row(self.excel_path.get(), EXCEL_SHEET, str(info.get("model", "")), str(info.get("version", "")))
        self._apply_review_form_values(
            logo=existing.get("logo", ""),
            salesman=existing.get("salesman", ""),
            language=existing.get("language", ""),
            attachment=existing.get("attachment", ""),
            remark=existing.get("remark", ""),
        )
        
        self._log(f"已选择: {info.get('model', '')} {info.get('version', '')}")

    def _open_folder_from_index(self, idx: int):
        if idx < 0 or idx >= len(self.folders): return
        info = self.folders[idx]
        path_obj = Path(str(info.get("path", "")))
        if not path_obj.exists():
            messagebox.showerror("错误", f"路径不存在: {path_obj}")
            return
        try:
            os.startfile(str(path_obj.resolve()))
        except OSError as exc:
            messagebox.showerror("错误", f"打开目录失败: {exc}")

    def _refresh_preview(self):
        def _work(_log_fn):
            rows = read_all_excel_rows(self.excel_path.get(), EXCEL_SHEET)
            return [{
                "serial": str(r[0] or ""), "model": str(r[1] or ""), "logo": str(r[2] or ""),
                "salesman": str(r[3] or ""), "language": str(r[4] or ""), "version": str(r[5] or ""),
                "date": str(r[6] or ""), "attachment": str(r[7] or ""), "remark": str(r[8] or "")
            } for r in rows]
        def _done(rows):
            self._preview_rows = rows
            self._render_preview_rows()
        self._run_task("刷新预览", _work, _done)

    def _render_preview_rows(self):
        if not hasattr(self, "preview_tree"): return
        for item_id in self.preview_tree.get_children(): self.preview_tree.delete(item_id)
        keyword = self.preview_search_var.get().strip().lower()
        for row in self._preview_rows:
            text = " ".join(str(row.get(k, "") or "") for k in ("model", "version", "logo", "salesman", "language", "remark")).lower()
            if keyword and keyword not in text: continue
            self.preview_tree.insert("", "end", values=(
                row.get("serial"), row.get("model"), row.get("logo"), row.get("salesman"),
                row.get("language"), row.get("version"), row.get("date"), row.get("attachment"), row.get("remark")
            ))

    def _on_preview_double_click(self, _event=None):
        sel = self.preview_tree.selection()
        if not sel: return
        v = self.preview_tree.item(sel[0], "values")
        self._editing_preview_key = self._preview_key(v[1], v[5])
        self._apply_review_form_values(
            logo=v[2],
            salesman=v[3],
            language=v[4],
            attachment=v[7],
            remark=v[8],
        )
        self.header_model_label.configure(text=v[1])
        self.header_version_badge.configure(text=v[5])
        self._log(f"已回填: {v[1]} {v[5]}")

    def _save_review_fields(self):
        status = self.review_status.get().replace("✅ ", "").replace("⏳ ", "").replace("❌ ", "").strip()
        remark = self.remark_entry.get().strip() or status
        
        if self._editing_preview_key:
            model, version = self._editing_preview_key
        else:
            info = self._current_info()
            if not info: return
            model, version = info.get("model", ""), info.get("version", "")

        def _work(log_fn):
            return update_record_fields(
                self.excel_path.get(), EXCEL_SHEET, model, version,
                self.field_logo.get(), self.field_salesman.get(), self.field_language.get(),
                self.field_attachment.get(), remark, log_fn=log_fn
            )
        def _done(result):
            if result.get("ok"):
                self._folder_status_map[self._preview_key(model, version)] = remark
                self._filter_folders(); self._refresh_preview()
            else: messagebox.showerror("失败", result.get("message"))
        self._run_task("保存台账", _work, _done)

    def _delete_selected_preview(self):
        sel = self.preview_tree.selection()
        if not sel: return
        v = self.preview_tree.item(sel[0], "values")
        if not messagebox.askyesno("确认", f"删除 {v[1]} {v[5]}?"): return
        def _work(log_fn): return delete_record(self.excel_path.get(), EXCEL_SHEET, v[1], v[5], log_fn=log_fn)
        def _done(res):
            if res.get("ok"): self._refresh_preview(); self._folder_status_map.pop(self._preview_key(v[1], v[5]), None); self._filter_folders()
        self._run_task("删除记录", _work, _done)

    def _current_info(self) -> dict | None:
        if self._selected_idx < 0: messagebox.showwarning("提示", "请先选择一个条目"); return None
        return self.folders[self._selected_idx]

    def _clean_usb(self):
        d = self.usb_drive.get().strip()
        if not d: return
        self._run_task("清理", lambda l: clean_usb(d, l))

    def _format_usb(self):
        d = self.usb_drive.get().strip()
        if not d or not messagebox.askyesno("格式化", f"确认格式化 {d}?"): return
        self._run_task("格式化", lambda l: format_usb(d, l))

    def _copy_to_usb(self):
        info = self._current_info(); d = self.usb_drive.get().strip()
        if not info or not d: return
        r = str(Path(info['path']) / info['rom_file']); p = str(Path(info['path']) / info['pkg_file'])
        self._run_task("复制", lambda l: copy_to_usb(r, p, d, l))

    def _eject_usb(self):
        d = self.usb_drive.get().strip()
        if not d: return
        self._run_task("弹出", lambda l: eject_usb(d, l))

    def _one_click(self):
        info = self._current_info(); d = self.usb_drive.get().strip()
        if not info or not d: return
        r = str(Path(info['path']) / info['rom_file']); p = str(Path(info['path']) / info['pkg_file'])
        def _work(l):
            return run_one_click(d, info['model'], info['version'], r, p, self.excel_path.get(), EXCEL_SHEET,
                                 self.field_logo.get(), self.field_language.get(), self.field_salesman.get(),
                                 self.field_attachment.get(), log_fn=l)
        def _done(res):
            if res.get("payload", {}).get("copy_ok"):
                self._folder_status_map[self._preview_key(info['model'], info['version'])] = "待确认"
                self._filter_folders(); self._refresh_preview()
        self._run_task("一键执行", _work, _done)

    def _next_folder(self):
        if self._selected_idx + 1 < len(self.folders): self._select_folder(self._selected_idx + 1)
        else: messagebox.showinfo("提示", "已到末尾")
