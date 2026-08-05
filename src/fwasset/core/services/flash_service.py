from collections.abc import Callable

from fwasset.core.usb_ops import copy_to_usb, eject_usb, format_usb


def run_one_click(
    drive: str,
    model: str,
    version: str,
    rom_path: str,
    pkg_path: str,
    log_fn: Callable[..., None] = print,
) -> dict:
    try:
        log_fn("=" * 50)
        log_fn(f"一键执行: {model} {version}")

        formatted = format_usb(drive, log_fn)
        if not formatted:
            log_fn("格式化失败，流程中止")
            return {
                "ok": False,
                "code": "format_failed",
                "message": "格式化失败",
                "payload": {
                    "format_ok": False,
                    "copy_ok": False,
                    "ejected": False,
                },
            }

        copied = copy_to_usb(rom_path, pkg_path, drive, log_fn)
        if not copied:
            log_fn("复制失败，流程中止")
            return {
                "ok": False,
                "code": "copy_failed",
                "message": "复制失败",
                "payload": {
                    "format_ok": True,
                    "copy_ok": False,
                    "ejected": False,
                },
            }

        ejected = bool(eject_usb(drive, log_fn))
        return {
            "ok": True,
            "code": "ok",
            "message": "一键执行完成",
            "payload": {
                "format_ok": True,
                "copy_ok": True,
                "ejected": ejected,
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "code": "service_exception",
            "message": str(exc),
            "payload": {
                "format_ok": False,
                "copy_ok": False,
                "ejected": False,
            },
        }
