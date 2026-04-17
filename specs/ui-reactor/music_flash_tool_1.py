import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import threading
import queue
import os
import time
import datetime
from pathlib import Path
import sys

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SRC_PATH = _PROJECT_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from handcontrol.core.services.at_command_service import apply_baudrate_command, send_at_command
from handcontrol.core.services.music_flash_service import run_music_flash
from handcontrol.core.settings import MUSIC_DEFAULT_SOURCE_DIR, SERIAL_AT_PRESETS, SERIAL_DEFAULT_BAUDRATE
from handcontrol.core.services.serial_service import (
    connect_port,
    disconnect_port,
    read_serial_messages,
    scan_serial_ports,
    send_serial_command,
)

# ==========================================
# Design Tokens
# ==========================================
BG_APP     = ("#F9FAFB", "#09090B")
BG_CARD    = ("#FFFFFF", "#27272A")
BG_HOVER   = ("#E5E7EB", "#3F3F46")
BG_INPUT   = ("#F3F4F6", "#18181B")

COLOR_PRIMARY       = ("#4F46E5", "#6366F1")
COLOR_PRIMARY_HOVER = ("#4338CA", "#4F46E5")
COLOR_SUCCESS       = ("#10B981", "#059669")
COLOR_WARNING       = ("#F59E0B", "#D97706")
COLOR_DANGER        = ("#EF4444", "#DC2626")

TEXT_PRIMARY   = ("#111827", "#F9FAFB")
TEXT_SECONDARY = ("#6B7280", "#A1A1AA")
BORDER_COLOR   = ("#E5E7EB", "#3F3F46")

FONT = "Segoe UI"
FLG  = 16
FMD  = 13
FSM  = 12

DEFAULT_SRC = MUSIC_DEFAULT_SOURCE_DIR or r"D:\按摩椅相关文件汇总\test_411\音乐\A122QMUSIC001-YJ"


def _build_at_presets() -> list[tuple[str, str, str, bool, bool]]:
    defaults = [
        ("设备名称", "AT+NM", "Premium XZ8", True, False),
        ("配对密码", "AT+MP", "8888", True, False),
        ("功能参数", "AT+FUN", "PIN=EN", False, False),
        ("波特率", "AT+BD", "38400", True, True),
    ]
    if not SERIAL_AT_PRESETS:
        return defaults

    label_map = {
        "AT+NM": "设备名称",
        "AT+MP": "配对密码",
        "AT+FUN": "功能参数",
        "AT+BD": "波特率",
    }
    parsed: list[tuple[str, str, str, bool, bool]] = []
    for item in SERIAL_AT_PRESETS:
        text = str(item or "").strip()
        if not text:
            continue
        if "=" in text:
            prefix, value = text.split("=", 1)
        else:
            prefix, value = text, ""
        prefix = prefix.strip().upper()
        value = value.strip()
        if not prefix.startswith("AT+"):
            continue
        is_bd = prefix == "AT+BD"
        editable = prefix != "AT+FUN"
        parsed.append((label_map.get(prefix, prefix), prefix, value, editable, is_bd))
    return parsed or defaults

AT_PRESETS = _build_at_presets()


