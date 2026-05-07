from fwasset.core.asset_index import AssetIndexError, load_assets, load_scan_meta, save_assets
from fwasset.core.file_scan import find_handcontrol_folders, scan_firmware_assets


def build_scan_result(root: str, log_fn=print) -> dict:
    try:
        log_fn(f"扫描中: {root}")
        assets, errors = scan_firmware_assets(root)
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
        assets = load_assets()
        meta = load_scan_meta()
        if not assets:
            return {
                "ok": True,
                "code": "index_empty",
                "message": "本地资产索引为空，请首次扫描根目录",
                "payload": {
                    "assets": [],
                    "folders": [],
                    "errors": [],
                    "scan_meta": meta,
                },
            }

        log_fn(f"从本地资产索引读取 {len(assets)} 个程序条目")
        return {
            "ok": True,
            "code": "ok",
            "message": "已读取本地资产索引",
            "payload": {
                "assets": assets,
                "folders": _handcontrol_folders_from_assets(assets),
                "errors": [],
                "scan_meta": meta,
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


def _handcontrol_folders_from_assets(assets: list[dict]) -> list[dict]:
    folders = []
    for asset in assets:
        if asset.get("firmware_type") != "handcontrol_ui":
            continue
        files = list(asset.get("files", []))
        folders.append(
            {
                "path": asset.get("path", ""),
                "rom_file": next((name for name in files if str(name).lower().endswith(".rom")), ""),
                "pkg_file": next((name for name in files if str(name).lower().endswith(".pkg")), ""),
                "model": asset.get("model", ""),
                "version": asset.get("version", ""),
                "label": asset.get("label", ""),
            }
        )
    return folders
