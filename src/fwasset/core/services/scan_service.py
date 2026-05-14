import threading

from fwasset.core.asset_index import AssetIndexError, count_assets, load_scan_meta, save_assets
from fwasset.core.file_scan import find_handcontrol_folders, scan_firmware_assets


def build_scan_result(
    root: str,
    log_fn=print,
    cancel_event: threading.Event | None = None,
) -> dict:
    try:
        log_fn(f"扫描中: {root}")
        assets, errors = scan_firmware_assets(
            root,
            cancel_event=cancel_event,
        )

        if cancel_event is not None and cancel_event.is_set():
            return {
                "ok": True,
                "code": "cancelled",
                "message": "扫描已被用户取消",
                "payload": {"assets": [], "folders": [], "errors": errors},
            }

        folders = find_handcontrol_folders(root)
        save_assets(assets, root)
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


def build_cached_scan_result(log_fn=print) -> dict:
    try:
        asset_count = count_assets()
        meta = load_scan_meta()
        if not asset_count:
            return {
                "ok": True,
                "code": "index_empty",
                "message": "本地资产索引为空，请首次扫描根目录",
                "payload": {
                    "assets": [],
                    "folders": [],
                    "errors": [],
                    "scan_meta": meta,
                    "asset_count": 0,
                },
            }

        log_fn(f"本地资产索引已有 {asset_count} 个程序条目")
        return {
            "ok": True,
            "code": "ok",
            "message": "已读取本地资产索引状态",
            "payload": {
                "assets": [],
                "folders": [],
                "errors": [],
                "scan_meta": meta,
                "asset_count": asset_count,
            },
        }
    except AssetIndexError as exc:
        return {
            "ok": False,
            "code": "index_unavailable",
            "message": str(exc),
            "payload": {
                "assets": [],
                "folders": [],
                "errors": [str(exc)],
                "scan_meta": [],
            },
        }
