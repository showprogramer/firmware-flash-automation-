import pytest

from core.services.flash_service import run_one_click


def test_run_one_click_ok(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("core.services.flash_service.clean_usb", lambda d, log_fn: 2)
    monkeypatch.setattr("core.services.flash_service.copy_to_usb", lambda r, p, d, log_fn: True)
    monkeypatch.setattr("core.services.flash_service.eject_usb", lambda d, log_fn: True)
    monkeypatch.setattr(
        "core.services.flash_service.write_excel_record",
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
                "attachment": "可通用",
                "remark": "待确认",
            },
        },
    )

    result = run_one_click("E:/", "L36", "V1.0.0", "r.ROM", "p.PKG", "a.xlsx", "Sheet1", log_fn=lambda _m: None)

    assert result["ok"] is True
    assert result["payload"]["copy_ok"] is True
    assert result["payload"]["preview_row"]["remark"] == "待确认"
    assert result["payload"]["preview_row"]["attachment"] == "可通用"


def test_run_one_click_copy_failed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("core.services.flash_service.clean_usb", lambda d, log_fn: 1)
    monkeypatch.setattr("core.services.flash_service.copy_to_usb", lambda r, p, d, log_fn: False)

    result = run_one_click("E:/", "L36", "V1.0.0", "r.ROM", "p.PKG", "a.xlsx", "Sheet1", log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "copy_failed"


def test_run_one_click_exception(monkeypatch: pytest.MonkeyPatch):
    def raise_clean(d, log_fn):
        raise RuntimeError("clean boom")

    monkeypatch.setattr("core.services.flash_service.clean_usb", raise_clean)

    result = run_one_click("E:/", "L36", "V1.0.0", "r.ROM", "p.PKG", "a.xlsx", "Sheet1", log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "service_exception"


