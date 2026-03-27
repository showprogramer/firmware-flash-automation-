from pathlib import Path
import zipfile

from handcontrol.core.diagnostics import build_diagnostic_bundle, sanitize_snapshot


def test_sanitize_snapshot_masks_path_fields():
    payload = {
        "root_dir": "D:/workspace/private",
        "current_folder": {"path": "D:/workspace/private/L36"},
        "items": [{"excel_path": "D:/workspace/private/records.xlsx"}],
    }

    masked = sanitize_snapshot(payload)

    assert masked["root_dir"] == "<redacted>/private"
    assert masked["current_folder"]["path"] == "<redacted>/L36"
    assert masked["items"][0]["excel_path"] == "<redacted>/records.xlsx"


def test_build_diagnostic_bundle_writes_expected_entries(tmp_path: Path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("[paths]\nroot_dir='D:/secret/root'\nexcel_path='D:/secret/records.xlsx'\n", encoding="utf-8")
    log_path = tmp_path / "logs" / "app.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("hello\n", encoding="utf-8")
    output = tmp_path / "diag.zip"

    result = build_diagnostic_bundle(
        output,
        app_state={
            "summary": {"status_text": "就绪"},
            "current_folder": {"path": "D:/secret/root/L36"},
            "folders": [{"path": "D:/secret/root/L36", "model": "L36"}],
            "preview_rows": [{"model": "L36", "version": "V1.0.0"}],
            "folder_statuses": [{"model": "L36", "version": "V1.0.0", "status": "待确认"}],
        },
        config_path=config_path,
        log_path=log_path,
    )

    assert result["ok"] is True
    assert output.exists()

    with zipfile.ZipFile(output) as zf:
        names = set(zf.namelist())
        assert "meta.json" in names
        assert "state/app_state.json" in names
        assert "state/folders.json" in names
        assert "state/preview_rows.json" in names
        assert "config/config.sanitized.json" in names
        assert "logs/app.log" in names

        config_text = zf.read("config/config.sanitized.json").decode("utf-8")
        state_text = zf.read("state/app_state.json").decode("utf-8")

    assert "D:/secret/root" not in config_text
    assert "D:/secret/root" not in state_text
    assert "<redacted>/records.xlsx" in config_text
    assert "<redacted>/L36" in state_text


def test_build_diagnostic_bundle_handles_missing_log(tmp_path: Path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("[paths]\nroot_dir=''\n", encoding="utf-8")
    output = tmp_path / "diag.zip"

    build_diagnostic_bundle(
        output,
        app_state={"summary": {}, "folders": [], "preview_rows": [], "folder_statuses": []},
        config_path=config_path,
        log_path=tmp_path / "missing.log",
    )

    with zipfile.ZipFile(output) as zf:
        assert "logs/app.log.missing.txt" in zf.namelist()
