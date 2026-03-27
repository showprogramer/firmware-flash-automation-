from handcontrol.core.excel_ops import write_excel_record
from handcontrol.core.usb_ops import clean_usb, copy_to_usb, eject_usb


def run_one_click(
    drive: str,
    model: str,
    version: str,
    rom_path: str,
    pkg_path: str,
    excel_path: str,
    sheet_name: str,
    logo: str = "",
    language: str = "",
    salesman: str = "",
    attachment: str = "",
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
                    "excel_result": None,
                    "preview_row": {},
                },
            }

        eject_usb(drive, log_fn)
        excel_result = write_excel_record(
            excel_path=excel_path,
            sheet_name=sheet_name,
            model=model,
            version=version,
            remark="待确认",
            rom_path=rom_path,
            logo=logo,
            language=language,
            salesman=salesman,
            attachment=attachment,
            log_fn=log_fn,
        )
        preview_row = {}
        if excel_result.get("ok") and excel_result.get("written_row"):
            wr = excel_result["written_row"]
            preview_row = {
                "serial": "",
                "model": str(wr.get("model", "")),
                "logo": str(wr.get("logo", "")),
                "salesman": str(wr.get("salesman", "")),
                "language": str(wr.get("language", "")),
                "attachment": str(wr.get("attachment", "")),
                "version": str(wr.get("version", "")),
                "date": str(wr.get("date", "")),
                "remark": str(wr.get("remark", "")),
            }

        return {
            "ok": True,
            "code": "ok",
            "message": "一键执行完成",
            "payload": {
                "copy_ok": True,
                "removed_count": removed,
                "excel_result": excel_result,
                "preview_row": preview_row,
            },
        }
    except Exception as e:
        return {
            "ok": False,
            "code": "service_exception",
            "message": str(e),
            "payload": {
                "copy_ok": False,
                "removed_count": 0,
                "excel_result": None,
                "preview_row": {},
            },
        }



