import shutil
import subprocess
from pathlib import Path

import psutil

from core.settings import JUNK_EXTENSIONS, JUNK_FILENAMES


_PERMISSION_HINTS = [
    "access is denied",
    "requires elevation",
    "administrator",
    "拒绝访问",
    "需要提升",
]


def _extract_drive_letter(drive: str) -> str:
    text = str(drive or "").strip()
    if not text:
        return ""
    if len(text) >= 2 and text[1] == ":":
        return text[0].upper()
    p = Path(text)
    anchor = str(p.anchor)
    if len(anchor) >= 2 and anchor[1] == ":":
        return anchor[0].upper()
    return text[0].upper()


def _looks_like_permission_denied(text: str) -> bool:
    lower_text = (text or "").lower()
    return any(hint in lower_text for hint in _PERMISSION_HINTS)


def get_usb_drives() -> list[str]:
    """Return removable USB drive mountpoints, e.g. ['E:\\', 'F:\\']."""
    drives = []
    for part in psutil.disk_partitions(all=False):
        if "removable" in part.opts.lower() or part.fstype.upper() in ("FAT32", "FAT", "EXFAT"):
            drives.append(part.mountpoint)
    return drives


def clean_usb(drive: str, log_fn=print) -> int:
    """Delete junk files at USB root and return removed count."""
    removed = 0
    root = Path(drive)
    for f in root.iterdir():
        if f.is_file() and (f.suffix.lower() in JUNK_EXTENSIONS or f.name.lower() in JUNK_FILENAMES):
            try:
                f.unlink()
                log_fn(f"  删除垃圾文件: {f.name}")
                removed += 1
            except Exception as e:
                log_fn(f"  删除失败 {f.name}: {e}")
    return removed


def copy_to_usb(rom_path: str, pkg_path: str, drive: str, log_fn=print) -> bool:
    """Copy ROM and PKG to USB root, replacing existing ROM/PKG files first."""
    drive_root = Path(drive)
    try:
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


