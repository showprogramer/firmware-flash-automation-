from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from fwasset.core.usb_ops import get_usb_drives
from fwasset.ui.design_tokens import (
    BG_APP,
    BG_CARD,
    BG_HOVER,
    BG_INPUT,
    BG_SIDEBAR,
    BORDER_COLOR,
    COLOR_PRIMARY,
    FONT_FAMILY,
    FONT_SIZE_LG,
    FONT_SIZE_MD,
    TEXT_PRIMARY,
)


class BaseFlashPanel(ctk.CTkFrame):
    mode_switch_values = ["手控模式", "音乐模式"]
    busy_message = "已有任务执行中，请稍后"
    task_done_suffix = "完成"
    task_error_title_suffix = "失败"

    def __init__(self, master):
        super().__init__(master, fg_color=BG_APP)
        self.usb_drive = tk.StringVar(value="")
        self._task_queue: queue.Queue = queue.Queue()
        self._busy = False
        self._polling_active = False

        self.grid_columnconfigure(0, weight=0, minsize=320)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

    def activate(self):
        if self._polling_active:
            return
        self._polling_active = True
        self._poll_task_queue()

    def deactivate(self):
        self._polling_active = False

    def _build_sidebar_frame(self, width: int = 320) -> ctk.CTkFrame:
        sidebar = ctk.CTkFrame(self, width=width, corner_radius=0, fg_color=BG_SIDEBAR)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        return sidebar

    def _build_brand_header(self, parent, title: str = "程序资产管理系统"):
        brand_frame = ctk.CTkFrame(parent, fg_color="transparent")
        brand_frame.pack(fill="x", padx=24, pady=(32, 16))
        ctk.CTkLabel(
            brand_frame,
            text="⚡",
            font=(FONT_FAMILY, 24),
            text_color=COLOR_PRIMARY,
        ).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(
            brand_frame,
            text=title,
            font=(FONT_FAMILY, FONT_SIZE_LG, "bold"),
            text_color=TEXT_PRIMARY,
        ).pack(side="left")

    def _build_main_container(self) -> ctk.CTkFrame:
        main = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew", padx=32, pady=32)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)
        return main

    def _build_usb_selector_row(self, parent, refresh_command=None):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=10)
        self.usb_menu = ctk.CTkComboBox(
            row,
            variable=self.usb_drive,
            values=[""],
            width=120,
            height=36,
            corner_radius=6,
        )
        self.usb_menu.pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            row,
            text="刷新",
            width=60,
            height=36,
            fg_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            hover_color=BG_HOVER,
            command=refresh_command or self._refresh_usb,
        ).pack(side="left", padx=4)
        return row

    def _log(self, message: str):
        if hasattr(self, "log_text"):
            self.log_text.insert("end", f"[{Path(__file__).name}] {message or ''}\n")
            self.log_text.see("end")

    def _run_task(self, name: str, fn, on_done=None):
        if self._busy:
            self._log(self.busy_message)
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
                    if callable(on_done):
                        on_done(payload)
                    self._log(f"{name}{self.task_done_suffix}")
                else:
                    self._handle_task_failure(name, payload)
        except queue.Empty:
            pass
        self.after(120, self._poll_task_queue)

    def _handle_task_failure(self, name: str, payload):
        self._log(f"{name}{self.task_error_title_suffix}: {payload}")
        messagebox.showerror(f"{name}{self.task_error_title_suffix}", str(payload))

    def _refresh_usb(self):
        drives = get_usb_drives() or [""]
        if not hasattr(self, "usb_menu"):
            self._log(f"U盘刷新: {', '.join([d for d in drives if d]) or '未发现'}")
            return
        self.usb_menu.configure(values=drives)
        if self.usb_drive.get() not in drives:
            self.usb_drive.set(drives[0])
        self._log(f"U盘刷新: {', '.join([d for d in drives if d]) or '未发现'}")
