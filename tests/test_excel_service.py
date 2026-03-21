import pytest

from core.services.excel_service import write_record


def test_write_record_ok(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "core.services.excel_service.write_excel_record",
        lambda **kwargs: {
            "ok": True,
            "reason": "ok",
            "tmp_path": "",
            "error": "",
            "written_row": {
                "model": "L36",
                "logo": "A",
                "salesman": "S",
                "language": "CN",
                "version": "V1.0.0",
                "date": "2026.03.21",
                "remark": "待确认",
            },
        },
    )

    result = write_record("a.xlsx", "Sheet1", "L36", "V1.0.0", "待确认", "r.ROM", log_fn=lambda _m: None)

    assert result["ok"] is True
    assert result["payload"]["preview_row"]["model"] == "L36"


def test_write_record_locked(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "core.services.excel_service.write_excel_record",
        lambda **kwargs: {"ok": False, "reason": "locked", "tmp_path": "tmp.xlsx", "error": "", "written_row": None},
    )

    result = write_record("a.xlsx", "Sheet1", "L36", "V1.0.0", "待确认", "r.ROM", log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "locked"
    assert result["payload"]["preview_row"] == {}


def test_write_record_exception(monkeypatch: pytest.MonkeyPatch):
    def raise_write(**kwargs):
        raise RuntimeError("svc boom")

    monkeypatch.setattr("core.services.excel_service.write_excel_record", raise_write)

    result = write_record("a.xlsx", "Sheet1", "L36", "V1.0.0", "待确认", "r.ROM", log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "service_exception"
