from core.excel_ops import delete_excel_row, update_excel_field, write_excel_record


def _to_preview_row(written_row: dict | None) -> dict:
    if not written_row:
        return {}
    return {
        "serial": "",
        "model": str(written_row.get("model", "")),
        "logo": str(written_row.get("logo", "")),
        "salesman": str(written_row.get("salesman", "")),
        "language": str(written_row.get("language", "")),
        "version": str(written_row.get("version", "")),
        "date": str(written_row.get("date", "")),
        "remark": str(written_row.get("remark", "")),
    }


def write_record(
    excel_path: str,
    sheet_name: str,
    model: str,
    version: str,
    remark: str,
    rom_path: str,
    logo: str = "",
    language: str = "",
    salesman: str = "",
    log_fn=print,
) -> dict:
    try:
        result = write_excel_record(
            excel_path=excel_path,
            sheet_name=sheet_name,
            model=model,
            version=version,
            remark=remark,
            rom_path=rom_path,
            logo=logo,
            language=language,
            salesman=salesman,
            log_fn=log_fn,
        )
        if result.get("ok"):
            return {
                "ok": True,
                "code": "ok",
                "message": "写入成功",
                "payload": {
                    "excel_result": result,
                    "preview_row": _to_preview_row(result.get("written_row")),
                },
            }
        reason = str(result.get("reason", "write_failed"))
        return {
            "ok": False,
            "code": reason,
            "message": str(result.get("error", "")) if reason != "locked" else "Excel 被占用",
            "payload": {
                "excel_result": result,
                "preview_row": {},
            },
        }
    except Exception as e:
        return {
            "ok": False,
            "code": "service_exception",
            "message": str(e),
            "payload": {
                "excel_result": None,
                "preview_row": {},
            },
        }


def update_record_fields(
    excel_path: str,
    sheet_name: str,
    model: str,
    version: str,
    logo: str = "",
    salesman: str = "",
    language: str = "",
    remark: str = "",
    log_fn=print,
) -> dict:
    try:
        for field, value in (
            ("logo", logo),
            ("salesman", salesman),
            ("language", language),
            ("remark", remark),
        ):
            result = update_excel_field(
                excel_path=excel_path,
                sheet_name=sheet_name,
                model=model,
                version=version,
                field=field,
                value=value,
                log_fn=log_fn,
            )
            if not result.get("ok"):
                reason = str(result.get("reason", "write_failed"))
                return {
                    "ok": False,
                    "code": reason,
                    "message": str(result.get("error", "")) if reason != "locked" else "Excel 被占用",
                    "payload": {
                        "excel_result": result,
                        "preview_row": {},
                    },
                }

        return {
            "ok": True,
            "code": "ok",
            "message": "保存成功",
            "payload": {
                "excel_result": {
                    "ok": True,
                    "reason": "ok",
                    "error": "",
                },
                "preview_row": {
                    "serial": "",
                    "model": str(model or ""),
                    "logo": str(logo or ""),
                    "salesman": str(salesman or ""),
                    "language": str(language or ""),
                    "version": str(version or ""),
                    "date": "",
                    "remark": str(remark or ""),
                },
            },
        }
    except Exception as e:
        return {
            "ok": False,
            "code": "service_exception",
            "message": str(e),
            "payload": {
                "excel_result": None,
                "preview_row": {},
            },
        }


def delete_record(
    excel_path: str,
    sheet_name: str,
    model: str,
    version: str,
    log_fn=print,
) -> dict:
    try:
        result = delete_excel_row(
            excel_path=excel_path,
            sheet_name=sheet_name,
            model=model,
            version=version,
            log_fn=log_fn,
        )
        if result.get("ok"):
            return {
                "ok": True,
                "code": "ok",
                "message": "删除成功",
                "payload": {
                    "excel_result": result,
                },
            }

        reason = str(result.get("reason", "write_failed"))
        return {
            "ok": False,
            "code": reason,
            "message": str(result.get("error", "")) if reason != "locked" else "Excel 被占用",
            "payload": {
                "excel_result": result,
            },
        }
    except Exception as e:
        return {
            "ok": False,
            "code": "service_exception",
            "message": str(e),
            "payload": {
                "excel_result": None,
            },
        }
