import pytest

from fwasset.core.services.scan_service import (
    build_cached_scan_result,
    build_scan_result,
)


def test_build_scan_result_ok(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "fwasset.core.services.scan_service.scan_firmware_assets",
        lambda root, last_scan_at=None, cancel_event=None: (
            [
                {
                    "firmware_type": "handcontrol_ui",
                    "model": "L36",
                    "version": "V1.0.0",
                    "label": "x",
                }
            ],
            [],
        ),
    )
    monkeypatch.setattr(
        "fwasset.core.services.scan_service.save_assets", lambda assets, root: None
    )
    # folders 由 handcontrol_folders_from_assets 从 assets 派生；本 fixture 无 rom/pkg → 0 folders
    monkeypatch.setattr(
        "fwasset.core.services.scan_service.handcontrol_folders_from_assets",
        lambda assets: [{"model": "L36", "version": "V1.0.0", "label": "x"}],
    )

    result = build_scan_result("D:/x", log_fn=lambda _m: None)

    assert result["ok"] is True
    assert result["code"] == "ok"
    assert len(result["payload"]["assets"]) == 1
    assert len(result["payload"]["folders"]) == 1
    assert result["payload"]["errors"] == []


def test_build_scan_result_uses_full_scan_when_scan_meta_exists(
    monkeypatch: pytest.MonkeyPatch,
):
    seen = {}

    def fake_scan(root, last_scan_at=None, cancel_event=None):
        seen["last_scan_at"] = last_scan_at
        return (
            [
                {
                    "firmware_type": "handcontrol_ui",
                    "model": "L36",
                    "version": "V1.0.0",
                    "label": "x",
                }
            ],
            [],
        )

    monkeypatch.setattr(
        "fwasset.core.services.scan_service.load_scan_meta",
        lambda: [{"root_dir": "D:/x", "last_scan_at": 123.0, "schema_version": 2}],
    )
    monkeypatch.setattr(
        "fwasset.core.services.scan_service.scan_firmware_assets", fake_scan
    )
    monkeypatch.setattr(
        "fwasset.core.services.scan_service.handcontrol_folders_from_assets",
        lambda assets: [],
    )
    monkeypatch.setattr(
        "fwasset.core.services.scan_service.save_assets", lambda assets, root: None
    )

    result = build_scan_result("D:/x", log_fn=lambda _m: None)

    assert result["ok"] is True
    assert seen["last_scan_at"] is None


def test_build_scan_result_failed(monkeypatch: pytest.MonkeyPatch):
    def raise_scan(root, last_scan_at=None, cancel_event=None):
        raise RuntimeError("scan boom")

    monkeypatch.setattr(
        "fwasset.core.services.scan_service.scan_firmware_assets", raise_scan
    )

    result = build_scan_result("D:/x", log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "scan_failed"
    assert "scan boom" in result["message"]


def test_build_cached_scan_result_ok(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("fwasset.core.services.scan_service.count_assets", lambda: 1)
    monkeypatch.setattr("fwasset.core.services.scan_service.load_scan_meta", lambda: [])

    result = build_cached_scan_result(log_fn=lambda _m: None)

    assert result["ok"] is True
    assert result["code"] == "ok"
    assert result["payload"]["asset_count"] == 1
    assert result["payload"]["assets"] == []
    assert result["payload"]["folders"] == []


def test_build_cached_scan_result_maps_db_errors_to_index_unavailable(
    monkeypatch: pytest.MonkeyPatch,
):
    """锁库/DB 错误不得裸抛，须返回 index_unavailable ServiceResult。"""
    import sqlite3

    def boom():
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr("fwasset.core.services.scan_service.count_assets", boom)

    result = build_cached_scan_result(log_fn=lambda _m: None)

    assert result["ok"] is False
    assert result["code"] == "index_unavailable"
    assert "locked" in result["message"]
    assert result["payload"]["scan_meta"] == []


def test_build_scan_result_cancelled(monkeypatch: pytest.MonkeyPatch):
    import threading

    cancel = threading.Event()
    cancel.set()

    def fake_scan(root, last_scan_at=None, cancel_event=None):
        return ([], [])

    saved = {"called": False}

    def fake_save(assets, root):
        saved["called"] = True

    monkeypatch.setattr(
        "fwasset.core.services.scan_service.scan_firmware_assets", fake_scan
    )
    monkeypatch.setattr("fwasset.core.services.scan_service.save_assets", fake_save)

    result = build_scan_result("D:/x", log_fn=lambda _m: None, cancel_event=cancel)

    assert result["ok"] is True
    assert result["code"] == "cancelled"
    assert "取消" in result["message"]
    assert result["payload"]["assets"] == []
    assert saved["called"] is False
