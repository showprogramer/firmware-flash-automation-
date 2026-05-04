from handcontrol.core.usb_ops import clean_usb, copy_to_usb, eject_usb


def run_one_click(
    drive: str,
    model: str,
    version: str,
    rom_path: str,
    pkg_path: str,
    log_fn=print,
) -> dict:
    try:
        log_fn("=" * 50)
        log_fn(f"一键执行: {model} {version}")
        removed = clean_usb(drive, log_fn)
        log_fn(f"  清理完成，删除 {removed} 个垃圾文件")

        copied = copy_to_usb(rom_path, pkg_path, drive, log_fn)
        if not copied:
            log_fn("复制失败，流程中止")
            return {
                "ok": False,
                "code": "copy_failed",
                "message": "复制失败",
                "payload": {
                    "copy_ok": False,
                    "removed_count": removed,
                    "ejected": False,
                },
            }

        ejected = bool(eject_usb(drive, log_fn))
        return {
            "ok": True,
            "code": "ok",
            "message": "一键执行完成",
            "payload": {
                "copy_ok": True,
                "removed_count": removed,
                "ejected": ejected,
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "code": "service_exception",
            "message": str(exc),
            "payload": {
                "copy_ok": False,
                "removed_count": 0,
                "ejected": False,
            },
        }