def diagnose_usb_health(drive: str, log_fn=print) -> dict:
    """Lightweight drive health check when USB is inserted."""
    root = Path(drive)
    if not root.exists():
        msg = f"盘符不存在或不可访问: {drive}"
        log_fn(f"  {msg}")
        return {"ok": False, "code": "drive_unavailable", "message": msg, "payload": {"drive": drive}}

    try:
        _ = next(root.iterdir(), None)
    except Exception as e:
        msg = f"盘符目录不可读取: {e}"
        log_fn(f"  {msg}")
        return {"ok": False, "code": "io_unavailable", "message": msg, "payload": {"drive": drive}}

    letter = _extract_drive_letter(drive)
    target = f"{letter}:" if letter else str(drive)
    try:
        result = subprocess.run(
            ["cmd", "/c", "vol", target],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if result.returncode == 0:
            return {
                "ok": True,
                "code": "ok",
                "message": "U盘健康检查通过",
                "payload": {"drive": drive, "volume_target": target},
            }
        msg = (result.stderr or result.stdout or "vol 命令失败").strip()
        log_fn(f"  U盘卷信息检查失败: {msg}")
        return {"ok": False, "code": "volume_check_failed", "message": msg, "payload": {"drive": drive}}
    except subprocess.TimeoutExpired:
        msg = "U盘卷信息检查超时"
        log_fn(f"  {msg}")
        return {"ok": False, "code": "check_timeout", "message": msg, "payload": {"drive": drive}}
    except Exception as e:
        msg = f"U盘健康检查异常: {e}"
        log_fn(f"  {msg}")
        return {"ok": False, "code": "check_error", "message": msg, "payload": {"drive": drive}}


def repair_usb_driver(drive: str, log_fn=print) -> dict:
    """Repair USB using built-in Windows tools: chkdsk + pnputil scan-devices."""
    letter = _extract_drive_letter(drive)
    target = f"{letter}:" if letter else str(drive)

    try:
        log_fn(f"  执行修复: chkdsk {target} /f")
        chkdsk_result = subprocess.run(
            ["chkdsk", target, "/f"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        msg = "系统缺少 chkdsk 命令"
        log_fn(f"  {msg}")
        return {"ok": False, "code": "tool_missing", "message": msg, "payload": {"drive": drive}}
    except subprocess.TimeoutExpired:
        msg = "chkdsk 执行超时"
        log_fn(f"  {msg}")
        return {"ok": False, "code": "chkdsk_timeout", "message": msg, "payload": {"drive": drive}}
    except Exception as e:
        msg = f"chkdsk 执行异常: {e}"
        log_fn(f"  {msg}")
        return {"ok": False, "code": "chkdsk_error", "message": msg, "payload": {"drive": drive}}

    chkdsk_text = (chkdsk_result.stdout or "") + "\n" + (chkdsk_result.stderr or "")
    if chkdsk_result.returncode != 0:
        if _looks_like_permission_denied(chkdsk_text):
            msg = "权限不足，请以管理员权限运行后重试"
            log_fn(f"  {msg}")
            return {"ok": False, "code": "permission_denied", "message": msg, "payload": {"drive": drive}}
        msg = (chkdsk_result.stderr or chkdsk_result.stdout or "chkdsk 执行失败").strip()
        log_fn(f"  chkdsk 失败: {msg}")
        return {"ok": False, "code": "chkdsk_failed", "message": msg, "payload": {"drive": drive}}

    try:
        log_fn("  执行设备重扫描: pnputil /scan-devices")
        scan_result = subprocess.run(
            ["pnputil", "/scan-devices"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        msg = "系统缺少 pnputil 命令"
        log_fn(f"  {msg}")
        return {"ok": False, "code": "tool_missing", "message": msg, "payload": {"drive": drive}}
    except subprocess.TimeoutExpired:
        msg = "pnputil 扫描超时"
        log_fn(f"  {msg}")
        return {"ok": False, "code": "scan_timeout", "message": msg, "payload": {"drive": drive}}
    except Exception as e:
        msg = f"pnputil 扫描异常: {e}"
        log_fn(f"  {msg}")
        return {"ok": False, "code": "scan_error", "message": msg, "payload": {"drive": drive}}

    scan_text = (scan_result.stdout or "") + "\n" + (scan_result.stderr or "")
    if scan_result.returncode != 0:
        if _looks_like_permission_denied(scan_text):
            msg = "权限不足，请以管理员权限运行后重试"
            log_fn(f"  {msg}")
            return {"ok": False, "code": "permission_denied", "message": msg, "payload": {"drive": drive}}
        msg = (scan_result.stderr or scan_result.stdout or "pnputil 扫描失败").strip()
        log_fn(f"  pnputil 扫描失败: {msg}")
        return {"ok": False, "code": "scan_failed", "message": msg, "payload": {"drive": drive}}

    return {
        "ok": True,
        "code": "ok",
        "message": "U盘驱动修复完成",
        "payload": {
            "drive": drive,
            "chkdsk_output": (chkdsk_result.stdout or "").strip(),
            "scan_output": (scan_result.stdout or "").strip(),
        },
    }


def eject_usb(drive: str, log_fn=print) -> bool:
    """Safely eject USB using PowerShell."""
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
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            log_fn(f"  U盘已安全弹出: {drive}")
            return True
        log_fn(f"  弹出失败（可忽略，手动拔出即可）: {result.stderr.strip()}")
        return False
    except Exception as e:
        log_fn(f"  弹出异常: {e}")
        return False


def format_usb(drive: str, log_fn=print) -> bool:
    """Format USB to FAT32 (dangerous operation, call after explicit confirmation)."""
    letter = drive.rstrip("\\:/")
    script = f"format {letter}: /FS:FAT32 /Q /Y"
    try:
        log_fn(f"  正在格式化 {drive} ...")
        result = subprocess.run(script, shell=True, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            log_fn("  格式化完成")
            return True
        log_fn(f"  格式化失败: {result.stderr}")
        return False
    except Exception as e:
        log_fn(f"  格式化异常: {e}")
        return False
