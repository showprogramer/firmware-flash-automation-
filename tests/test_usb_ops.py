from pathlib import Path
from types import SimpleNamespace

import pytest

from core.usb_ops import clean_usb, copy_to_usb, eject_usb, format_usb, get_usb_drives


def _logs():
    messages = []
    return messages, messages.append


def test_get_usb_drives_filters_expected_partitions(monkeypatch: pytest.MonkeyPatch):
    parts = [
        SimpleNamespace(opts="rw,removable", fstype="NTFS", mountpoint="E:\\"),
        SimpleNamespace(opts="rw", fstype="FAT32", mountpoint="F:\\"),
        SimpleNamespace(opts="rw", fstype="NTFS", mountpoint="C:\\"),
    ]
    monkeypatch.setattr("core.usb_ops.psutil.disk_partitions", lambda all=False: parts)

    drives = get_usb_drives()

    assert drives == ["E:\\", "F:\\"]


def test_clean_usb_deletes_only_junk_files(tmp_path: Path):
    junk_ext = tmp_path / "a.tmp"
    junk_name = tmp_path / "autorun.inf"
    keep = tmp_path / "keep.txt"
    junk_ext.write_text("x", encoding="utf-8")
    junk_name.write_text("x", encoding="utf-8")
    keep.write_text("x", encoding="utf-8")

    logs, log_fn = _logs()
    removed = clean_usb(str(tmp_path), log_fn=log_fn)

    assert removed == 2
    assert not junk_ext.exists()
    assert not junk_name.exists()
    assert keep.exists()
    assert any("删除垃圾文件" in msg for msg in logs)


def test_copy_to_usb_replaces_old_rom_pkg(tmp_path: Path):
    drive = tmp_path / "usb"
    drive.mkdir()
    old_rom = drive / "OLD.ROM"
    old_pkg = drive / "OLD.PKG"
    keep = drive / "note.txt"
    old_rom.write_text("old", encoding="utf-8")
    old_pkg.write_text("old", encoding="utf-8")
    keep.write_text("keep", encoding="utf-8")

    src = tmp_path / "src"
    src.mkdir()
    rom = src / "NEW.ROM"
    pkg = src / "NEW.PKG"
    rom.write_text("new rom", encoding="utf-8")
    pkg.write_text("new pkg", encoding="utf-8")

    logs, log_fn = _logs()
    ok = copy_to_usb(str(rom), str(pkg), str(drive), log_fn=log_fn)

    assert ok is True
    assert not old_rom.exists()
    assert not old_pkg.exists()
    assert (drive / "NEW.ROM").exists()
    assert (drive / "NEW.PKG").exists()
    assert keep.exists()
    assert any("移除旧文件" in msg for msg in logs)
    assert any("已复制" in msg for msg in logs)


def test_copy_to_usb_returns_false_on_error(tmp_path: Path):
    drive = tmp_path / "usb"
    drive.mkdir()
    missing_rom = tmp_path / "missing.ROM"
    missing_pkg = tmp_path / "missing.PKG"

    logs, log_fn = _logs()
    ok = copy_to_usb(str(missing_rom), str(missing_pkg), str(drive), log_fn=log_fn)

    assert ok is False
    assert any("复制失败" in msg for msg in logs)


def test_eject_usb_success(monkeypatch: pytest.MonkeyPatch):
    logs, log_fn = _logs()

    def fake_run(cmd, **kwargs):
        assert cmd[0] == "powershell"
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("core.usb_ops.subprocess.run", fake_run)

    ok = eject_usb("E:\\", log_fn=log_fn)

    assert ok is True
    assert any("已安全弹出" in msg for msg in logs)


def test_eject_usb_failure_and_exception(monkeypatch: pytest.MonkeyPatch):
    logs1, log_fn1 = _logs()
    monkeypatch.setattr(
        "core.usb_ops.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stderr="denied"),
    )
    ok1 = eject_usb("E:\\", log_fn=log_fn1)
    assert ok1 is False
    assert any("弹出失败" in msg for msg in logs1)

    logs2, log_fn2 = _logs()

    def raise_run(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("core.usb_ops.subprocess.run", raise_run)
    ok2 = eject_usb("E:\\", log_fn=log_fn2)
    assert ok2 is False
    assert any("弹出异常" in msg for msg in logs2)


def test_format_usb_success_failure_and_exception(monkeypatch: pytest.MonkeyPatch):
    logs1, log_fn1 = _logs()
    monkeypatch.setattr(
        "core.usb_ops.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stderr=""),
    )
    ok1 = format_usb("E:\\", log_fn=log_fn1)
    assert ok1 is True
    assert any("格式化完成" in msg for msg in logs1)

    logs2, log_fn2 = _logs()
    monkeypatch.setattr(
        "core.usb_ops.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stderr="failed"),
    )
    ok2 = format_usb("E:\\", log_fn=log_fn2)
    assert ok2 is False
    assert any("格式化失败" in msg for msg in logs2)

    logs3, log_fn3 = _logs()

    def raise_run(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("core.usb_ops.subprocess.run", raise_run)
    ok3 = format_usb("E:\\", log_fn=log_fn3)
    assert ok3 is False
    assert any("格式化异常" in msg for msg in logs3)
