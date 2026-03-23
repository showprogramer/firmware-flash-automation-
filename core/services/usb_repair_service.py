from core.usb_ops import diagnose_usb_health, repair_usb_driver


def diagnose_drive(drive: str, log_fn=print) -> dict:
    try:
        result = diagnose_usb_health(drive, log_fn=log_fn)
        if result.get("ok"):
            return {
                "ok": True,
                "code": "ok",
                "message": "U盘健康检查通过",
                "payload": {"diagnose_result": result},
            }
        return {
            "ok": False,
            "code": str(result.get("code", "unhealthy")),
            "message": str(result.get("message", "U盘健康检查失败")),
            "payload": {"diagnose_result": result},
        }
    except Exception as e:
        return {
            "ok": False,
            "code": "service_exception",
            "message": str(e),
            "payload": {"diagnose_result": None},
        }


def repair_drive(drive: str, log_fn=print) -> dict:
    try:
        result = repair_usb_driver(drive, log_fn=log_fn)
        if result.get("ok"):
            return {
                "ok": True,
                "code": "ok",
                "message": "U盘驱动修复完成",
                "payload": {"repair_result": result},
            }
        return {
            "ok": False,
            "code": str(result.get("code", "repair_failed")),
            "message": str(result.get("message", "U盘驱动修复失败")),
            "payload": {"repair_result": result},
        }
    except Exception as e:
        return {
            "ok": False,
            "code": "service_exception",
            "message": str(e),
            "payload": {"repair_result": None},
        }
