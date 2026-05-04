import pytest

from handcontrol.core.services.flash_service import run_one_click


def test_run_one_click_ok(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("handcontrol.core.services.flash_service.clean_usb", lambda d, log_fn: 2)
    monkeypatch.setattr("handcontrol.core.services.flash_service.copy_to_usb", lambda r, p, d, log_fn: True)
    monkeypatch.setattr("handcontrol.core.services.flash_service.eject_usb", lambda d, log_fn: True)

    result = run_one_click("E:/", "L36", "V1.0.0", "r.ROM", "p.PKG", log_fn=lambda _m: None)

    assert result["ok"] is True
    assert result["payload"] == {
        "copy_ok": True,
        "removed_count": 2,
        "ejected": True,
    }


def test_run_one_click_copy_failed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("handcontrol.core.services.flash_service.clean_usb", lambda d, log_fn: 1)
    monkeypatch.setattr("handcontrol.core.services.flash_service.copy_to_usb", lambda r, p, d, log_fn: False)

    result = run_one_click("E:/", "L36", "V1.0.0", "r.ROM", "p.PKG", log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "copy_failed"
    assert "excel_result" not in result["payload"]


def test_run_one_click_exception(monkeypatch: pytest.MonkeyPatch):
    def raise_clean(d, log_fn):
        raise RuntimeError("clean boom")

    monkeypatch.setattr("handcontrol.core.services.flash_service.clean_usb", raise_clean)

    result = run_one_click("E:/", "L36", "V1.0.0", "r.ROM", "p.PKG", log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "service_exception"
