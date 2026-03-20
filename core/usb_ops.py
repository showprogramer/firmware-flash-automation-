import shutil
import subprocess
from pathlib import Path

import psutil

from core.settings import JUNK_EXTENSIONS, JUNK_FILENAMES


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
