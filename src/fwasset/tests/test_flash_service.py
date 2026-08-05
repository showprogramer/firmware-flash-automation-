import pytest

from fwasset.core.services.flash_service import run_one_click


def test_run_one_click_ok(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "fwasset.core.services.flash_service.format_usb", lambda d, log_fn: True
    )
    monkeypatch.setattr(
        "fwasset.core.services.flash_service.copy_to_usb", lambda r, p, d, log_fn: True
    )
    monkeypatch.setattr(
        "fwasset.core.services.flash_service.eject_usb", lambda d, log_fn: True
    )

    result = run_one_click(
        "E:/", "L36", "V1.0.0", "r.ROM", "p.PKG", log_fn=lambda _m: None
    )

    assert result["ok"] is True
    assert result["payload"] == {
        "format_ok": True,
        "copy_ok": True,
        "ejected": True,
    }


def test_run_one_click_format_failed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "fwasset.core.services.flash_service.format_usb", lambda d, log_fn: False
    )

    result = run_one_click(
        "E:/", "L36", "V1.0.0", "r.ROM", "p.PKG", log_fn=lambda _m: None
    )

    assert result["ok"] is False
    assert result["code"] == "format_failed"
    assert result["payload"]["format_ok"] is False
    assert result["payload"]["copy_ok"] is False


def test_run_one_click_copy_failed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "fwasset.core.services.flash_service.format_usb", lambda d, log_fn: True
    )
    monkeypatch.setattr(
        "fwasset.core.services.flash_service.copy_to_usb", lambda r, p, d, log_fn: False
    )

    result = run_one_click(
        "E:/", "L36", "V1.0.0", "r.ROM", "p.PKG", log_fn=lambda _m: None
    )

    assert result["ok"] is False
    assert result["code"] == "copy_failed"
    assert result["payload"]["format_ok"] is True
    assert result["payload"]["copy_ok"] is False


def test_run_one_click_exception(monkeypatch: pytest.MonkeyPatch):
    def raise_format(d, log_fn):
        raise RuntimeError("format boom")

    monkeypatch.setattr("fwasset.core.services.flash_service.format_usb", raise_format)

    result = run_one_click(
        "E:/", "L36", "V1.0.0", "r.ROM", "p.PKG", log_fn=lambda _m: None
    )

    assert result["ok"] is False
    assert result["code"] == "service_exception"
