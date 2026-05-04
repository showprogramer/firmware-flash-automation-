from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from fwasset.core.services.at_command_service import apply_baudrate_command, send_at_command
from fwasset.core.services.music_flash_service import run_music_flash
from fwasset.core.services.serial_service import (
    connect_port,
    disconnect_port,
    read_serial_messages,
    scan_serial_ports,
    send_serial_command,
)
from fwasset.core.settings import MUSIC_DEFAULT_SOURCE_DIR, SERIAL_AT_PRESETS, SERIAL_DEFAULT_BAUDRATE
from fwasset.ui.base_panel import BaseFlashPanel
from fwasset.ui.design_tokens import (
    BG_CARD, BG_HOVER, BG_INPUT, BORDER_COLOR,
    COLOR_DANGER, COLOR_PRIMARY, COLOR_PRIMARY_HOVER, COLOR_SUCCESS,
    FONT_FAMILY, FONT_SIZE_LG, FONT_SIZE_MD, FONT_SIZE_SM, FONT_SIZE_XL,
    TEXT_PRIMARY, TEXT_SECONDARY
)
from fwasset.ui.shared_widgets import section_title


class MusicPanel(BaseFlashPanel):
    mode_key = "music"

    def __init__(self, master, switch_view_cb):
        super().__init__(master, switch_view_cb)
        
        # Observable Variables
        self.source_dir = tk.StringVar(value=MUSIC_DEFAULT_SOURCE_DIR or str(Path.cwd()))
        self.serial_port = tk.StringVar(value="")
        self.baudrate = tk.StringVar(value=str(SERIAL_DEFAULT_BAUDRATE))
        self.custom_cmd = tk.StringVar(value="AT+")
        self.format_first = tk.BooleanVar(value=True)
        self.eject_after = tk.BooleanVar(value=True)
        
        # State
        self._serial_conn = None
        self._connected = False
        self._presets = [str(x).strip() for x in SERIAL_AT_PRESETS if str(x).strip()] or ["AT+NM=Premium XZ8", "AT+BD=38400"]

        self._build_sidebar()
        self._build_main_view()
        
        # Initial Actions
        self._refresh_usb()
        self._scan_ports()

    def activate(self):
        super().activate()
        self._poll_serial_messages()

    # ==========================================
    # 🗂️ 左侧：全高侧边栏
    # ==========================================
    def _build_sidebar(self):
        sidebar = self._build_sidebar_frame()
        self._build_brand_header(sidebar)
        self._build_mode_switch(sidebar)

        # 串口摘要
        section_title(sidebar, "可用串口摘要")
        self.port_list_frame = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        self.port_list_frame.pack(fill="both", expand=True, padx=12)

        legend_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        legend_frame.pack(fill="x", padx=20, pady=20)
        self.conn_status_dot = ctk.CTkFrame(legend_frame, width=10, height=10, corner_radius=5, fg_color=COLOR_DANGER)
        self.conn_status_dot.pack(side="left", padx=6)
        self.conn_status_text = ctk.CTkLabel(legend_frame, text="串口未连接", font=(FONT_FAMILY, FONT_SIZE_SM), text_color=TEXT_SECONDARY)
        self.conn_status_text.pack(side="left")

    # ==========================================
    # 🖥️ 右侧：主视图区域
    # ==========================================
    def _build_main_view(self):
        main = self._build_main_container()
        self._build_header(main)
        self._build_dashboard_cards(main)
        self._build_data_panel(main)

    def _build_header(self, parent):
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 24))
        
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left")
        ctk.CTkLabel(title_box, text="音乐固件模式", font=(FONT_FAMILY, FONT_SIZE_XL, "bold"), text_color=TEXT_PRIMARY).pack(side="left", padx=(0, 12))
        
        self.header_port_badge = ctk.CTkLabel(
            title_box, text="未连接", fg_color=TEXT_SECONDARY, corner_radius=6,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"), text_color="white", padx=12, pady=4
        )
        self.header_port_badge.pack(side="left")

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")
        ctk.CTkButton(actions, text="📁 音乐目录", fg_color=BG_CARD, text_color=TEXT_PRIMARY, hover_color=BG_HOVER, border_width=1, border_color=BORDER_COLOR, command=self._browse_source).pack(side="left", padx=8)

    def _build_dashboard_cards(self, parent):
        cards_container = ctk.CTkFrame(parent, fg_color="transparent")
        cards_container.grid(row=1, column=0, sticky="ew", pady=(0, 24))
        cards_container.grid_columnconfigure(0, weight=4) 
        cards_container.grid_columnconfigure(1, weight=5) 
        
        # -- 卡片 1: 音乐 U 盘刷机 --
        usb_card = ctk.CTkFrame(cards_container, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER_COLOR)
        usb_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        section_title(usb_card, "💿 音乐 U 盘刷机")
        self._build_usb_selector_row(usb_card)
        
        options_row = ctk.CTkFrame(usb_card, fg_color="transparent")
        options_row.pack(fill="x", padx=20, pady=5)
        ctk.CTkCheckBox(options_row, text="格式化", variable=self.format_first, font=(FONT_FAMILY, FONT_SIZE_SM)).pack(side="left")
        ctk.CTkCheckBox(options_row, text="完成后弹出", variable=self.eject_after, font=(FONT_FAMILY, FONT_SIZE_SM)).pack(side="left", padx=10)

        ctk.CTkButton(usb_card, text="🚀 执行音乐刷机流程", height=48, corner_radius=8, font=(FONT_FAMILY, FONT_SIZE_LG, "bold"), fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER, command=self._run_music_flash).pack(fill="x", padx=20, pady=(15, 20))

        # -- 卡片 2: 串口与 AT 控制 --
        serial_card = ctk.CTkFrame(cards_container, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER_COLOR)
        serial_card.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        section_title(serial_card, "🔌 串口与 AT 控制")
        
        row1 = ctk.CTkFrame(serial_card, fg_color="transparent")
        row1.pack(fill="x", padx=20, pady=(0, 10))
        self.serial_menu = ctk.CTkComboBox(row1, variable=self.serial_port, values=[""], height=36, corner_radius=6, width=160)
        self.serial_menu.pack(side="left", padx=(0, 10))
        self.baud_menu = ctk.CTkOptionMenu(row1, variable=self.baudrate, values=["9600", "38400", "57600", "115200"], height=36, width=90)
        self.baud_menu.pack(side="left", padx=(0, 10))
        self.connect_btn = ctk.CTkButton(row1, text="连接", height=36, width=80, fg_color=COLOR_PRIMARY, command=self._toggle_connect)
        self.connect_btn.pack(side="left")

        preset_row = ctk.CTkFrame(serial_card, fg_color="transparent")
        preset_row.pack(fill="x", padx=20, pady=5)
        for p in self._presets[:2]: # 显示前两个预设为按钮
            ctk.CTkButton(preset_row, text=p, height=32, fg_color=BG_INPUT, text_color=TEXT_PRIMARY, hover_color=BG_HOVER, command=lambda x=p: self._send_preset(x)).pack(side="left", padx=(0, 8), fill="x", expand=True)

        cmd_row = ctk.CTkFrame(serial_card, fg_color="transparent")
        cmd_row.pack(fill="x", padx=20, pady=(10, 20))
        ctk.CTkEntry(cmd_row, textvariable=self.custom_cmd, placeholder_text="输入 AT 指令...", height=42, corner_radius=8).pack(side="left", fill="x", expand=True, padx=(0, 12))
        ctk.CTkButton(cmd_row, text="发送", height=42, width=80, font=(FONT_FAMILY, FONT_SIZE_MD, "bold"), fg_color=COLOR_SUCCESS, command=self._send_custom).pack(side="right")

    def _build_data_panel(self, parent):
        panel = ctk.CTkTabview(parent, corner_radius=12, fg_color=BG_CARD, segmented_button_selected_color=COLOR_PRIMARY, segmented_button_selected_hover_color=COLOR_PRIMARY_HOVER, segmented_button_unselected_color=BG_INPUT)
        panel.grid(row=2, column=0, sticky="nsew")
        
        tab_log = panel.add("💻 串口与运行日志")
        toolbar = ctk.CTkFrame(tab_log, fg_color="transparent")
        toolbar.pack(fill="x", padx=10, pady=(5, 5))
        ctk.CTkButton(toolbar, text="🗑 清空日志", fg_color=BG_INPUT, text_color=TEXT_PRIMARY, hover_color=BG_HOVER, width=100, height=32, command=self._clear_log).pack(side="right")
        
        self.log_text = ctk.CTkTextbox(tab_log, font=("Consolas", FONT_SIZE_MD), fg_color=BG_INPUT, corner_radius=8)
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

    # ==========================================
    # 🔌 业务逻辑
    # ==========================================
    def _clear_log(self):
        self.log_text.delete("1.0", "end")

    def _handle_task_failure(self, name: str, payload):
        self._log(f"{name}失败: {payload}")

    def _poll_serial_messages(self):
        if not self._polling_active:
            return
        if self._connected and self._serial_conn:
            result = read_serial_messages(self._serial_conn, encoding="utf-8", log_fn=lambda _m: None)
            if result.get("ok"):
                for line in (result.get("payload") or {}).get("lines", []):
                    self._log(f"收← {line}")
        self.after(200, self._poll_serial_messages)

    def _browse_source(self):
        s = filedialog.askdirectory(initialdir=self.source_dir.get() or str(Path.cwd()))
        if s: self.source_dir.set(s)

    def _scan_ports(self):
        for w in self.port_list_frame.winfo_children(): w.destroy()
        res = scan_serial_ports(log_fn=lambda _m: None)
        ports = (res.get("payload") or {}).get("ports", [])
        labels = [f"{p.get('device','')} {p.get('description','')}".strip() for p in ports if p.get("device")]
        if not labels: labels = [""]
        self.serial_menu.configure(values=labels)
        if self.serial_port.get() not in labels: self.serial_port.set(labels[0])
        
        for p in labels:
            if not p: continue
            f = ctk.CTkFrame(self.port_list_frame, fg_color="transparent", height=32)
            f.pack(fill="x", pady=2)
            ctk.CTkLabel(f, text="🔌", font=(FONT_FAMILY, 14)).pack(side="left", padx=10)
            ctk.CTkLabel(f, text=p[:28], font=(FONT_FAMILY, FONT_SIZE_SM), text_color=TEXT_PRIMARY).pack(side="left")

    def _selected_device(self) -> str:
        s = self.serial_port.get().strip()
        return s.split()[0] if s else ""

    def _set_connected(self, connected: bool):
        self._connected = connected
        self.connect_btn.configure(text="断开" if connected else "连接", fg_color=COLOR_DANGER if connected else COLOR_PRIMARY)
        self.conn_status_dot.configure(fg_color=COLOR_SUCCESS if connected else COLOR_DANGER)
        self.conn_status_text.configure(text="串口已连接" if connected else "串口未连接")
        self.header_port_badge.configure(text=self._selected_device() if connected else "未连接", fg_color=COLOR_SUCCESS if connected else TEXT_SECONDARY)

    def _toggle_connect(self):
        if self._connected:
            disconnect_port(self._serial_conn, log_fn=lambda _m: None)
            self._serial_conn = None; self._set_connected(False)
            return
        device = self._selected_device()
        if not device: return
        try: baud = int(self.baudrate.get())
        except: return
        res = connect_port(device, baudrate=baud, timeout_sec=1.0, log_fn=lambda _m: None)
        if res.get("ok"):
            self._serial_conn = (res.get("payload") or {}).get("connection")
            self._set_connected(True)
        else: self._log(f"连接失败: {res.get('message')}")

    def _run_music_flash(self):
        s = self.source_dir.get().strip(); d = self.usb_drive.get().strip()
        if not s or not d: return
        def _work(l): return run_music_flash(s, d, bool(self.format_first.get()), bool(self.eject_after.get()), log_fn=l)
        self._run_task("音乐刷机", _work, lambda res: self._log(f"结果: {res.get('message')}"))

    def _send_preset(self, preset: str):
        if not self._connected or not self._serial_conn: return
        cmd = preset.strip()
        if "=" in cmd: prefix, val = cmd.split("=", 1)
        else: prefix, val = cmd, ""
        if prefix.upper() == "AT+BD":
            res = apply_baudrate_command(self._serial_conn, int(val), log_fn=lambda _m: None)
            self._log(f"BD 结果: {res.get('message')}")
            self._toggle_connect(); return
        res = send_at_command(self._serial_conn, prefix, val, log_fn=lambda _m: None)
        self._log(f"{prefix} 结果: {res.get('payload', {}).get('response')}")

    def _send_custom(self):
        if not self._connected or not self._serial_conn: return
        cmd = self.custom_cmd.get().strip()
        if not cmd: return
        res = send_serial_command(self._serial_conn, cmd, log_fn=lambda _m: None)
        self._log(f"自定义结果: {res.get('payload', {}).get('response')}")
