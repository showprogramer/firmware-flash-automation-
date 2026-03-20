"""
手控 UI 刷机工具
================
功能：
  1. 扫描指定根目录，列出所有含 .ROM + .PKG 的手控文件夹
  2. 检测 U 盘插入，清理垃圾文件（.usu 等），可选格式化
  3. 复制 .ROM / .PKG 到 U 盘，安全弹出
  4. 记录测试结果到 Excel 表格（追加或更新行）

运行方式：
  python 手控刷机工具.py
  （Python 3.8+ / Windows）
"""

import os
import re
import shutil
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from datetime import datetime

import psutil
import openpyxl
from openpyxl.styles import PatternFill

# ── 默认配置 ──────────────────────────────────────────────────────────────────
DEFAULT_ROOT   = r"D:\按摩椅相关文件汇总\YJ-按摩椅家用，商用程序汇总（之前没整理的）"
DEFAULT_EXCEL  = str(Path(__file__).resolve().parent / "data" / "handcontrol_ui_template.xlsx")
EXCEL_SHEET    = "Sheet1"
EXCEL_HEADER_ROW = 2          # 第2行是表头（第1行是大标题）
JUNK_EXTENSIONS = {".usu", ".tmp", ".bak"}
JUNK_FILENAMES  = {"autorun.inf"}


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def find_handcontrol_folders(root: str) -> list[dict]:
    """
    递归扫描 root，找到同时含有 .ROM 和 .PKG 文件的最深一级文件夹。
    返回列表，每项 dict 含：
      path, rom_file, pkg_file, model, version
    """
    results = []
    root_path = Path(root)

    for dirpath, dirnames, filenames in os.walk(root_path):
        # 跳过驱动工具目录
        if "CH341SER" in dirpath or "主板程序" in dirpath:
            continue

        lower_files = {f.lower(): f for f in filenames}
        rom_files = [f for f in filenames if f.lower().endswith(".rom")]
        pkg_files = [f for f in filenames if f.lower().endswith(".pkg")]

        if rom_files and pkg_files:
            rom = rom_files[0]   # 通常只有一个
            pkg = pkg_files[0]
            model, version = parse_rom_filename(rom)
            # 如果 model 还是空，用文件夹名推断
            if not model:
                model = guess_model_from_path(dirpath)

            results.append({
                "path":     dirpath,
                "rom_file": rom,
                "pkg_file": pkg,
                "model":    model,
                "version":  version,
                "label":    f"{model}  {version}  [{Path(dirpath).name}]",
            })

    results.sort(key=lambda x: x["path"])
    return results


def parse_rom_filename(name: str) -> tuple[str, str]:
    """
    从文件名解析型号和版本号。
    支持格式：
      YJ-L50S-3122MG-791_UI_118.3.10.ROM
      ITE_NOR_yj_massage_4d_music_L36_v34.3.2.ROM
      ITE_NOR.ROM  (无版本)
    """
    name_no_ext = Path(name).stem

    # 型号：匹配 L\d+ 系列  如 L36 L39S L50S L26Amax
    # 用 _ 或 - 作为单词边界（文件名里没有真正的 \b）
    model_match = re.search(r'(?:^|[_\-])((L\d+[A-Za-z]*))(?:[_\-]|$)', name_no_ext, re.IGNORECASE)
    model = model_match.group(1).upper() if model_match else ""

    # 版本号：匹配 v/V 后跟数字点号  或 _UI_xxx  或 末尾数字串
    ver_match = re.search(r'[Vv](\d+\.\d+(?:\.\d+)?)', name_no_ext)
    if not ver_match:
        ver_match = re.search(r'_UI_(\d+\.\d+(?:\.\d+)?)', name_no_ext)
    if not ver_match:
        ver_match = re.search(r'_(\d+\.\d+\.\d+)$', name_no_ext)
    version = "V" + ver_match.group(1) if ver_match else ""

    return model, version


