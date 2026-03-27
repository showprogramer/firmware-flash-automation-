from handcontrol.core.excel_ops import load_excel_status
from handcontrol.core.file_scan import find_handcontrol_folders


def build_scan_result(root: str, excel_path: str, sheet_name: str, log_fn=print) -> dict:
    try:
        log_fn(f"扫描中: {root}")
        folders = find_handcontrol_folders(root)
        status_map = load_excel_status(excel_path, sheet_name)
        tested = sum(1 for v in status_map.values() if v == "测试通过")
        pending = sum(1 for v in status_map.values() if v == "待确认")
        return {
            "ok": True,
            "code": "ok",
            "message": "扫描完成",
            "payload": {
                "folders": folders,
                "status_map": status_map,
                "tested": tested,
                "pending": pending,
            },
        }
    except Exception as e:
        return {
            "ok": False,
            "code": "scan_failed",
            "message": str(e),
            "payload": {
                "folders": [],
                "status_map": {},
                "tested": 0,
                "pending": 0,
            },
        }

