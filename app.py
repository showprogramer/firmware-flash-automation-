import queue
import threading
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core.excel_ops import load_excel_row, read_all_excel_rows
from core.services.excel_service import write_record
from core.services.flash_service import run_one_click
from core.services.scan_service import build_scan_result
from core.settings import (
    CONFIG_LOAD_ERROR,
    CONFIG_LOAD_SOURCE,
    CONFIG_LOAD_STATUS,
    DEFAULT_EXCEL,
    DEFAULT_ROOT,
    EXCEL_SHEET,
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

        self._task_queue: queue.Queue = queue.Queue()
        self._task_id = 0
        self._preview_rows: list[dict] = []
        self._preview_by_key: dict[tuple[str, str], dict] = {}
        self._preview_item_by_key: dict[tuple[str, str], str] = {}

        self._build_ui()
        self._refresh_usb()
        self._report_config_status()
        self._poll_task_queue()
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
        cols = ("序号", "型号", "logo", "业务员", "语言", "版本号", "完成日期", "备注")
        self.preview = ttk.Treeview(prev_frame, columns=cols, show="headings", height=6, selectmode="browse")
        col_widths = [40, 80, 60, 60, 110, 80, 80, 180]
        for col, w in zip(cols, col_widths):
            self.preview.heading(col, text=col)
            self.preview.column(col, width=w, minwidth=w, anchor="w")
        psb_y = ttk.Scrollbar(prev_frame, orient="vertical", command=self.preview.yview)
        psb_x = ttk.Scrollbar(prev_frame, orient="horizontal", command=self.preview.xview)
        self.preview.configure(yscrollcommand=psb_y.set, xscrollcommand=psb_x.set)
        self.preview.grid(row=0, column=0, sticky="nsew")
        psb_y.grid(row=0, column=1, sticky="ns")
        psb_x.grid(row=1, column=0, sticky="ew")
        prev_frame.columnconfigure(0, weight=1)
        prev_frame.rowconfigure(0, weight=1)
        self.preview.tag_configure("待确认", background="#FFFF99")
        self.preview.tag_configure("测试通过", background="#C6EFCE")
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
        for row in self.preview.get_children():
            self.preview.delete(row)
        self._preview_item_by_key = {}
        for row in self._preview_rows:
            key = self._preview_key(row["model"], row["version"])
            item_id = self.preview.insert("", "end", values=self._preview_values(row), tags=(self._preview_tag(row["remark"]),))
            self._preview_item_by_key[key] = item_id

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
        item_id = self._preview_item_by_key.get(key)
        if item_id:
            existing = self._preview_by_key.get(key, {})
            if not normalized["serial"]:
                normalized["serial"] = str(existing.get("serial", ""))
            self.preview.item(item_id, values=self._preview_values(normalized), tags=(self._preview_tag(normalized["remark"]),))
            self._preview_by_key[key] = normalized
            for i, existing in enumerate(self._preview_rows):
                if self._preview_key(existing["model"], existing["version"]) == key:
                    self._preview_rows[i] = normalized
                    break
            return
        item_id = self.preview.insert("", "end", values=self._preview_values(normalized), tags=(self._preview_tag(normalized["remark"]),))
        self._preview_rows.append(normalized)
        self._preview_by_key[key] = normalized
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

    def _refresh_usb(self):
        drives = get_usb_drives()
        self.usb_combo["values"] = drives
        if drives:
            self.usb_drive.set(drives[0])
            self.log(f"检测到 U 盘: {', '.join(drives)}")
        else:
            self.usb_drive.set("")

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
                self.listbox.insert("end", item["label"])
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
        info = self._current_info()
        if not info:
            return
        excel = self.excel_path.get()
        logo = self.field_logo.get().strip()
        language = self.field_language.get().strip()
        salesman = self.field_salesman.get().strip()
        remark = self.remark_text.get("1.0", "end").strip()
        status = self.review_status.get()
        final_remark = status if not remark or remark == status else f"{status}  |  {remark}"
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
