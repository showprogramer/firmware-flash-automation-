from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from fwasset.core.services.at_command_service import apply_baudrate_command, send_at_command
from fwasset.core.services.serial_service import (
    connect_port,
    disconnect_port,
    read_serial_messages,
    scan_serial_ports,
    send_serial_command,
)
from fwasset.core.settings import SERIAL_AT_PRESETS, SERIAL_DEFAULT_BAUDRATE
from fwasset.ui.design_tokens import (
    BG_HOVER,
    BG_INPUT,
    COLOR_DANGER,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    FONT_FAMILY,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class SerialControl(ctk.CTkFrame):
    def __init__(self, master, log_fn=print):
        super().__init__(master, fg_color="transparent")
        self._log = log_fn
        self._polling_active = False
        self._serial_conn = None
        self._connected = False

        self.serial_port = tk.StringVar(value="")
        self.baudrate = tk.StringVar(value=str(SERIAL_DEFAULT_BAUDRATE))
        self.custom_cmd = tk.StringVar(value="AT+")
        self._presets = [str(x).strip() for x in SERIAL_AT_PRESETS if str(x).strip()] or ["AT+NM=Premium XZ8", "AT+BD=38400"]

        self._build()
        self._scan_ports()

    def activate(self):
        if self._polling_active:
            return
        self._polling_active = True
        self._poll_serial_messages()

    def deactivate(self):
        self._polling_active = False

    def _build(self):
        row1 = ctk.CTkFrame(self, fg_color="transparent")
        row1.pack(fill="x", padx=20, pady=(0, 10))
        self.serial_menu = ctk.CTkComboBox(row1, variable=self.serial_port, values=[""], height=36, corner_radius=6, width=180)
        self.serial_menu.pack(side="left", padx=(0, 10))
        self.baud_menu = ctk.CTkOptionMenu(
            row1,
            variable=self.baudrate,
            values=["9600", "38400", "57600", "115200"],
            height=36,
            width=90,
        )
        self.baud_menu.pack(side="left", padx=(0, 10))
        self.refresh_btn = ctk.CTkButton(
            row1,
            text="刷新",
            height=36,
            width=72,
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            command=self._scan_ports,
        )
        self.refresh_btn.pack(side="left", padx=(0, 10))
        self.connect_btn = ctk.CTkButton(
            row1,
            text="连接",
            height=36,
            width=80,
            fg_color=COLOR_PRIMARY,
            command=self._toggle_connect,
        )
        self.connect_btn.pack(side="left")

        status_row = ctk.CTkFrame(self, fg_color="transparent")
        status_row.pack(fill="x", padx=20, pady=(0, 12))
        self.conn_status_dot = ctk.CTkFrame(status_row, width=10, height=10, corner_radius=5, fg_color=COLOR_DANGER)
        self.conn_status_dot.pack(side="left", padx=(0, 8))
        self.conn_status_text = ctk.CTkLabel(
            status_row,
            text="串口未连接",
            font=(FONT_FAMILY, FONT_SIZE_SM),
            text_color=TEXT_SECONDARY,
        )
        self.conn_status_text.pack(side="left")

        preset_row = ctk.CTkFrame(self, fg_color="transparent")
        preset_row.pack(fill="x", padx=20, pady=5)
        for preset in self._presets[:2]:
            ctk.CTkButton(
                preset_row,
                text=preset,
                height=32,
                fg_color=BG_INPUT,
                text_color=TEXT_PRIMARY,
                hover_color=BG_HOVER,
                command=lambda value=preset: self._send_preset(value),
            ).pack(side="left", padx=(0, 8), fill="x", expand=True)

        cmd_row = ctk.CTkFrame(self, fg_color="transparent")
        cmd_row.pack(fill="x", padx=20, pady=(10, 20))
        ctk.CTkEntry(
            cmd_row,
            textvariable=self.custom_cmd,
            placeholder_text="输入 AT 指令...",
            height=42,
            corner_radius=8,
        ).pack(side="left", fill="x", expand=True, padx=(0, 12))
        ctk.CTkButton(
            cmd_row,
            text="发送",
            height=42,
            width=80,
            font=(FONT_FAMILY, FONT_SIZE_MD, "bold"),
            fg_color=COLOR_SUCCESS,
            command=self._send_custom,
        ).pack(side="right")

    def _scan_ports(self):
        result = scan_serial_ports(log_fn=lambda _m: None)
        ports = (result.get("payload") or {}).get("ports", [])
        labels = [f"{p.get('device', '')} {p.get('description', '')}".strip() for p in ports if p.get("device")]
        if not labels:
            labels = [""]
        self.serial_menu.configure(values=labels)
        if self.serial_port.get() not in labels:
            self.serial_port.set(labels[0])

    def _selected_device(self) -> str:
        value = self.serial_port.get().strip()
        return value.split()[0] if value else ""

    def _set_connected(self, connected: bool):
        self._connected = connected
        self.connect_btn.configure(text="断开" if connected else "连接", fg_color=COLOR_DANGER if connected else COLOR_PRIMARY)
        self.conn_status_dot.configure(fg_color=COLOR_SUCCESS if connected else COLOR_DANGER)
        self.conn_status_text.configure(text="串口已连接" if connected else "串口未连接")

    def _toggle_connect(self):
        if self._connected:
            disconnect_port(self._serial_conn, log_fn=lambda _m: None)
            self._serial_conn = None
            self._set_connected(False)
            return

        device = self._selected_device()
        if not device:
            return
        try:
            baud = int(self.baudrate.get())
        except Exception:
            return
        result = connect_port(device, baudrate=baud, timeout_sec=1.0, log_fn=lambda _m: None)
        if not result.get("ok"):
            self._log(f"连接失败: {result.get('message')}")
            return
        self._serial_conn = (result.get("payload") or {}).get("connection")
        self._set_connected(True)

    def _send_preset(self, preset: str):
        if not self._connected or not self._serial_conn:
            return
        command = preset.strip()
        if "=" in command:
            prefix, value = command.split("=", 1)
        else:
            prefix, value = command, ""
        if prefix.upper() == "AT+BD":
            result = apply_baudrate_command(self._serial_conn, int(value), log_fn=lambda _m: None)
            self._log(f"BD 结果: {result.get('message')}")
            self._toggle_connect()
            return
        result = send_at_command(self._serial_conn, prefix, value, log_fn=lambda _m: None)
        self._log(f"{prefix} 结果: {result.get('payload', {}).get('response')}")

    def _send_custom(self):
        if not self._connected or not self._serial_conn:
            return
        command = self.custom_cmd.get().strip()
        if not command:
            return
        result = send_serial_command(self._serial_conn, command, log_fn=lambda _m: None)
        self._log(f"自定义结果: {result.get('payload', {}).get('response')}")

    def _poll_serial_messages(self):
        if not self._polling_active:
            return
        if self._connected and self._serial_conn:
            result = read_serial_messages(self._serial_conn, encoding="utf-8", log_fn=lambda _m: None)
            if result.get("ok"):
                for line in (result.get("payload") or {}).get("lines", []):
                    self._log(f"收← {line}")
        self.after(200, self._poll_serial_messages)
