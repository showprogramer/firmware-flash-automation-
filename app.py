import queue
import threading
import tkinter as tk
import traceback
import os
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core.excel_ops import load_excel_row, read_all_excel_rows
from core.services.excel_service import delete_record, update_record_fields, write_record
from core.services.flash_service import run_one_click
from core.services.scan_service import build_scan_result
from core.services.usb_repair_service import diagnose_drive, repair_drive
from core.settings import (
    CONFIG_LOAD_ERROR,
    CONFIG_LOAD_SOURCE,
    CONFIG_LOAD_STATUS,
    DEFAULT_EXCEL,
    DEFAULT_ROOT,
    EXCEL_SHEET,
    USB_AUTO_DIAGNOSE_ON_INSERT,
    USB_HEALTH_CHECK_INTERVAL_SEC,
)
from core.usb_ops import clean_usb, copy_to_usb, eject_usb, format_usb, get_usb_drives


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("手控 UI 刷机工具")
        self.geometry("1100x740")
        self.resizable(True, True)

        self.root_dir = tk.StringVar(value=DEFAULT_ROOT)
        self.excel_path = tk.StringVar(value=DEFAULT_EXCEL)
        self.usb_drive = tk.StringVar(value="")
        self.folders: list[dict] = []
        self.current_idx = tk.IntVar(value=-1)

        self.field_logo = tk.StringVar()
        self.field_language = tk.StringVar()
        self.field_salesman = tk.StringVar()
        self.field_remark = tk.StringVar()
        self.busy = tk.BooleanVar(value=False)
        self.status_text = tk.StringVar(value="就绪")

        # 搜索关键词
        self.search_var = tk.StringVar()

        self._task_queue: queue.Queue = queue.Queue()
        self._task_id = 0
        self._preview_rows: list[dict] = []
        self._preview_by_key: dict[tuple[str, str], dict] = {}
        self._preview_item_by_key: dict[tuple[str, str], str] = {}
        self._editing_preview_key: tuple[str, str] | None = None
        self._known_usb_drives: set[str] = set()
        self._usb_diag_inflight: set[str] = set()

        self._build_ui()
        self._refresh_usb(log_events=True, detect_insert=False)
        self._report_config_status()
        self._poll_task_queue()
        self._poll_usb_insert_events()
        self._manual_refresh_preview()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        pad = dict(padx=6, pady=3)

        cfg = ttk.LabelFrame(self, text="配置")
        cfg.pack(fill="x", **pad)
        ttk.Label(cfg, text="程序根目录:").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(cfg, textvariable=self.root_dir, width=65).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(cfg, text="浏览", command=self._browse_root).grid(row=0, column=2, **pad)
        ttk.Label(cfg, text="Excel 表格:").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(cfg, textvariable=self.excel_path, width=65).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Button(cfg, text="浏览", command=self._browse_excel).grid(row=1, column=2, **pad)
        cfg.columnconfigure(1, weight=1)

        main_area = ttk.Frame(self)
        main_area.pack(fill="both", expand=True, **pad)

        left = ttk.LabelFrame(main_area, text="手控文件夹列表")
        left.pack(side="left", fill="both", expand=True, padx=(0, 4))
        ttk.Button(left, text="扫描目录", command=self._scan).pack(fill="x", padx=4, pady=2)
        ttk.Button(left, text="刷新预览", command=self._manual_refresh_preview).pack(fill="x", padx=4, pady=(0, 2))
        self.listbox = tk.Listbox(left, selectmode="browse", font=("Consolas", 9), activestyle="dotbox")
        sb = ttk.Scrollbar(left, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=2)
        sb.pack(side="right", fill="y", pady=2)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        self.listbox.bind("<Double-Button-1>", self._open_folder_from_listbox)
        legend = ttk.Frame(left)
        legend.pack(fill="x", padx=4, pady=2)
        for color, lbl in [('#FFFF99', '待确认'), ('#C6EFCE', '测试通过'), ('white', '未操作')]:
            tk.Frame(legend, bg=color, width=12, height=12, relief="solid", bd=1).pack(side="left", padx=(4, 1))
            ttk.Label(legend, text=lbl).pack(side="left", padx=(0, 8))

        right_nb = ttk.Notebook(main_area, width=310)
        right_nb.pack(side="right", fill="both")
        tab_flash = ttk.Frame(right_nb)
        tab_review = ttk.Frame(right_nb)
        right_nb.add(tab_flash, text="  刷机操作  ")
        right_nb.add(tab_review, text="  审核填写  ")
        self._build_flash_tab(tab_flash)
        self._build_review_tab(tab_review)

        bottom = ttk.PanedWindow(self, orient="vertical")
        bottom.pack(fill="both", expand=False, padx=6, pady=(0, 4))
        bottom.configure(height=220)

        log_frame = ttk.LabelFrame(bottom, text="日志")
        self.log_text = tk.Text(log_frame, height=5, font=("Consolas", 9), state="disabled")
        log_sb = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_sb.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_sb.pack(side="right", fill="y")
        bottom.add(log_frame, weight=1)

        prev_frame = ttk.LabelFrame(bottom, text="表格预览（所有已记录条目）")

        # ── 阶段1：搜索栏 ──────────────────────────────────────────────────
        search_bar = ttk.Frame(prev_frame)
        search_bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=(4, 2))
        ttk.Label(search_bar, text="搜索:").pack(side="left")
        search_entry = ttk.Entry(search_bar, textvariable=self.search_var, width=22)
        search_entry.pack(side="left", padx=(4, 8))
        ttk.Button(search_bar, text="清除", command=lambda: self.search_var.set("")).pack(side="left")
        # ── 阶段3：删除按钮 ────────────────────────────────────────────────
        ttk.Button(search_bar, text="删除选中行", command=self._delete_selected_preview_row).pack(side="right", padx=4)
        self.search_var.trace_add("write", lambda *_: self._filter_preview())

        cols = ("序号", "型号", "logo", "业务员", "语言", "版本号", "完成日期", "备注")
        self.preview = ttk.Treeview(prev_frame, columns=cols, show="headings", height=6, selectmode="browse")
        col_widths = [40, 80, 60, 60, 110, 80, 80, 180]
        for col, w in zip(cols, col_widths):
            self.preview.heading(col, text=col)
            self.preview.column(col, width=w, minwidth=w, anchor="w")
        psb_y = ttk.Scrollbar(prev_frame, orient="vertical", command=self.preview.yview)
        psb_x = ttk.Scrollbar(prev_frame, orient="horizontal", command=self.preview.xview)
        self.preview.configure(yscrollcommand=psb_y.set, xscrollcommand=psb_x.set)
        self.preview.grid(row=1, column=0, sticky="nsew")
        psb_y.grid(row=1, column=1, sticky="ns")
        psb_x.grid(row=2, column=0, sticky="ew")
        prev_frame.columnconfigure(0, weight=1)
        prev_frame.rowconfigure(1, weight=1)
        self.preview.tag_configure("待确认", background="#FFFF99")
        self.preview.tag_configure("测试通过", background="#C6EFCE")
        # ── 阶段2：双击回填 ────────────────────────────────────────────────
        self.preview.bind("<Double-1>", self._on_preview_double_click)
        bottom.add(prev_frame, weight=2)

        btn_bar = ttk.Frame(self)
        btn_bar.pack(fill="x", padx=6, pady=(0, 4))
        ttk.Button(btn_bar, text="刷新预览", command=self._manual_refresh_preview).pack(side="left")
        ttk.Label(btn_bar, textvariable=self.status_text, foreground="gray").pack(side="left", padx=12)
        ttk.Button(btn_bar, text="清空日志", command=self._clear_log).pack(side="right")

    def _build_flash_tab(self, parent):
        pad = dict(padx=8, pady=2)
        btn = dict(fill="x", **pad)
        self.lbl_model = ttk.Label(parent, text="型号：-", font=("", 10, "bold"))
        self.lbl_ver = ttk.Label(parent, text="版本：-")
        self.lbl_rom = ttk.Label(parent, text="ROM：-", wraplength=270)
        self.lbl_pkg = ttk.Label(parent, text="PKG：-")
        for w in (self.lbl_model, self.lbl_ver, self.lbl_rom, self.lbl_pkg):
            w.pack(anchor="w", **pad)
        ttk.Separator(parent).pack(fill="x", padx=4, pady=4)
        usb_row = ttk.Frame(parent)
        usb_row.pack(fill="x", padx=8)
        ttk.Label(usb_row, text="U盘:").pack(side="left")
        self.usb_combo = ttk.Combobox(usb_row, textvariable=self.usb_drive, width=6)
        self.usb_combo.pack(side="left", padx=4)
        ttk.Button(usb_row, text="刷新", command=self._refresh_usb).pack(side="left")
        ttk.Button(usb_row, text="驱动扫描/修复", command=self._repair_usb_driver).pack(side="left", padx=4)
        ttk.Separator(parent).pack(fill="x", padx=4, pady=4)
        ttk.Button(parent, text="1  清理 U 盘垃圾文件", command=self._clean_usb).pack(**btn)
        ttk.Button(parent, text="2  格式化 U 盘 (FAT32)", command=self._format_usb).pack(**btn)
        ttk.Button(parent, text="3  复制文件到 U 盘", command=self._copy_to_usb).pack(**btn)
        ttk.Button(parent, text="4  安全弹出 U 盘", command=self._eject_usb).pack(**btn)
        ttk.Separator(parent).pack(fill="x", padx=4, pady=4)
        ttk.Button(parent, text="5  写入记录（待确认）", command=lambda: self._write_excel("待确认")).pack(**btn)
        ttk.Button(parent, text="   标记为【测试通过】", command=lambda: self._write_excel("测试通过")).pack(**btn)
        ttk.Separator(parent).pack(fill="x", padx=4, pady=4)
        ttk.Button(parent, text="★ 一键执行（清理→复制→弹出→写表）", command=self._one_click).pack(**btn)
        ttk.Separator(parent).pack(fill="x", padx=4, pady=4)
        ttk.Button(parent, text="下一个  ▶", command=self._next_folder).pack(**btn)

    def _build_review_tab(self, parent):
        pad = dict(padx=8, pady=4)
        ttk.Label(parent, text="选中列表项后填写详情，点【保存】直接写入 Excel。", foreground="gray").pack(anchor="w", **pad)
        ttk.Label(parent, text="也可双击下方预览表格任意行快速回填字段。", foreground="gray", font=("", 8)).pack(anchor="w", padx=8)
        ttk.Separator(parent).pack(fill="x", padx=4, pady=2)
        fields = [
            ("Logo / 品牌:", self.field_logo, ["中性", "通用", "定制"]),
            ("语言:", self.field_language, ["中、英、越", "中、英", "英文", "希伯来语、俄、英"]),
            ("业务员:", self.field_salesman, []),
        ]
        for label, var, opts in fields:
            row = ttk.Frame(parent)
            row.pack(fill="x", **pad)
            ttk.Label(row, text=label, width=12, anchor="e").pack(side="left")
            if opts:
                ttk.Combobox(row, textvariable=var, values=opts, width=20).pack(side="left", padx=4, fill="x", expand=True)
            else:
                ttk.Entry(row, textvariable=var, width=22).pack(side="left", padx=4, fill="x", expand=True)
        ttk.Label(parent, text="备注:").pack(anchor="w", padx=8)
        self.remark_text = tk.Text(parent, height=4, width=28, font=("", 9))
        self.remark_text.pack(fill="x", padx=8, pady=2)
        ttk.Separator(parent).pack(fill="x", padx=4, pady=6)
        status_row = ttk.Frame(parent)
        status_row.pack(fill="x", padx=8)
        ttk.Label(status_row, text="测试状态:").pack(side="left")
        self.review_status = ttk.Combobox(status_row, values=["待确认", "测试通过", "测试失败"], width=10, state="readonly")
        self.review_status.set("测试通过")
        self.review_status.pack(side="left", padx=4)
        ttk.Button(parent, text="保存到 Excel", command=self._save_review).pack(fill="x", padx=8, pady=8)
        ttk.Label(parent, text="下拉框可直接输入自定义值", foreground="gray", font=("", 8)).pack(anchor="w", padx=8)

    def log(self, msg: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _report_config_status(self):
        status = CONFIG_LOAD_STATUS
        path = CONFIG_LOAD_SOURCE
        if status == "ok":
            self.log(f"配置加载成功: {path}")
            return
        if status == "missing":
            self.log(f"配置文件不存在，使用内置默认配置: {path}")
            return
        err = CONFIG_LOAD_ERROR or "未知错误"
        message = f"配置加载失败，已回退内置默认配置。\n\n路径:\n{path}\n\n原因:\n{err}"
        self.log(message.replace("\n", " "))
        messagebox.showwarning("配置回退", message)

    def _thread_log(self, msg: str):
        self._task_queue.put(("log", msg))

    def _set_status(self, text: str):
        self.status_text.set(text)

    def _set_busy(self, busy: bool, status: str = "就绪"):
        self.busy.set(busy)
        self._set_status(status)
        self._set_all_buttons_state("disabled" if busy else "normal")

    def _set_all_buttons_state(self, state: str):
        def _walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Button):
                    try:
                        child.configure(state=state)
                    except Exception:
                        pass
                _walk(child)

        _walk(self)

    def _run_task(self, name: str, fn, on_done):
        if self.busy.get():
            messagebox.showinfo("提示", "已有任务在执行中，请稍候")
            return

        self._task_id += 1
        task_id = self._task_id
        self._set_busy(True, f"{name}执行中...")

        def worker():
            try:
                result = fn(self._thread_log)
                self._task_queue.put(("done", task_id, name, result, on_done))
            except Exception as e:
                tb = traceback.format_exc()
                self._task_queue.put(("fail", task_id, name, str(e), tb))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _run_non_blocking_task(self, name: str, fn, on_done=None):
        def worker():
            try:
                result = fn(self._thread_log)
                self._task_queue.put(("done_nb", name, result, on_done))
            except Exception as e:
                tb = traceback.format_exc()
                self._task_queue.put(("fail_nb", name, str(e), tb))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _poll_task_queue(self):
        try:
            while True:
                item = self._task_queue.get_nowait()
                kind = item[0]
                if kind == "log":
                    self.log(item[1])
                elif kind == "done":
                    _, _, name, result, on_done = item
                    self._set_busy(False, "就绪")
                    if callable(on_done):
                        on_done(result)
                    self.log(f"{name}完成")
                elif kind == "fail":
                    _, _, name, err, tb = item
                    self._set_busy(False, "就绪")
                    self.log(f"{name}失败: {err}")
                    self.log(tb)
                    messagebox.showerror(f"{name}失败", f"{err}\n\n详情见日志")
                elif kind == "done_nb":
                    _, name, result, on_done = item
                    if callable(on_done):
                        on_done(result)
                    self.log(f"{name}完成")
                elif kind == "fail_nb":
                    _, name, err, tb = item
                    self.log(f"{name}失败: {err}")
                    self.log(tb)
        except queue.Empty:
            pass
        self.after(120, self._poll_task_queue)

    def _on_close(self):
        if self.busy.get() and not messagebox.askyesno("确认退出", "后台任务仍在执行，确认退出吗？"):
            return
        self.destroy()

    def _preview_key(self, model: str, version: str) -> tuple[str, str]:
        return (str(model or "").strip().upper(), str(version or "").strip().upper())

    def _preview_tag(self, remark: str) -> str:
        return "待确认" if remark == "待确认" else ("测试通过" if remark == "测试通过" else "")

    def _preview_values(self, row: dict) -> list[str]:
        return [
            str(row.get("serial", "")),
            str(row.get("model", "")),
            str(row.get("logo", "")),
            str(row.get("salesman", "")),
            str(row.get("language", "")),
            str(row.get("version", "")),
            str(row.get("date", "")),
            str(row.get("remark", "")),
        ]

    def _row_to_preview_dict(self, row: list) -> dict:
        values = [str(v or "") for v in row]
        while len(values) < 9:
            values.append("")
        return {
            "serial": values[0],
            "model": values[1],
            "logo": values[2],
            "salesman": values[3],
            "language": values[4],
            "version": values[5],
            "date": values[6],
            "remark": values[8],
        }

    def _rebuild_preview_tree(self):
        """重建预览树（应用当前搜索过滤）。"""
        for row in self.preview.get_children():
            self.preview.delete(row)
        self._preview_item_by_key = {}
        keyword = self._current_search_keyword()
        for row in self._preview_rows:
            if keyword and not self._row_matches_keyword(row, keyword):
                continue
            key = self._preview_key(row["model"], row["version"])
            item_id = self.preview.insert("", "end", values=self._preview_values(row), tags=(self._preview_tag(row["remark"]),))
            self._preview_item_by_key[key] = item_id

    def _current_search_keyword(self) -> str:
        search_var = self.__dict__.get("search_var")
        if search_var is None:
            return ""
        try:
            return str(search_var.get() or "").strip().lower()
        except Exception:
            return ""

    def _row_matches_keyword(self, row: dict, keyword: str) -> bool:
        """检查行是否包含关键词（不区分大小写，匹配型号/版本/logo/备注/语言/业务员）。"""
        fields = ("model", "version", "logo", "salesman", "language", "remark", "serial")
        return any(keyword in str(row.get(f, "")).lower() for f in fields)

    # ── 阶段1：搜索过滤 ───────────────────────────────────────────────────────

    def _filter_preview(self):
        """搜索框内容变化时重建预览树（纯内存过滤，不读磁盘）。"""
        self._rebuild_preview_tree()

    def _reindex_preview_serials(self):
        for i, row in enumerate(self._preview_rows, start=1):
            row["serial"] = str(i)

    def _update_listbox_color_by_key(self, model: str, version: str, remark: str):
        target_key = self._preview_key(model, version)
        for i, item in enumerate(self.folders):
            if self._preview_key(item.get("model", ""), item.get("version", "")) == target_key:
                self._update_listbox_color(i, remark)

    # ── 阶段2：双击预览行回填到审核 tab ──────────────────────────────────────

    def _on_preview_double_click(self, _event=None):
        """双击预览表格中的行，将该行数据回填到审核填写 tab。"""
        sel = self.preview.selection()
        if not sel:
            return
        values = self.preview.item(sel[0], "values")
        # values 顺序: 序号 型号 logo 业务员 语言 版本号 完成日期 备注
        if len(values) < 8:
            return
        _serial, model, logo, salesman, language, version, _date, remark = values[:8]
        key = self._preview_key(model, version)
        self._editing_preview_key = key
        source = self._preview_by_key.get(key, {})
        if source:
            model = source.get("model", model)
            version = source.get("version", version)
            logo = source.get("logo", logo)
            salesman = source.get("salesman", salesman)
            language = source.get("language", language)
            remark = source.get("remark", remark)

        self.field_logo.set(logo)
        self.field_language.set(language)
        self.field_salesman.set(salesman)
        self.remark_text.delete("1.0", "end")
        self.remark_text.insert("1.0", remark)

        # 同步更新刷机操作 tab 的型号/版本显示
        self.lbl_model.config(text=f"型号：{model}")
        self.lbl_ver.config(text=f"版本：{version}")
        self.lbl_rom.config(text="ROM：（从预览回填，请在列表选择后确认）")
        self.lbl_pkg.config(text="PKG：-")

        self.log(f"已从预览回填: {model} {version}")

    # ── 阶段3：删除选中预览行 ─────────────────────────────────────────────────

    def _delete_selected_preview_row(self):
        """删除预览表格中选中的行（同步删除 Excel 中对应记录）。"""
        sel = self.preview.selection()
        if not sel:
            messagebox.showwarning("提示", "请先在预览表格中选择要删除的行")
            return
        values = self.preview.item(sel[0], "values")
        if len(values) < 6:
            return
        model = str(values[1]).strip()
        version = str(values[5]).strip()
        if not model or not version:
            messagebox.showwarning("提示", "所选行缺少型号或版本号，无法删除")
            return
        if not messagebox.askyesno(
            "确认删除",
            f"将从 Excel 表格中永久删除以下记录：\n\n型号：{model}\n版本：{version}\n\n此操作不可撤销，确认吗？"
        ):
            return

        excel = self.excel_path.get()

        def _work(log_fn):
            log_fn(f"删除记录: {model} {version}")
            return delete_record(excel, EXCEL_SHEET, model, version, log_fn=log_fn)

        def _done(result):
            if result.get("ok"):
                # 从内存缓存和预览树移除
                key = self._preview_key(model, version)
                self._preview_rows = [r for r in self._preview_rows
                                      if self._preview_key(r["model"], r["version"]) != key]
                self._preview_by_key.pop(key, None)
                self._preview_item_by_key.pop(key, None)
                if self._editing_preview_key == key:
                    self._editing_preview_key = None
                self._reindex_preview_serials()
                self._rebuild_preview_tree()
                self.log(f"  已删除: {model} {version} ✓")
            else:
                code = str(result.get("code", "delete_failed"))
                msg = str(result.get("message", "未知错误"))
                if code == "not_found":
                    messagebox.showwarning("未找到记录", f"Excel 中未找到 {model} {version} 的记录")
                elif code == "locked":
                    messagebox.showwarning("Excel 被占用", "请关闭 WPS/Excel 后重试")
                else:
                    messagebox.showerror("删除失败", f"删除失败：\n{msg}")

        self._run_task("删除记录", _work, _done)

    def _upsert_preview_row(self, row: dict):
        key = self._preview_key(row.get("model", ""), row.get("version", ""))
        normalized = {
            "serial": str(row.get("serial", "")),
            "model": str(row.get("model", "")),
            "logo": str(row.get("logo", "")),
            "salesman": str(row.get("salesman", "")),
            "language": str(row.get("language", "")),
            "version": str(row.get("version", "")),
            "date": str(row.get("date", "")),
            "remark": str(row.get("remark", "")),
        }
        keyword = self._current_search_keyword()
        existing = self._preview_by_key.get(key)
        if existing is not None:
            if not normalized["serial"]:
                normalized["serial"] = str(existing.get("serial", ""))
            if not normalized["date"]:
                normalized["date"] = str(existing.get("date", ""))
            self._preview_by_key[key] = normalized
            replaced = False
            for i, cached in enumerate(self._preview_rows):
                if self._preview_key(cached["model"], cached["version"]) == key:
                    self._preview_rows[i] = normalized
                    replaced = True
                    break
            if not replaced:
                self._preview_rows.append(normalized)

            visible = not keyword or self._row_matches_keyword(normalized, keyword)
            item_id = self._preview_item_by_key.get(key)
            if visible:
                if item_id:
                    self.preview.item(
                        item_id,
                        values=self._preview_values(normalized),
                        tags=(self._preview_tag(normalized["remark"]),),
                    )
                else:
                    item_id = self.preview.insert(
                        "", "end", values=self._preview_values(normalized), tags=(self._preview_tag(normalized["remark"]),)
                    )
                    self._preview_item_by_key[key] = item_id
            elif item_id:
                self.preview.delete(item_id)
                self._preview_item_by_key.pop(key, None)
            return

        self._preview_rows.append(normalized)
        self._preview_by_key[key] = normalized
        if not keyword or self._row_matches_keyword(normalized, keyword):
            item_id = self.preview.insert("", "end", values=self._preview_values(normalized), tags=(self._preview_tag(normalized["remark"]),))
            self._preview_item_by_key[key] = item_id

    def _manual_refresh_preview(self):
        self._reload_preview_cache_from_disk()

    def _reload_preview_cache_from_disk(self):
        def _work(_log_fn):
            rows = read_all_excel_rows(self.excel_path.get(), EXCEL_SHEET)
            return [self._row_to_preview_dict(r) for r in rows]

        def _done(preview_rows):
            self._preview_rows = preview_rows
            self._preview_by_key = {self._preview_key(r["model"], r["version"]): r for r in preview_rows}
            self._rebuild_preview_tree()

        self._run_task("刷新预览", _work, _done)

    def _browse_root(self):
        d = filedialog.askdirectory(initialdir=self.root_dir.get())
        if d:
            self.root_dir.set(d)

    def _browse_excel(self):
        f = filedialog.askopenfilename(
            initialdir=str(Path(self.excel_path.get()).parent),
            filetypes=[("Excel", "*.xlsx *.xls"), ("All", "*.*")],
        )
        if f:
            self.excel_path.set(f)
            self._manual_refresh_preview()

    def _refresh_usb(self, log_events: bool = True, detect_insert: bool = True) -> list[str]:
        drives = get_usb_drives()
        prev = set(self._known_usb_drives)
        current = set(drives)
        inserted = [d for d in drives if d not in prev] if detect_insert else []
        removed = [d for d in prev if d not in current]
        self._known_usb_drives = current

        self.usb_combo["values"] = drives
        current_selected = self.usb_drive.get()
        if drives:
            if current_selected not in current:
                self.usb_drive.set(drives[0])
            if log_events and inserted:
                self.log(f"检测到 U 盘: {', '.join(inserted)}")
        else:
            self.usb_drive.set("")
            if log_events and removed:
                self.log("未检测到可用 U 盘")
        return inserted

    def _poll_usb_insert_events(self):
        try:
            inserted = self._refresh_usb(log_events=False, detect_insert=True)
            if USB_AUTO_DIAGNOSE_ON_INSERT and inserted:
                for drive in inserted:
                    self._diagnose_usb_inserted(drive)
        finally:
            self.after(max(2, int(USB_HEALTH_CHECK_INTERVAL_SEC)) * 1000, self._poll_usb_insert_events)

    def _diagnose_usb_inserted(self, drive: str):
        key = drive.upper()
        if key in self._usb_diag_inflight:
            return
        self._usb_diag_inflight.add(key)

        def _work(log_fn):
            log_fn(f"检测到新 U 盘，开始健康检查: {drive}")
            return diagnose_drive(drive, log_fn=log_fn)

        def _done(result):
            self._usb_diag_inflight.discard(key)
            if result.get("ok"):
                return
            self._set_status("U盘可能异常，请点驱动修复")
            msg = result.get("message", "U盘健康检查失败")
            self.log(f"U盘健康检查提示: {msg}")

        self._run_non_blocking_task("U盘健康检查", _work, _done)

    def _scan(self):
        root = self.root_dir.get()
        if not root:
            messagebox.showwarning("提示", "请先选择程序根目录")
            return

        def _work(log_fn):
            return build_scan_result(root, self.excel_path.get(), EXCEL_SHEET, log_fn=log_fn)

        def _done(result):
            if not result.get("ok"):
                messagebox.showerror("扫描失败", result.get("message", "未知错误"))
                return
            payload = result.get("payload", {})
            self.listbox.delete(0, "end")
            self.folders = payload.get("folders", [])
            status_map = payload.get("status_map", {})
            for i, item in enumerate(self.folders):
                display_label = f"{i + 1:03d}. {item['label']}"
                self.listbox.insert("end", display_label)
                key = (item["model"].upper(), item["version"].upper())
                status = status_map.get(key, "")
                if status == "待确认":
                    self.listbox.itemconfig(i, bg="#FFFF99", fg="black")
                elif status == "测试通过":
                    self.listbox.itemconfig(i, bg="#C6EFCE", fg="black")
            tested = int(payload.get("tested", 0))
            pending = int(payload.get("pending", 0))
            self.log(f"共找到 {len(self.folders)} 个手控文件夹（已测: {tested}，待确认: {pending}）")

        self._run_task("扫描目录", _work, _done)

    def _refresh_preview(self):
        self._manual_refresh_preview()

    def _update_listbox_color(self, idx: int, remark: str):
        if idx < 0 or idx >= self.listbox.size():
            return
        if remark == "待确认":
            self.listbox.itemconfig(idx, bg="#FFFF99", fg="black")
        elif remark == "测试通过":
            self.listbox.itemconfig(idx, bg="#C6EFCE", fg="black")
        else:
            self.listbox.itemconfig(idx, bg="white", fg="black")

    def _on_select(self, _event=None):
        sel = self.listbox.curselection()
        if not sel:
            return
        self._editing_preview_key = None
        idx = sel[0]
        self.current_idx.set(idx)
        info = self.folders[idx]
        self.lbl_model.config(text=f"型号：{info['model']}")
        self.lbl_ver.config(text=f"版本：{info['version']}")
        self.lbl_rom.config(text=f"ROM：{info['rom_file']}")
        self.lbl_pkg.config(text=f"PKG：{info['pkg_file']}")
        existing = load_excel_row(self.excel_path.get(), EXCEL_SHEET, info["model"], info["version"])
        self.field_logo.set(existing.get("logo", ""))
        self.field_language.set(existing.get("language", ""))
        self.field_salesman.set(existing.get("salesman", ""))
        self.remark_text.delete("1.0", "end")
        self.remark_text.insert("1.0", existing.get("remark", ""))

    def _open_folder_from_listbox(self, event=None):
        idx = None
        if event is not None and hasattr(event, "y"):
            try:
                idx = int(self.listbox.nearest(event.y))
            except Exception:
                idx = None
        if idx is None:
            sel = self.listbox.curselection()
            if sel:
                idx = int(sel[0])
        if idx is None or idx < 0 or idx >= len(self.folders):
            return

        try:
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(idx)
        except Exception:
            pass

        self.current_idx.set(idx)
        self._on_select()
        info = self.folders[idx]
        self._open_in_explorer(info.get("path", ""), info.get("model", ""), info.get("version", ""))

    def _open_in_explorer(self, folder_path: str, model: str = "", version: str = ""):
        path_str = str(folder_path or "").strip()
        if not path_str:
            messagebox.showwarning("提示", "该项缺少目录路径，无法快速定位")
            return
        path_obj = Path(path_str)
        if not path_obj.exists() or not path_obj.is_dir():
            messagebox.showwarning("路径不存在", f"目录不存在：\n{path_obj}")
            self.log(f"快速定位失败，目录不存在: {path_obj}")
            return

        try:
            if hasattr(os, "startfile"):
                os.startfile(str(path_obj))  # type: ignore[attr-defined]
            else:
                raise RuntimeError("当前系统不支持 Explorer 快速定位")
        except Exception as exc:
            self.log(f"快速定位失败: {path_obj} ({exc})")
            messagebox.showerror("打开失败", f"无法打开目录：\n{path_obj}\n\n{exc}")
            return

        label = f"{model} {version}".strip()
        if label:
            self.log(f"快速定位已打开: {label} -> {path_obj}")
        else:
            self.log(f"快速定位已打开: {path_obj}")

    def _current_info(self) -> dict | None:
        idx = self.current_idx.get()
        if idx < 0 or idx >= len(self.folders):
            messagebox.showwarning("提示", "请先在列表中选择一个手控文件夹")
            return None
        return self.folders[idx]

    def _clean_usb(self):
        drive = self.usb_drive.get()
        if not drive:
            messagebox.showwarning("提示", "未检测到 U 盘，请插入后点击刷新")
            return

        def _work(log_fn):
            log_fn(f"清理 U 盘 {drive} ...")
            return clean_usb(drive, log_fn)

        def _done(n):
            self.log(f"  清理完成，删除 {n} 个垃圾文件")

        self._run_task("清理U盘", _work, _done)

    def _format_usb(self):
        drive = self.usb_drive.get()
        if not drive:
            messagebox.showwarning("提示", "未检测到 U 盘")
            return
        if not messagebox.askyesno("确认", f"将格式化 {drive}，所有数据会丢失，确认吗？"):
            return

        def _work(log_fn):
            log_fn(f"格式化 {drive} ...")
            return format_usb(drive, log_fn)

        def _done(ok):
            self.log("格式化成功" if ok else "格式化失败，请手动格式化")

        self._run_task("格式化U盘", _work, _done)

    def _copy_to_usb(self):
        info = self._current_info()
        if not info:
            return
        drive = self.usb_drive.get()
        if not drive:
            messagebox.showwarning("提示", "未检测到 U 盘")
            return
        rom = str(Path(info["path"]) / info["rom_file"])
        pkg = str(Path(info["path"]) / info["pkg_file"])

        def _work(log_fn):
            log_fn(f"复制文件到 {drive} ...")
            return copy_to_usb(rom, pkg, drive, log_fn)

        def _done(ok):
            if ok:
                self.log("复制完成")

        self._run_task("复制到U盘", _work, _done)

    def _eject_usb(self):
        drive = self.usb_drive.get()
        if not drive:
            messagebox.showwarning("提示", "未检测到 U 盘")
            return

        def _work(log_fn):
            log_fn(f"弹出 {drive} ...")
            return eject_usb(drive, log_fn)

        self._run_task("弹出U盘", _work, lambda _ok: None)

    def _repair_usb_driver(self):
        drive = self.usb_drive.get()
        if not drive:
            messagebox.showwarning("提示", "未检测到 U 盘")
            return
        if not messagebox.askyesno("确认", f"将对 {drive} 执行 Windows 扫描/修复命令（chkdsk + pnputil），确认吗？"):
            return

        def _work(log_fn):
            return repair_drive(drive, log_fn=log_fn)

        def _done(result):
            if result.get("ok"):
                self._set_status("U盘驱动修复完成")
                messagebox.showinfo("完成", "U盘驱动修复完成")
                return
            msg = str(result.get("message", "U盘驱动修复失败"))
            messagebox.showerror("修复失败", msg)

        self._run_task("驱动修复", _work, _done)

    def _write_excel(self, remark: str):
        info = self._current_info()
        if not info:
            return
        excel = self.excel_path.get()
        logo = self.field_logo.get().strip()
        language = self.field_language.get().strip()
        salesman = self.field_salesman.get().strip()
        rom_path = str(Path(info["path"]) / info["rom_file"])

        def _work(log_fn):
            log_fn(
                f"写入 Excel: {info['model']} {info['version']}  "
                f"logo={logo}  语言={language}  业务员={salesman}  [{remark}]"
            )
            return write_record(
                excel_path=excel,
                sheet_name=EXCEL_SHEET,
                model=info["model"],
                version=info["version"],
                remark=remark,
                rom_path=rom_path,
                logo=logo,
                language=language,
                salesman=salesman,
                log_fn=log_fn,
            )

        def _done(result):
            if result.get("ok"):
                self._update_listbox_color(self.current_idx.get(), remark)
                written = (result.get("payload", {}) or {}).get("preview_row", {})
                if written:
                    self._upsert_preview_row(written)
                return
            excel_result = (result.get("payload", {}) or {}).get("excel_result") or {}
            if result.get("code") == "locked":
                tmp = excel_result.get("tmp_path") or str(Path(excel).with_name(Path(excel).stem + "_刷机记录_待导入.xlsx"))
                messagebox.showwarning(
                    "Excel 被占用",
                    f"表格被 WPS/Excel 占用，无法直接写入。\n\n已将记录保存到备用文件：\n{tmp}\n\n"
                    "解决方法：\n① 关闭 WPS/Excel 后再点一次写入按钮\n② 或打开备用文件，手动复制该行到主表",
                )
            else:
                err = result.get("message", "") or "未知错误"
                messagebox.showerror("Excel 写入失败", f"未能写入 Excel。\n\n错误信息：\n{err}")

        self._run_task("写入Excel", _work, _done)

    def _one_click(self):
        info = self._current_info()
        if not info:
            return
        drive = self.usb_drive.get()
        if not drive:
            messagebox.showwarning("提示", "未检测到 U 盘，请插入后点击刷新")
            return
        logo = self.field_logo.get().strip()
        language = self.field_language.get().strip()
        salesman = self.field_salesman.get().strip()
        rom = str(Path(info["path"]) / info["rom_file"])
        pkg = str(Path(info["path"]) / info["pkg_file"])

        def _work(log_fn):
            return run_one_click(
                drive=drive,
                model=info["model"],
                version=info["version"],
                rom_path=rom,
                pkg_path=pkg,
                excel_path=self.excel_path.get(),
                sheet_name=EXCEL_SHEET,
                logo=logo,
                language=language,
                salesman=salesman,
                log_fn=log_fn,
            )

        def _done(result):
            payload = result.get("payload", {}) or {}
            if not payload.get("copy_ok", False):
                return
            excel_result = payload.get("excel_result", {}) or {}
            if excel_result.get("ok"):
                self._update_listbox_color(self.current_idx.get(), "待确认")
                written = payload.get("preview_row", {})
                if written:
                    self._upsert_preview_row(written)
            self.log("一键完成！请插入手控器测试 ✓")
            if not excel_result.get("ok") and excel_result.get("reason") == "locked":
                excel = self.excel_path.get()
                tmp = excel_result["tmp_path"] or str(Path(excel).with_name(Path(excel).stem + "_刷机记录_待导入.xlsx"))
                messagebox.showwarning(
                    "Excel 被占用",
                    f"U盘已准备好，但 Excel 写入失败（文件被占用）。\n\n记录已暂存到：\n{tmp}\n\n"
                    "关闭 WPS/Excel 后，点【写入记录】补录即可。",
                )
            elif not excel_result.get("ok"):
                err = excel_result.get("error", "") or "未知错误"
                messagebox.showerror("Excel 写入失败", f"U盘已准备好，但写入 Excel 失败。\n\n错误信息：\n{err}")
            self.log("=" * 50)

        self._run_task("一键执行", _work, _done)

    def _save_review(self):
        excel = self.excel_path.get()
        logo = self.field_logo.get().strip()
        language = self.field_language.get().strip()
        salesman = self.field_salesman.get().strip()
        remark = self.remark_text.get("1.0", "end").strip()
        status = self.review_status.get()
        final_remark = status if not remark or remark == status else f"{status}  |  {remark}"
        editing_key = getattr(self, "_editing_preview_key", None)
        if editing_key:
            existing = self._preview_by_key.get(editing_key, {})
            model = str(existing.get("model", editing_key[0]))
            version = str(existing.get("version", editing_key[1]))

            def _work(log_fn):
                log_fn(f"审核保存(历史): {model} {version}  logo={logo}  语言={language}  [{status}]")
                return update_record_fields(
                    excel_path=excel,
                    sheet_name=EXCEL_SHEET,
                    model=model,
                    version=version,
                    logo=logo,
                    salesman=salesman,
                    language=language,
                    remark=final_remark,
                    log_fn=log_fn,
                )

            def _done(result):
                if result.get("ok"):
                    self._update_listbox_color_by_key(model, version, status)
                    written = (result.get("payload", {}) or {}).get("preview_row", {})
                    if written:
                        self._upsert_preview_row(written)
                    self.log("  保存成功 ✓")
                    return
                code = str(result.get("code", "write_failed"))
                msg = str(result.get("message", "未知错误"))
                if code == "locked":
                    messagebox.showwarning("Excel 被占用", "请关闭 WPS/Excel 后重试。")
                else:
                    messagebox.showerror("Excel 写入失败", f"保存失败。\n\n错误信息：\n{msg}")

            self._run_task("审核保存", _work, _done)
            return

        info = self._current_info()
        if not info:
            return
        rom_path = str(Path(info["path"]) / info["rom_file"])

        def _work(log_fn):
            log_fn(f"审核保存: {info['model']} {info['version']}  logo={logo}  语言={language}  [{status}]")
            return write_record(
                excel_path=excel,
                sheet_name=EXCEL_SHEET,
                model=info["model"],
                version=info["version"],
                remark=final_remark,
                rom_path=rom_path,
                logo=logo,
                language=language,
                salesman=salesman,
                log_fn=log_fn,
            )

        def _done(result):
            if result.get("ok"):
                self._update_listbox_color(self.current_idx.get(), status)
                written = (result.get("payload", {}) or {}).get("preview_row", {})
                if written:
                    self._upsert_preview_row(written)
                self.log("  保存成功 ✓")
                return
            excel_result = (result.get("payload", {}) or {}).get("excel_result") or {}
            if result.get("code") == "locked":
                tmp = excel_result.get("tmp_path") or str(Path(excel).with_name(Path(excel).stem + "_刷机记录_待导入.xlsx"))
                messagebox.showwarning("Excel 被占用", f"请关闭 WPS/Excel 后重试。\n已暂存到：\n{tmp}")
            else:
                err = result.get("message", "") or "未知错误"
                messagebox.showerror("Excel 写入失败", f"保存失败。\n\n错误信息：\n{err}")

        self._run_task("审核保存", _work, _done)

    def _next_folder(self):
        idx = self.current_idx.get()
        next_idx = idx + 1
        if next_idx >= len(self.folders):
            messagebox.showinfo("提示", "已经是最后一个文件夹了")
            return
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(next_idx)
        self.listbox.see(next_idx)
        self._on_select()
        self.log(f"切换到下一个: {self.folders[next_idx]['label']}")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
