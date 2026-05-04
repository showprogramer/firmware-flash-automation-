from handcontrol.core.file_scan import find_handcontrol_folders


def build_scan_result(root: str, log_fn=print) -> dict:
    try:
        log_fn(f"扫描中: {root}")
        folders = find_handcontrol_folders(root)
        return {
            "ok": True,
            "code": "ok",
            "message": "扫描完成",
            "payload": {
                "folders": folders,
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "code": "scan_failed",
            "message": str(exc),
            "payload": {
                "folders": [],
            },
        }
