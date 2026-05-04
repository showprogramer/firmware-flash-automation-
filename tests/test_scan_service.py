import pytest

from fwasset.core.services.scan_service import build_scan_result


def test_build_scan_result_ok(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "fwasset.core.services.scan_service.scan_firmware_assets",
        lambda root: ([{"firmware_type": "handcontrol_ui", "model": "L36", "version": "V1.0.0", "label": "x"}], []),
    )
    monkeypatch.setattr(
        "fwasset.core.services.scan_service.find_handcontrol_folders",
        lambda root: [{"model": "L36", "version": "V1.0.0", "label": "x"}],
    )

    result = build_scan_result("D:/x", log_fn=lambda _m: None)

    assert result["ok"] is True
    assert result["code"] == "ok"
    assert len(result["payload"]["assets"]) == 1
    assert len(result["payload"]["folders"]) == 1
    assert result["payload"]["errors"] == []
    assert "status_map" not in result["payload"]


def test_build_scan_result_failed(monkeypatch: pytest.MonkeyPatch):
    def raise_scan(_root):
        raise RuntimeError("scan boom")

    monkeypatch.setattr("fwasset.core.services.scan_service.scan_firmware_assets", raise_scan)

    result = build_scan_result("D:/x", log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "scan_failed"
    assert "scan boom" in result["message"]
