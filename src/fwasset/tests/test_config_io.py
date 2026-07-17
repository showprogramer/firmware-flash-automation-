"""Tests for atomic_write_text — 失败时原文件不变、临时文件清理。"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from fwasset.core.config_io import atomic_write_text


def test_writes_new_file_with_content_and_newline(tmp_path: Path) -> None:
    target = tmp_path / "cfg.toml"
    atomic_write_text(target, "hello\n")
    assert target.read_text(encoding="utf-8") == "hello\n"


def test_overwrites_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "cfg.toml"
    target.write_text("old\n", encoding="utf-8")
    atomic_write_text(target, "new\n")
    assert target.read_text(encoding="utf-8") == "new\n"


def test_os_replace_failure_leaves_existing_bytes_and_no_tmp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "cfg.toml"
    original = "preserve-me\n".encode("utf-8")
    target.write_bytes(original)

    def boom(_src: str, _dst: str) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="replace failed"):
        atomic_write_text(target, "should-not-land\n")
    assert target.read_bytes() == original
    assert list(tmp_path.glob(".cfg.toml.*.tmp")) == []


def test_os_fsync_failure_leaves_existing_bytes_and_no_tmp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "cfg.toml"
    original = "still-here\n".encode("utf-8")
    target.write_bytes(original)

    def boom(_fd: int) -> None:
        raise OSError("fsync failed")

    monkeypatch.setattr(os, "fsync", boom)
    with pytest.raises(OSError, match="fsync failed"):
        atomic_write_text(target, "nope\n")
    assert target.read_bytes() == original
    assert list(tmp_path.glob(".cfg.toml.*.tmp")) == []


def test_replace_failure_when_target_missing_creates_no_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "new.toml"

    def boom(_src: str, _dst: str) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        atomic_write_text(target, "x\n")
    assert not target.exists()
    assert list(tmp_path.glob(".new.toml.*.tmp")) == []


def test_chinese_path_and_filename(tmp_path: Path) -> None:
    root = tmp_path / "型号根"
    root.mkdir()
    target = root / "平台配置.toml"
    atomic_write_text(target, 'name = "标准单机芯3D"\n')
    assert target.read_text(encoding="utf-8") == 'name = "标准单机芯3D"\n'