def guess_model_from_path(dirpath: str) -> str:
    """从路径片段猜型号"""
    for part in reversed(Path(dirpath).parts):
        m = re.search(r'\b(L\d+[A-Za-z]*(?:max|pro|s)?)\b', part, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return "未知型号"


def get_usb_drives() -> list[str]:
    """返回当前所有 USB 可移动驱动器盘符列表，如 ['E:\\', 'F:\\']"""
    drives = []
    for part in psutil.disk_partitions(all=False):
        if "removable" in part.opts.lower() or part.fstype.upper() in ("FAT32", "FAT", "EXFAT"):
            drives.append(part.mountpoint)
    return drives


def clean_usb(drive: str, log_fn=print) -> int:
    """删除 U 盘根目录垃圾文件，返回删除数量"""
    removed = 0
    root = Path(drive)
    for f in root.iterdir():
        if f.is_file():
            if f.suffix.lower() in JUNK_EXTENSIONS or f.name.lower() in JUNK_FILENAMES:
                try:
                    f.unlink()
                    log_fn(f"  删除垃圾文件: {f.name}")
                    removed += 1
                except Exception as e:
                    log_fn(f"  删除失败 {f.name}: {e}")
    return removed


def copy_to_usb(rom_path: str, pkg_path: str, drive: str, log_fn=print) -> bool:
    """复制 ROM 和 PKG 到 U 盘根目录，先清空根目录已有的同类文件"""
    drive_root = Path(drive)
    try:
        # 删除旧的 ROM/PKG
        for old in drive_root.iterdir():
            if old.suffix.lower() in (".rom", ".pkg"):
                old.unlink()
                log_fn(f"  移除旧文件: {old.name}")

        shutil.copy2(rom_path, drive_root / Path(rom_path).name)
        log_fn(f"  已复制: {Path(rom_path).name}")
        shutil.copy2(pkg_path, drive_root / Path(pkg_path).name)
        log_fn(f"  已复制: {Path(pkg_path).name}")
        return True
    except Exception as e:
        log_fn(f"  复制失败: {e}")
        return False


def eject_usb(drive: str, log_fn=print) -> bool:
    """安全弹出 U 盘（PowerShell）"""
    letter = drive.rstrip("\\").rstrip("/")
    script = f"""
$vol = Get-WmiObject -Class Win32_Volume -Filter "DriveLetter='{letter}'"
$vol.DriveLetter = $null
$vol.Put()
(New-Object -ComObject Shell.Application).Namespace(17).ParseName('{letter}').InvokeVerb('Eject')
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            log_fn(f"  U盘已安全弹出: {drive}")
            return True
        else:
            log_fn(f"  弹出失败（可忽略，手动拔出即可）: {result.stderr.strip()}")
            return False
    except Exception as e:
        log_fn(f"  弹出异常: {e}")
        return False


def format_usb(drive: str, log_fn=print) -> bool:
    """格式化 U 盘为 FAT32（危险操作，需确认后调用）"""
    letter = drive.rstrip("\\:/")
    script = f"format {letter}: /FS:FAT32 /Q /Y"
    try:
        log_fn(f"  正在格式化 {drive} ...")
        result = subprocess.run(
            script, shell=True, capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            log_fn("  格式化完成")
            return True
        else:
            log_fn(f"  格式化失败: {result.stderr}")
            return False
    except Exception as e:
        log_fn(f"  格式化异常: {e}")
        return False


# ── Excel 操作 ────────────────────────────────────────────────────────────────

def load_excel(path: str):
    if not Path(path).exists():
        raise FileNotFoundError(f"找不到 Excel 文件: {path}")
    return openpyxl.load_workbook(path)


def find_or_create_row(ws, model: str, version: str) -> int:
    """
    在表格中查找匹配 型号+版本号 的行，
    找到返回行号，找不到在最后追加一行返回新行号。
    型号在 B 列（col=2），版本号在 F 列（col=6），数据从第3行起。
    """
    for row in ws.iter_rows(min_row=EXCEL_HEADER_ROW + 1, max_row=ws.max_row):
        b_val = str(row[1].value or "").strip()   # B列 型号
        f_val = str(row[5].value or "").strip()   # F列 版本号
        if b_val.upper() == model.upper() and f_val.upper() == version.upper():
            return row[0].row
    # 追加
    new_row = ws.max_row + 1
    return new_row


def write_excel_record(excel_path: str, sheet_name: str,
                       model: str, version: str, remark: str = "待确认",
                       rom_path: str = "", logo: str = "",
                       language: str = "", salesman: str = "",
                       log_fn=print):
    """
    在 Excel 表格写入/更新一行记录。
    列顺序（第2行表头）：序号 型号 logo 业务员 语言 版本号 完成日期 附图 备注

    文件被 WPS/Excel 占用时，先保存为临时文件再替换原文件。
    """
    excel_path = Path(excel_path)

    # 检查文件是否被占用（尝试独占打开）
    def _is_locked(p: Path) -> bool:
        try:
            with open(p, "r+b"):
                return False
        except (IOError, PermissionError):
            return True

    if _is_locked(excel_path):
        log_fn("  ⚠ Excel 文件被 WPS/Excel 占用，将保存为备用文件，请手动合并或关闭后重试")
        tmp_path = excel_path.with_name(excel_path.stem + "_刷机记录_待导入.xlsx")
        _do_write(str(tmp_path), sheet_name, model, version, remark, rom_path, log_fn,
                  logo=logo, language=language, salesman=salesman, is_tmp=True)
        return False

    return _do_write(str(excel_path), sheet_name, model, version, remark, rom_path, log_fn,
                     logo=logo, language=language, salesman=salesman)


def _do_write(excel_path: str, sheet_name: str,
              model: str, version: str, remark: str, rom_path: str, log_fn,
              logo: str = "", language: str = "", salesman: str = "",
              is_tmp=False):
    try:
        p = Path(excel_path)
        if p.exists():
            wb = openpyxl.load_workbook(excel_path)
        else:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = sheet_name
            ws.append(["现有摩众手控UI明细"])
            ws.append(["序号", "型号", "logo", "业务员", "语言", "版本号", "完成日期", "附图", "备注"])

        ws = wb[sheet_name] if sheet_name in wb.sheetnames else wb.active
        row_num = find_or_create_row(ws, model, version)

        # 完成日期：优先用 ROM 文件的最后修改时间，否则用今天
        if rom_path and Path(rom_path).exists():
            mtime = Path(rom_path).stat().st_mtime
            date_str = datetime.fromtimestamp(mtime).strftime("%Y.%m.%d")
        else:
            date_str = datetime.now().strftime("%Y.%m.%d")

        yellow = PatternFill("solid", fgColor="FFFF99")
        green  = PatternFill("solid", fgColor="C6EFCE")

        ws.cell(row=row_num, column=2, value=model)
        if logo:
            ws.cell(row=row_num, column=3, value=logo)
        if salesman:
            ws.cell(row=row_num, column=4, value=salesman)
        if language:
            ws.cell(row=row_num, column=5, value=language)
        ws.cell(row=row_num, column=6, value=version)
        ws.cell(row=row_num, column=7, value=date_str)
        ws.cell(row=row_num, column=9, value=remark)

        fill = yellow if remark == "待确认" else (green if remark == "测试通过" else PatternFill())
        for col in range(1, 10):
            ws.cell(row=row_num, column=col).fill = fill

        wb.save(excel_path)
        label = "（备用文件）" if is_tmp else ""
        log_fn(f"  Excel 已写入{label}: 第{row_num}行  {model} {version}  {date_str}  [{remark}]")
        if is_tmp:
            log_fn(f"  备用文件路径: {excel_path}")
        return True
    except Exception as e:
        log_fn(f"  Excel 写入失败: {e}")
        return False


# ── Excel 全量读取（供预览用）─────────────────────────────────────────────────

def read_all_excel_rows(excel_path: str, sheet_name: str) -> list[list]:
    """读取表格数据行（跳过前两行标题），返回 list of list"""
    rows = []
    p = Path(excel_path)
    if not p.exists():
        return rows
    try:
        wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
        ws = wb[sheet_name] if sheet_name in wb.sheetnames else wb.active
        for row in ws.iter_rows(min_row=EXCEL_HEADER_ROW + 1, max_row=ws.max_row, values_only=True):
            if any(v is not None for v in row):
                rows.append([str(v or "") for v in row])
        wb.close()
    except Exception:
        pass
    return rows


# ── GUI ──────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("手控 UI 刷机工具")
        self.geometry("1100x740")
        self.resizable(True, True)

        self.root_dir   = tk.StringVar(value=DEFAULT_ROOT)
        self.excel_path = tk.StringVar(value=DEFAULT_EXCEL)
        self.usb_drive  = tk.StringVar(value="")
        self.folders: list[dict] = []
        self.current_idx = tk.IntVar(value=-1)

        # 审核字段
        self.field_logo     = tk.StringVar()
        self.field_language = tk.StringVar()
        self.field_salesman = tk.StringVar()
        self.field_remark   = tk.StringVar()

        self._build_ui()
        self._refresh_usb()


    # ── 布局 ─────────────────────────────────────────────────────────────────

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
        ttk.Button(left, text="刷新预览", command=self._refresh_preview).pack(fill="x", padx=4, pady=(0, 2))
        self.listbox = tk.Listbox(left, selectmode="browse", font=("Consolas", 9), activestyle="dotbox")
        sb = ttk.Scrollbar(left, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=2)
        sb.pack(side="right", fill="y", pady=2)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        legend = ttk.Frame(left)
        legend.pack(fill="x", padx=4, pady=2)
        for color, lbl in [("#FFFF99", "待确认"), ("#C6EFCE", "测试通过"), ("white", "未操作")]:
            tk.Frame(legend, bg=color, width=12, height=12, relief="solid", bd=1).pack(side="left", padx=(4, 1))
            ttk.Label(legend, text=lbl).pack(side="left", padx=(0, 8))

        right_nb = ttk.Notebook(main_area, width=310)
        right_nb.pack(side="right", fill="both")
        tab_flash  = ttk.Frame(right_nb)
        tab_review = ttk.Frame(right_nb)
        right_nb.add(tab_flash,  text="  刷机操作  ")
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
        psb_y = ttk.Scrollbar(prev_frame, orient="vertical",   command=self.preview.yview)
        psb_x = ttk.Scrollbar(prev_frame, orient="horizontal", command=self.preview.xview)
        self.preview.configure(yscrollcommand=psb_y.set, xscrollcommand=psb_x.set)
        self.preview.grid(row=0, column=0, sticky="nsew")
        psb_y.grid(row=0, column=1, sticky="ns")
        psb_x.grid(row=1, column=0, sticky="ew")
        prev_frame.columnconfigure(0, weight=1)
        prev_frame.rowconfigure(0, weight=1)
        self.preview.tag_configure("待确认",  background="#FFFF99")
        self.preview.tag_configure("测试通过", background="#C6EFCE")
        bottom.add(prev_frame, weight=2)

        btn_bar = ttk.Frame(self)
        btn_bar.pack(fill="x", padx=6, pady=(0, 4))
        ttk.Button(btn_bar, text="刷新预览", command=self._refresh_preview).pack(side="left")
        ttk.Button(btn_bar, text="清空日志", command=self._clear_log).pack(side="right")

    def _build_flash_tab(self, parent):
        pad = dict(padx=8, pady=2)
        btn = dict(fill="x", **pad)
        self.lbl_model = ttk.Label(parent, text="型号：-", font=("", 10, "bold"))
        self.lbl_ver   = ttk.Label(parent, text="版本：-")
        self.lbl_rom   = ttk.Label(parent, text="ROM：-", wraplength=270)
        self.lbl_pkg   = ttk.Label(parent, text="PKG：-")
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
        ttk.Button(parent, text="1  清理 U 盘垃圾文件",   command=self._clean_usb).pack(**btn)
        ttk.Button(parent, text="2  格式化 U 盘 (FAT32)", command=self._format_usb).pack(**btn)
        ttk.Button(parent, text="3  复制文件到 U 盘",     command=self._copy_to_usb).pack(**btn)
        ttk.Button(parent, text="4  安全弹出 U 盘",       command=self._eject_usb).pack(**btn)
        ttk.Separator(parent).pack(fill="x", padx=4, pady=4)
        ttk.Button(parent, text="5  写入记录（待确认）",
                   command=lambda: self._write_excel("待确认")).pack(**btn)
        ttk.Button(parent, text="   标记为【测试通过】",
                   command=lambda: self._write_excel("测试通过")).pack(**btn)
        ttk.Separator(parent).pack(fill="x", padx=4, pady=4)
        ttk.Button(parent, text="★ 一键执行（清理→复制→弹出→写表）",
                   command=self._one_click).pack(**btn)
        ttk.Separator(parent).pack(fill="x", padx=4, pady=4)
        ttk.Button(parent, text="下一个  ▶", command=self._next_folder).pack(**btn)

    def _build_review_tab(self, parent):
        pad = dict(padx=8, pady=4)
        ttk.Label(parent, text="选中列表项后填写详情，点【保存】直接写入 Excel。",
                  foreground="gray").pack(anchor="w", **pad)
        ttk.Separator(parent).pack(fill="x", padx=4, pady=2)
        fields = [
            ("Logo / 品牌:", self.field_logo,     ["中性", "通用", "定制"]),
            ("语言:",        self.field_language,  ["中、英、越", "中、英", "英文", "希伯来语、俄、英"]),
            ("业务员:",      self.field_salesman,  []),
        ]
        for label, var, opts in fields:
            row = ttk.Frame(parent)
            row.pack(fill="x", **pad)
            ttk.Label(row, text=label, width=12, anchor="e").pack(side="left")
            if opts:
                ttk.Combobox(row, textvariable=var, values=opts, width=20).pack(
                    side="left", padx=4, fill="x", expand=True)
            else:
                ttk.Entry(row, textvariable=var, width=22).pack(side="left", padx=4, fill="x", expand=True)
        ttk.Label(parent, text="备注:").pack(anchor="w", padx=8)
        self.remark_text = tk.Text(parent, height=4, width=28, font=("", 9))
        self.remark_text.pack(fill="x", padx=8, pady=2)
        ttk.Separator(parent).pack(fill="x", padx=4, pady=6)
        status_row = ttk.Frame(parent)
        status_row.pack(fill="x", padx=8)
        ttk.Label(status_row, text="测试状态:").pack(side="left")
        self.review_status = ttk.Combobox(
            status_row, values=["待确认", "测试通过", "测试失败"], width=10, state="readonly")
        self.review_status.set("测试通过")
        self.review_status.pack(side="left", padx=4)
        ttk.Button(parent, text="保存到 Excel", command=self._save_review).pack(fill="x", padx=8, pady=8)
        ttk.Label(parent, text="下拉框可直接输入自定义值",
                  foreground="gray", font=("", 8)).pack(anchor="w", padx=8)

    # ── 辅助 ─────────────────────────────────────────────────────────────────

    def log(self, msg: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _browse_root(self):
        d = filedialog.askdirectory(initialdir=self.root_dir.get())
        if d:
            self.root_dir.set(d)

    def _browse_excel(self):
        f = filedialog.askopenfilename(
            initialdir=str(Path(self.excel_path.get()).parent),
            filetypes=[("Excel", "*.xlsx *.xls"), ("All", "*.*")]
        )
        if f:
            self.excel_path.set(f)

    def _refresh_usb(self):
        drives = get_usb_drives()
        self.usb_combo["values"] = drives
        if drives:
            self.usb_drive.set(drives[0])
            self.log(f"检测到 U 盘: {', '.join(drives)}")
        else:
            self.usb_drive.set("")

    def _scan(self):
        self.listbox.delete(0, "end")
        self.folders = []
        root = self.root_dir.get()
        if not root:
            messagebox.showwarning("提示", "请先选择程序根目录")
            return
        self.log(f"扫描中: {root}")
        self.folders = find_handcontrol_folders(root)
        status_map = self._load_excel_status()
        for i, f in enumerate(self.folders):
            self.listbox.insert("end", f["label"])
            key = (f["model"].upper(), f["version"].upper())
            status = status_map.get(key, "")
            if status == "待确认":
                self.listbox.itemconfig(i, bg="#FFFF99", fg="black")
            elif status == "测试通过":
                self.listbox.itemconfig(i, bg="#C6EFCE", fg="black")
        tested  = sum(1 for v in status_map.values() if v == "测试通过")
        pending = sum(1 for v in status_map.values() if v == "待确认")
        self.log(f"共找到 {len(self.folders)} 个手控文件夹（已测: {tested}，待确认: {pending}）")
        self._refresh_preview()

    def _load_excel_status(self) -> dict:
        result = {}
        excel = self.excel_path.get()
        if not excel or not Path(excel).exists():
            return result
        try:
            wb = openpyxl.load_workbook(excel, read_only=True, data_only=True)
            ws = wb[EXCEL_SHEET] if EXCEL_SHEET in wb.sheetnames else wb.active
            for row in ws.iter_rows(min_row=EXCEL_HEADER_ROW + 1, max_row=ws.max_row, values_only=True):
                if len(row) >= 9:
                    m = str(row[1] or "").strip().upper()
                    v = str(row[5] or "").strip().upper()
                    r = str(row[8] or "").strip()
                    if m and v:
                        result[(m, v)] = r
            wb.close()
        except Exception as e:
            self.log(f"  读取Excel状态失败: {e}")
        return result

    def _load_excel_row(self, model: str, version: str) -> dict:
        excel = self.excel_path.get()
        if not excel or not Path(excel).exists():
            return {}
        try:
            wb = openpyxl.load_workbook(excel, read_only=True, data_only=True)
            ws = wb[EXCEL_SHEET] if EXCEL_SHEET in wb.sheetnames else wb.active
            for row in ws.iter_rows(min_row=EXCEL_HEADER_ROW + 1, max_row=ws.max_row, values_only=True):
                if (str(row[1] or "").strip().upper() == model.upper() and
                        str(row[5] or "").strip().upper() == version.upper()):
                    wb.close()
                    return {
                        "logo":     str(row[2] or ""),
                        "salesman": str(row[3] or ""),
                        "language": str(row[4] or ""),
                        "remark":   str(row[8] or ""),
                    }
            wb.close()
        except Exception:
            pass
        return {}

    def _refresh_preview(self):
        for row in self.preview.get_children():
            self.preview.delete(row)
        rows = read_all_excel_rows(self.excel_path.get(), EXCEL_SHEET)
        for r in rows:
            if len(r) >= 9:
                display = [r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[8]]
                remark = r[8]
            else:
                display = r[:8]
                remark = ""
            tag = "待确认" if remark == "待确认" else ("测试通过" if remark == "测试通过" else "")
            self.preview.insert("", "end", values=display, tags=(tag,))

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
        existing = self._load_excel_row(info["model"], info["version"])
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

    # ── 刷机操作 ─────────────────────────────────────────────────────────────

    def _clean_usb(self):
        drive = self.usb_drive.get()
        if not drive:
            messagebox.showwarning("提示", "未检测到 U 盘，请插入后点击刷新")
            return
        self.log(f"清理 U 盘 {drive} ...")
        n = clean_usb(drive, self.log)
        self.log(f"  清理完成，删除 {n} 个垃圾文件")

    def _format_usb(self):
        drive = self.usb_drive.get()
        if not drive:
            messagebox.showwarning("提示", "未检测到 U 盘")
            return
        if not messagebox.askyesno("确认", f"将格式化 {drive}，所有数据会丢失，确认吗？"):
            return
        self.log(f"格式化 {drive} ...")
        ok = format_usb(drive, self.log)
        self.log("格式化成功" if ok else "格式化失败，请手动格式化")

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
        self.log(f"复制文件到 {drive} ...")
        ok = copy_to_usb(rom, pkg, drive, self.log)
        if ok:
            self.log("复制完成")

    def _eject_usb(self):
        drive = self.usb_drive.get()
        if not drive:
            messagebox.showwarning("提示", "未检测到 U 盘")
            return
        self.log(f"弹出 {drive} ...")
        eject_usb(drive, self.log)

    def _write_excel(self, remark: str):
        info = self._current_info()
        if not info:
            return
        excel = self.excel_path.get()
        rom_path = str(Path(info["path"]) / info["rom_file"])
        self.log(f"写入 Excel: {info['model']} {info['version']}  [{remark}]")
        ok = write_excel_record(excel, EXCEL_SHEET, info["model"], info["version"],
                                remark=remark, rom_path=rom_path, log_fn=self.log)
        if ok:
            self._update_listbox_color(self.current_idx.get(), remark)
            self._refresh_preview()
        if not ok:
            tmp = str(Path(excel).with_name(Path(excel).stem + "_刷机记录_待导入.xlsx"))
            messagebox.showwarning(
                "Excel 被占用",
                f"表格被 WPS/Excel 占用，无法直接写入。\n\n"
                f"已将记录保存到备用文件：\n{tmp}\n\n"
                f"解决方法：\n"
                f"① 关闭 WPS/Excel 后再点一次写入按钮\n"
                f"② 或打开备用文件，手动复制该行到主表"
            )

    def _one_click(self):
        info = self._current_info()
        if not info:
            return
        drive = self.usb_drive.get()
        if not drive:
            messagebox.showwarning("提示", "未检测到 U 盘，请插入后点击刷新")
            return
        self.log("=" * 50)
        self.log(f"一键执行: {info['model']} {info['version']}")
        n = clean_usb(drive, self.log)
        self.log(f"  清理完成，删除 {n} 个垃圾文件")
        rom = str(Path(info["path"]) / info["rom_file"])
        pkg = str(Path(info["path"]) / info["pkg_file"])
        ok = copy_to_usb(rom, pkg, drive, self.log)
        if not ok:
            self.log("复制失败，流程中止")
            return
        eject_usb(drive, self.log)
        excel_ok = write_excel_record(
            self.excel_path.get(), EXCEL_SHEET,
            info["model"], info["version"],
            remark="待确认", rom_path=rom, log_fn=self.log
        )
        if excel_ok:
            self._update_listbox_color(self.current_idx.get(), "待确认")
            self._refresh_preview()
        self.log("一键完成！请插入手控器测试 ✓")
        if not excel_ok:
            excel = self.excel_path.get()
            tmp = str(Path(excel).with_name(Path(excel).stem + "_刷机记录_待导入.xlsx"))
            messagebox.showwarning(
                "Excel 被占用",
                f"U盘已准备好，但 Excel 写入失败（文件被占用）。\n\n"
                f"记录已暂存到：\n{tmp}\n\n"
                f"关闭 WPS/Excel 后，点【写入记录】补录即可。"
            )
        self.log("=" * 50)

    # ── 审核保存 ─────────────────────────────────────────────────────────────

    def _save_review(self):
        info = self._current_info()
        if not info:
            return
        excel    = self.excel_path.get()
        logo     = self.field_logo.get().strip()
        language = self.field_language.get().strip()
        salesman = self.field_salesman.get().strip()
        remark   = self.remark_text.get("1.0", "end").strip()
        status   = self.review_status.get()
        final_remark = status if not remark or remark == status else f"{status}  |  {remark}"
        rom_path = str(Path(info["path"]) / info["rom_file"])
        self.log(f"审核保存: {info['model']} {info['version']}  logo={logo}  语言={language}  [{status}]")
        ok = write_excel_record(
            excel, EXCEL_SHEET, info["model"], info["version"],
            remark=final_remark, rom_path=rom_path,
            logo=logo, language=language, salesman=salesman,
            log_fn=self.log
        )
        if ok:
            self._update_listbox_color(self.current_idx.get(), status)
            self._refresh_preview()
            self.log("  保存成功 ✓")
        else:
            tmp = str(Path(excel).with_name(Path(excel).stem + "_刷机记录_待导入.xlsx"))
            messagebox.showwarning("Excel 被占用",
                                   f"请关闭 WPS/Excel 后重试。\n已暂存到：\n{tmp}")

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


# ── 入口 ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()

