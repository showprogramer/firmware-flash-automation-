from fwasset.core.file_scan import find_handcontrol_folders, scan_firmware_assets


def build_scan_result(root: str, log_fn=print) -> dict:
    try:
        log_fn(f"扫描中: {root}")
        assets, errors = scan_firmware_assets(root)
        folders = find_handcontrol_folders(root)
        message = "扫描完成"
        if errors:
            message = f"扫描完成（{len(errors)} 个目录读取失败）"
        return {
            "ok": True,
            "code": "ok",
            "message": message,
            "payload": {
                "assets": assets,
                "folders": folders,
                "errors": errors,
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "code": "scan_failed",
            "message": str(exc),
            "payload": {
                "assets": [],
                "folders": [],
                "errors": [],
            },
        }