class MusicFlashTool(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("音乐版刷机工具")
        self.geometry("960x700")
        self.minsize(860, 620)
        self.configure(fg_color=BG_APP)

        self._demo_mode = False
        probe = scan_serial_ports(log_fn=lambda _m: None)
        if not probe.get("ok") and probe.get("code") == "serial_missing":
            self._demo_mode = True

        self._port_obj    = None
        self._running     = False
        self._is_flashing = False
        self._polling     = False  # 轮询检测模式标志
        self._log_q       = queue.Queue()
        self._drive_q     = queue.Queue()
        self._cur_drives  = set()
        self._at_vars     = {}
        self._at_res      = {}
        self._at_btns     = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build()
        self._scan_drives()
        self._scan_ports()
        self._poll_log()
        threading.Thread(target=self._watch_drives, daemon=True).start()
        # 取消自动连接，改为用户手动点击连接按钮
        # self.after(400, self._auto_connect)
        self.after(100, lambda: self.state("zoomed"))  # 延迟最大化，确保日志区可见

    # ──────────────────────────────────────
    # 布局
    # ──────────────────────────────────────
    def _build(self):
        root = ctk.CTkFrame(self, fg_color="transparent")
        root.grid(sticky="nsew", padx=24, pady=24)
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(2, weight=1)
        self._build_header(root)
        self._build_flash_card(root)
        self._build_serial_card(root)

    def _build_header(self, parent):
        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        ctk.CTkLabel(bar, text="音乐版刷机",
                     font=(FONT, 22, "bold"), text_color=TEXT_PRIMARY).pack(side="left")
        ctk.CTkLabel(bar, text="A122QMUSIC001-YJ",
                     fg_color=COLOR_SUCCESS, corner_radius=6,
                     font=(FONT, FSM, "bold"), text_color="white",
                     padx=10, pady=3).pack(side="left", padx=12)
        if self._demo_mode:
            ctk.CTkLabel(bar, text="pyserial 未安装 — 演示模式",
                         font=(FONT, FSM), text_color=COLOR_WARNING).pack(side="right")

    def _build_flash_card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=12,
                            border_width=1, border_color=BORDER_COLOR)
        card.grid(row=1, column=0, sticky="ew", pady=(0, 14))

        self._card_title(card, "⚡ U盘准备")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=(0, 12))
        inner.grid_columnconfigure(1, weight=1)

        # 音乐文件夹路径
        ctk.CTkLabel(inner, text="音乐文件夹", width=80,
                     font=(FONT, FSM), text_color=TEXT_SECONDARY, anchor="w"
                     ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self._src_var = ctk.StringVar(value=DEFAULT_SRC)
        ctk.CTkEntry(inner, textvariable=self._src_var, height=36, corner_radius=8,
                     fg_color=BG_INPUT, border_width=1, border_color=BORDER_COLOR,
                     font=(FONT, FSM)
                     ).grid(row=0, column=1, sticky="ew", padx=8, pady=(0, 8))
        ctk.CTkButton(inner, text="浏览", width=64, height=36, corner_radius=8,
                      fg_color=BG_INPUT, text_color=TEXT_PRIMARY, hover_color=BG_HOVER,
                      font=(FONT, FSM), command=self._browse_src
                      ).grid(row=0, column=2, pady=(0, 8))

        # U盘盘符
        ctk.CTkLabel(inner, text="U 盘", width=80,
                     font=(FONT, FSM), text_color=TEXT_SECONDARY, anchor="w"
                     ).grid(row=1, column=0, sticky="w")
        self._drive_var = ctk.StringVar(value="—")
        self._drive_menu = ctk.CTkOptionMenu(
            inner, variable=self._drive_var, values=["—"],
            width=110, height=36, corner_radius=8,
            fg_color=BG_INPUT, text_color=TEXT_PRIMARY,
            button_color=BG_INPUT, button_hover_color=BG_HOVER,
            font=(FONT, FSM))
        self._drive_menu.grid(row=1, column=1, sticky="w", padx=8)
        ctk.CTkButton(inner, text="扫描", width=64, height=36, corner_radius=8,
                      fg_color=BG_INPUT, text_color=TEXT_PRIMARY, hover_color=BG_HOVER,
                      font=(FONT, FSM), command=self._scan_drives
                      ).grid(row=1, column=2)

        # 进度
        self._prog_var = ctk.DoubleVar(value=0)
        self._prog_bar = ctk.CTkProgressBar(card, variable=self._prog_var,
                                             height=6, corner_radius=3,
                                             fg_color=BG_INPUT,
                                             progress_color=COLOR_SUCCESS)
        self._prog_bar.pack(fill="x", padx=20, pady=(4, 6))
        self._prog_label = ctk.CTkLabel(card, text="就绪",
                                        font=(FONT, FSM), text_color=TEXT_SECONDARY)
        self._prog_label.pack(anchor="w", padx=20, pady=(0, 6))

        self._flash_btn = ctk.CTkButton(
            card, text="🚀  一键格式化并复制弹出",
            height=46, corner_radius=8,
            font=(FONT, FLG, "bold"),
            fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS,
            command=self._start_flash)
        self._flash_btn.pack(fill="x", padx=20, pady=(0, 20))

    def _build_serial_card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=12,
                            border_width=1, border_color=BORDER_COLOR)
        card.grid(row=2, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(2, weight=1)

        self._card_title(card, "🔌 串口 AT 配置")

        # 连接行
        conn = ctk.CTkFrame(card, fg_color="transparent")
        conn.pack(fill="x", padx=20, pady=(0, 12))

        self._port_var = ctk.StringVar(value="—")
        self._port_menu = ctk.CTkOptionMenu(
            conn, variable=self._port_var, values=["—"],
            width=240, height=34, corner_radius=8,          # 宽一点，显示完整名称
            fg_color=BG_INPUT, text_color=TEXT_PRIMARY,
            button_color=BG_INPUT, button_hover_color=BG_HOVER,
            font=(FONT, FSM))
        self._port_menu.pack(side="left", padx=(0, 8))

        self._baud_var = ctk.StringVar(value=str(SERIAL_DEFAULT_BAUDRATE))
        ctk.CTkOptionMenu(
            conn, variable=self._baud_var,
            values=["9600", "38400", "57600", "115200"],
            width=100, height=34, corner_radius=8,
            fg_color=BG_INPUT, text_color=TEXT_PRIMARY,
            button_color=BG_INPUT, button_hover_color=BG_HOVER,
            font=(FONT, FSM)).pack(side="left", padx=(0, 8))

        ctk.CTkButton(conn, text="扫描", width=64, height=34, corner_radius=8,
                      fg_color=BG_INPUT, text_color=TEXT_PRIMARY, hover_color=BG_HOVER,
                      font=(FONT, FSM), command=self._scan_ports
                      ).pack(side="left", padx=(0, 8))

        self._conn_btn = ctk.CTkButton(
            conn, text="连接", width=72, height=34, corner_radius=8,
            fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS,
            font=(FONT, FSM, "bold"), command=self._toggle_conn)
        self._conn_btn.pack(side="left", padx=(0, 12))

        self._conn_label = ctk.CTkLabel(
            conn, text="● 未连接", font=(FONT, FSM), text_color=COLOR_DANGER)
        self._conn_label.pack(side="left")

        # AT 指令行
        at_frame = ctk.CTkFrame(card, fg_color="transparent")
        at_frame.pack(fill="x", padx=20, pady=(0, 10))
        for i, (lbl, prefix, default, editable, is_bd) in enumerate(AT_PRESETS):
            self._build_at_row(at_frame, i, lbl, prefix, default, editable, is_bd)

        # 批量发送
        send_row = ctk.CTkFrame(card, fg_color="transparent")
        send_row.pack(fill="x", padx=20, pady=(0, 12))
        self._send_all_btn = ctk.CTkButton(
            send_row, text="发送全部 AT 指令",
            height=38, corner_radius=8,
            fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER,
            font=(FONT, FMD, "bold"), command=self._send_all)
        self._send_all_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(send_row, text="清空", width=68, height=38, corner_radius=8,
                      fg_color=BG_INPUT, text_color=TEXT_SECONDARY, hover_color=BG_HOVER,
                      font=(FONT, FSM), command=self._clear_console
                      ).pack(side="right")

        # 自定义指令行
        custom_row = ctk.CTkFrame(card, fg_color="transparent")
        custom_row.pack(fill="x", padx=20, pady=(0, 12))

        ctk.CTkLabel(custom_row, text="自定义指令:", font=(FONT, FSM), text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 8))
        self._custom_cmd_var = ctk.StringVar(value="AT+")
        ctk.CTkEntry(custom_row, textvariable=self._custom_cmd_var, width=280, height=34, corner_radius=8,
                     fg_color=BG_INPUT, border_width=1, border_color=BORDER_COLOR,
                     font=("Consolas", FMD)).pack(side="left", padx=(0, 8))

        self._custom_send_btn = ctk.CTkButton(
            custom_row, text="发送 (+CRLF)", width=100, height=34, corner_radius=8,
            fg_color=BG_CARD, text_color=TEXT_PRIMARY, hover_color=BG_HOVER,
            border_width=1, border_color=BORDER_COLOR,
            font=(FONT, FSM), command=self._send_custom)
        self._custom_send_btn.pack(side="left")

        # 控制台
        self._console = ctk.CTkTextbox(
            card, corner_radius=8,
            font=("Consolas", FSM),
            fg_color=("#1A1A2E", "#0D0D14"),
            text_color=("#D4D4D4", "#D4D4D4"))
        self._console.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self._log("[系统] 就绪。请先连接串口再发送 AT 指令。")
        # 初始状态：按钮禁用（未连接）
        self._update_send_buttons_state(False)

    def _build_at_row(self, parent, idx, lbl, prefix, default, editable, is_bd):
        row = ctk.CTkFrame(parent, fg_color=BG_INPUT, corner_radius=8, height=44)
        row.pack(fill="x", pady=4)
        row.pack_propagate(False)

        ctk.CTkLabel(row, text=lbl, width=72,
                     font=(FONT, FSM), text_color=TEXT_SECONDARY, anchor="w"
                     ).pack(side="left", padx=(12, 4))
        ctk.CTkLabel(row, text=f"{prefix}=",
                     font=("Consolas", FMD), text_color=COLOR_PRIMARY
                     ).pack(side="left", padx=(0, 4))

        var = ctk.StringVar(value=default)
        self._at_vars[idx] = var

        if editable:
            ctk.CTkEntry(row, textvariable=var, width=180, height=28, corner_radius=6,
                         fg_color=BG_CARD, border_width=1, border_color=BORDER_COLOR,
                         font=("Consolas", FMD)).pack(side="left", padx=(0, 8))
        else:
            ctk.CTkLabel(row, text=default,
                         font=("Consolas", FMD), text_color=TEXT_PRIMARY
                         ).pack(side="left", padx=(0, 8))

        # 波特率行加提示标签
        if is_bd:
            ctk.CTkLabel(row, text="发送后模块立即切换，App 自动断开",
                         font=(FONT, 10), text_color=TEXT_SECONDARY
                         ).pack(side="left", padx=(0, 8))

        btn = ctk.CTkButton(row, text="发送", width=50, height=28, corner_radius=6,
                      fg_color=BG_CARD, text_color=TEXT_PRIMARY, hover_color=BG_HOVER,
                      border_width=1, border_color=BORDER_COLOR,
                      font=(FONT, FSM),
                      command=lambda i=idx, p=prefix, b=is_bd: self._send_one(i, p, b))
        btn.pack(side="left", padx=(0, 6))
        self._at_btns[idx] = btn

        res = ctk.CTkLabel(row, text="—", width=56,
                           font=(FONT, FSM), text_color=TEXT_SECONDARY)
        res.pack(side="left")
        self._at_res[idx] = res

    # ──────────────────────────────────────
    # U盘
    # ──────────────────────────────────────
    def _browse_src(self):
        d = filedialog.askdirectory(initialdir=self._src_var.get())
        if d:
            self._src_var.set(d)

    def _scan_drives(self):
        drives = [f"{l}:\\" for l in "DEFGHIJKLMNOPQRSTUVWXYZ"
                  if os.path.exists(f"{l}:\\")]
        if drives:
            self._drive_menu.configure(values=drives)
            self._drive_var.set("E:\\" if "E:\\" in drives else drives[0])
        else:
            self._drive_menu.configure(values=["未找到"])
            self._drive_var.set("未找到")

    def _watch_drives(self):
        while True:
            time.sleep(2)
            cur = {f"{l}:\\" for l in "DEFGHIJKLMNOPQRSTUVWXYZ"
                   if os.path.exists(f"{l}:\\")}
            if cur != self._cur_drives:
                self._cur_drives = cur
                self._drive_q.put(True)

    def _start_flash(self):
        src   = self._src_var.get().strip()
        drive = self._drive_var.get().strip()
        if not os.path.isdir(src):
            self._set_prog("❌ 音乐文件夹不存在", 0, COLOR_DANGER); return
        if len(drive) < 2 or not os.path.exists(drive):
            self._set_prog("❌ U盘路径无效", 0, COLOR_DANGER); return
        self._is_flashing = True
        self._flash_btn.configure(state="disabled", text="处理中...")
        self._set_prog("准备中...", 0, COLOR_WARNING)
        threading.Thread(target=self._flash_worker, args=(src, drive),
                         daemon=True).start()

    def _flash_worker(self, src: str, drive: str):
        try:
            self._ui(lambda: self._set_prog("格式化 U 盘...", 0.15, COLOR_WARNING))
            folder = os.path.basename(src.rstrip("\\/"))
            self._ui(lambda: self._set_prog(f"复制 {folder} 到 {drive}...", 0.55, COLOR_WARNING))
            result = run_music_flash(
                source_dir=src,
                drive=drive,
                format_first=True,
                eject_after=True,
                log_fn=lambda s: self._log_q.put(f"[流程] {s}"),
            )
            if not result.get("ok"):
                raise RuntimeError(str(result.get("message", "刷机流程失败")))
            ejected = bool((result.get("payload") or {}).get("ejected", False))
            msg = f"✅ {folder} 已写入 {drive}" + ("，U盘已弹出" if ejected else "，请手动拔出")
            self._ui(lambda: self._set_prog(msg, 1.0, COLOR_SUCCESS))

        except Exception as e:
            err = str(e)
            self._ui(lambda: self._set_prog(f"❌ {err}", 0, COLOR_DANGER))
        finally:
            self._is_flashing = False
            self._ui(lambda: self._flash_btn.configure(
                state="normal", text="🚀  一键格式化并复制"))

    def _set_prog(self, text, val, color):
        self._prog_var.set(val)
        self._prog_bar.configure(progress_color=color)
        self._prog_label.configure(text=text, text_color=color)

    def _ui(self, fn):
        self.after(0, fn)

    # ──────────────────────────────────────
    # 串口
    # ──────────────────────────────────────
    def _scan_ports(self):
        result = scan_serial_ports(log_fn=lambda msg: self._log_q.put(f"[扫描] {msg}"))
        if not result.get("ok"):
            self._log(f"[扫描] {result.get('message', '扫描失败')}")
            if self._demo_mode:
                vals = ["COM3  USB-SERIAL CH340 (演示)", "COM5  USB串行设备 (演示)"]
                self._port_menu.configure(values=vals)
                self._port_var.set(vals[0])
            return

        ports = (result.get("payload") or {}).get("ports", [])
        labels = [f"{p.get('device', '')}  {p.get('description', '')}".strip() for p in ports if p.get("device")]
        if not labels:
            self._log("[扫描] 未找到可用串口")
            return
        self._port_menu.configure(values=labels)
        sel = labels[0]
        for lbl in labels:
            if "CH340" in lbl.upper() or "CH341" in lbl.upper():
                sel = lbl
                break
        self._port_var.set(sel)
        self._log(f"[扫描] {len(labels)} 个端口: " + " | ".join(labels))

    def _auto_connect(self):
        if self._demo_mode: return
        lbl = self._port_var.get()
        if "CH340" in lbl.upper() or "CH341" in lbl.upper():
            self._log(f"[自动] 检测到 CH340，自动连接")
            self._connect()

    def _toggle_conn(self):
        if self._port_obj and self._port_obj.is_open:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        if self._demo_mode:
            self._set_conn_ui(True)
            self._log("[连接] 演示模式")
            return
        port = self._port_var.get().split()[0]
        baud = int(self._baud_var.get())

        for attempt in range(3):
            result = connect_port(port, baudrate=baud, timeout_sec=1.0, log_fn=lambda msg: self._log_q.put(f"[连接] {msg}"))
            if result.get("ok"):
                self._port_obj = (result.get("payload") or {}).get("connection")
                self._running  = True
                self._set_conn_ui(True)
                self._log(f"[连接] {port}  {self._port_var.get().split(None,1)[-1]}  @ {baud} bps")
                threading.Thread(target=self._read_loop, daemon=True).start()
                return
            if attempt < 2:
                self._log(f"[连接] 端口忙，第 {attempt+1} 次重试... ({result.get('message', '')})")
                time.sleep(1)
            else:
                self._log(f"[错误] 连接失败: {result.get('message', '未知错误')}")
                self._log("[提示] 请确认端口未被其他程序占用 (SSCOM、串口助手等)")

    def _disconnect(self):
        self._running = False
        self._polling = False
        disconnect_port(self._port_obj, log_fn=lambda msg: self._log_q.put(f"[连接] {msg}"))
        self._port_obj = None
        self._set_conn_ui(False)
        self._log("[连接] 已断开")

    def _set_conn_ui(self, on: bool):
        if on:
            self._conn_btn.configure(text="断开",
                                     fg_color=COLOR_DANGER, hover_color=COLOR_DANGER)
            self._conn_label.configure(text="● 已连接", text_color=COLOR_SUCCESS)
            # 重新连接时重置所有 AT 指令结果标签，避免上次状态残留
            for res_label in self._at_res.values():
                res_label.configure(text="—", text_color=TEXT_SECONDARY)
            # 重置问候确认标志，允许新一轮检测
            self._greeting_confirmed = False
        else:
            self._conn_btn.configure(text="连接",
                                     fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS)
            self._conn_label.configure(text="● 未连接", text_color=COLOR_DANGER)
        self._update_send_buttons_state(on)

    def _update_send_buttons_state(self, enabled: bool):
        """启用/禁用所有 AT 发送相关按钮。"""
        state = "normal" if enabled else "disabled"
        for btn in self._at_btns.values():
            btn.configure(state=state)
        if hasattr(self, '_send_all_btn'):
            self._send_all_btn.configure(state=state)
        if hasattr(self, '_custom_send_btn'):
            self._custom_send_btn.configure(state=state)

    def _send_one(self, idx: int, prefix: str, is_bd: bool = False):
        if self._demo_mode:
            val = self._at_vars[idx].get().strip()
            self._log(f"[AT→] {prefix}={val}  (演示)")
            if is_bd:
                self._at_res[idx].configure(text="✓ 已发送", text_color=COLOR_SUCCESS)
                self._log("[波特率] 演示：模块已切换，自动验证跳过")
            else:
                self.after(500, lambda: self._mark(idx, True))
            return

        if not (self._port_obj and self._port_obj.is_open):
            self._log("[错误] 串口未连接，请先连接主板再发送指令")
            self._mark(idx, False)
            return

        val = self._at_vars[idx].get().strip()
        self._at_res[idx].configure(text="…", text_color=COLOR_WARNING)
        self._log(f"[AT→] {prefix}={val}")

        if is_bd:
            def _send_bd():
                self._running = False
                result = apply_baudrate_command(self._port_obj, new_baud=int(val), log_fn=lambda msg: self._log_q.put(f"[波特率] {msg}"))
                self._port_obj = None
                self.after(0, lambda: self._set_conn_ui(False))
                if result.get("ok"):
                    self._log_q.put(f"[波特率] ✅ {result.get('message', '')}")
                    self.after(0, lambda: self._at_res[idx].configure(text="✓ 已验证", text_color=COLOR_SUCCESS))
                    return
                code = str(result.get("code", "baud_unknown"))
                self._log_q.put(f"[波特率] ⚠ {result.get('message', '')}")
                if code == "baud_unchanged":
                    self.after(0, lambda: self._at_res[idx].configure(text="✗ 未改变", text_color=COLOR_DANGER))
                else:
                    self.after(0, lambda: self._at_res[idx].configure(text="? 未知", text_color=COLOR_WARNING))

            threading.Thread(target=_send_bd, daemon=True).start()

        else:
            def _send_normal():
                self._running = False
                result = send_at_command(
                    self._port_obj,
                    prefix=prefix,
                    value=val,
                    success_tokens=("OK", "BT"),
                    log_fn=lambda msg: self._log_q.put(f"[AT] {msg}"),
                )
                response = str((result.get("payload") or {}).get("response", "") or "")
                self._log_q.put(f"[AT←] {response or '(无响应)'}")
                self.after(0, lambda: self._mark(idx, bool(result.get("ok"))))
                if self._port_obj and self._port_obj.is_open:
                    self._running = True
                    threading.Thread(target=self._read_loop, daemon=True).start()

            threading.Thread(target=_send_normal, daemon=True).start()

    def _send_custom(self):
        if not (self._port_obj and self._port_obj.is_open) and not self._demo_mode:
            self._log("[错误] 串口未连接，请先连接主板再发送指令")
            return

        val = self._custom_cmd_var.get().strip()
        if not val: return

        cmd = f"{val}\r\n"
        self._log(f"[AT→] {val}")

        if self._demo_mode:
            self._log("[演示] 指令已发送")
            return

        def _worker():
            result = send_serial_command(self._port_obj, val, wait_sec=0.8, log_fn=lambda msg: self._log_q.put(f"[AT] {msg}"))
            if result.get("ok"):
                resp = str((result.get("payload") or {}).get("response", "") or "")
                self._log_q.put(f"[AT←] {resp or '(无响应)'}")
            else:
                self._log_q.put(f"[错误] 发送失败: {result.get('message', '未知错误')}")

        threading.Thread(target=_worker, daemon=True).start()

    def _send_all(self):
        if not (self._port_obj and self._port_obj.is_open) and not self._demo_mode:
            self._log("[错误] 串口未连接，请先连接主板再发送指令")
            return
        self._log("[批量] 开始顺序发送...")
        def _seq(i=0):
            if i >= len(AT_PRESETS): 
                self._log("[批量] 完成"); return
            _, prefix, _, _, is_bd = AT_PRESETS[i]
            self._send_one(i, prefix, is_bd)
            if is_bd:
                return   # 波特率是最后一步，发完自动断开，不再继续
            self.after(900, lambda: _seq(i + 1))
        _seq()

    def _mark(self, idx, ok):
        self._at_res[idx].configure(
            text="✓ OK" if ok else "✗ ERR",
            text_color=COLOR_SUCCESS if ok else COLOR_DANGER)

    def _read_loop(self):
        while self._running:
            try:
                if self._port_obj and self._port_obj.is_open:
                    read_result = read_serial_messages(self._port_obj, encoding="utf-8", log_fn=lambda msg: self._log_q.put(f"[接收] {msg}"))
                    if not read_result.get("ok"):
                        time.sleep(0.05)
                        continue
                    for data in (read_result.get("payload") or {}).get("lines", []):
                        upper = data.upper()
                        if ("ON!" in upper or "BT_OK" in upper or "BT_OFF" in upper
                                or data.isdigit()):
                            self._log_q.put(f"收←◆{data}")
                            if "BT_OK" in upper and not getattr(self, '_greeting_confirmed', False):
                                self._greeting_confirmed = True
                                baud = str(self._port_obj.baudrate)
                                self._log_q.put(f"[连接] ✅ 波特率 {baud} 匹配，模块通信正常")
                        else:
                            self._log_q.put(f"[接收] {data}")
                time.sleep(0.05)
            except Exception as e:
                if self._running:
                    self._running = False
                    self._log_q.put(f"❌ 串口物理连接已断开，请重新连接! ({e})")
                    self.after(0, lambda: self._set_conn_ui(False))
                    if self._port_obj:
                        try:
                            disconnect_port(self._port_obj, log_fn=lambda _msg: None)
                        except Exception:
                            pass
                break

    # ──────────────────────────────────────
    # 日志 & 工具
    # ──────────────────────────────────────
    def _poll_log(self):
        try:
            while True: self._log(self._log_q.get_nowait())
        except queue.Empty: pass
        try:
            self._drive_q.get_nowait()
            self._scan_drives()
            if not self._is_flashing:
                self._set_prog("就绪", 0, TEXT_SECONDARY)
                self._log("[U盘] 盘符变化，已自动刷新并重置状态")
            else:
                self._log("[U盘] 盘符变化，已自动刷新 (操作中，跳过重置状态)")
        except queue.Empty: pass
        self.after(100, self._poll_log)

    def _log(self, text):
        try:
            stamp = datetime.datetime.now().strftime("[%H:%M:%S.%f")[:-3] + "] "
            self._console.configure(state="normal")
            self._console.insert("end", stamp + text + "\n")
            self._console.see("end")
            self._console.configure(state="disabled")
        except Exception:
            pass  # 窗口关闭时忽略

    def _clear_console(self):
        self._console.configure(state="normal")
        self._console.delete("1.0", "end")
        self._console.configure(state="disabled")

    def _card_title(self, parent, title):
        ctk.CTkLabel(parent, text=title,
                     font=(FONT, FLG, "bold"), text_color=TEXT_PRIMARY
                     ).pack(anchor="w", padx=20, pady=(18, 12))


if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    app = MusicFlashTool()
    app.mainloop()
