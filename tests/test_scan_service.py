import pytest

from handcontrol.core.services.scan_service import build_scan_result


def test_build_scan_result_ok(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "handcontrol.core.services.scan_service.find_handcontrol_folders",
        lambda root: [{"model": "L36", "version": "V1.0.0", "label": "x"}],
    )

    result = build_scan_result("D:/x", log_fn=lambda _m: None)

    assert result["ok"] is True
    assert result["code"] == "ok"
    assert len(result["payload"]["folders"]) == 1
    assert "status_map" not in result["payload"]


def test_build_scan_result_failed(monkeypatch: pytest.MonkeyPatch):
    def raise_scan(_root):
        raise RuntimeError("scan boom")

    monkeypatch.setattr("handcontrol.core.services.scan_service.find_handcontrol_folders", raise_scan)

    result = build_scan_result("D:/x", log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "scan_failed"
    assert "scan boom" in result["message"]
