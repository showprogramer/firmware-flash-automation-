"""Tests for ensure_model_ids — 先读全量、再生成、碰撞与损坏。"""
from __future__ import annotations

from pathlib import Path

import pytest

from fwasset.core import config_io
from fwasset.core.model_config import load_model_config, save_model_id
from fwasset.core.services.model_id_service import ensure_model_ids


def _silent(_m: str) -> None:
    pass


def test_assigns_two_fresh_roots(tmp_path: Path):
    r1 = tmp_path / "L36程序"
    r2 = tmp_path / "L50程序"
    r1.mkdir()
    r2.mkdir()
    result = ensure_model_ids([r1, r2], log_fn=_silent)
    assert result["ok"] is True
    assert result["code"] == "ok"
    assert load_model_config(r1)[0] == "l36"
    assert load_model_config(r2)[0] == "l50"
    assert result["payload"]["assigned"]["L36程序"] == "l36"
    assert result["payload"]["assigned"]["L50程序"] == "l50"


def test_second_call_keeps_ids(tmp_path: Path):
    r1 = tmp_path / "L36程序"
    r1.mkdir()
    ensure_model_ids([r1], log_fn=_silent)
    mid1 = load_model_config(r1)[0]
    result = ensure_model_ids([r1], log_fn=_silent)
    assert result["ok"] is True
    assert load_model_config(r1)[0] == mid1
    assert result["payload"]["existing"]["L36程序"] == mid1
    assert result["payload"]["assigned"] == {}


def test_rename_keeps_id(tmp_path: Path):
    r1 = tmp_path / "L36程序"
    r1.mkdir()
    ensure_model_ids([r1], log_fn=_silent)
    assert load_model_config(r1)[0] == "l36"
    renamed = tmp_path / "L36改名程序"
    r1.rename(renamed)
    result = ensure_model_ids([renamed], log_fn=_silent)
    assert result["ok"] is True
    assert load_model_config(renamed)[0] == "l36"
    assert result["payload"]["existing"]["L36改名程序"] == "l36"


def test_collision_respects_existing_first(tmp_path: Path):
    a = tmp_path / "L36程序"
    b = tmp_path / "L36"
    a.mkdir()
    b.mkdir()
    save_model_id(a, "l36")
    result = ensure_model_ids([a, b], log_fn=_silent)
    assert result["ok"] is True
    assert load_model_config(a)[0] == "l36"
    assert load_model_config(b)[0] == "l36-2"
    assert result["payload"]["existing"]["L36程序"] == "l36"
    assert result["payload"]["assigned"]["L36"] == "l36-2"


def test_collision_suffix_stable_after_other_removed(tmp_path: Path):
    a = tmp_path / "L36程序"
    b = tmp_path / "L36"
    a.mkdir()
    b.mkdir()
    ensure_model_ids([a, b], log_fn=_silent)
    id_a = load_model_config(a)[0]
    id_b = load_model_config(b)[0]
    assert {id_a, id_b} == {"l36", "l36-2"}
    # 移走 l36 根
    if id_a == "l36":
        a.rename(tmp_path / "_gone")
        remain = b
        expected = "l36-2"
    else:
        b.rename(tmp_path / "_gone")
        remain = a
        expected = "l36-2"
    result = ensure_model_ids([remain], log_fn=_silent)
    assert result["ok"] is True
    assert load_model_config(remain)[0] == expected


def test_damaged_root_skipped_others_continue(tmp_path: Path):
    good = tmp_path / "L50程序"
    bad = tmp_path / "L36程序"
    good.mkdir()
    bad.mkdir()
    (bad / "型号配置.toml").write_text("[[broken\n", encoding="utf-8")
    original = (bad / "型号配置.toml").read_bytes()
    result = ensure_model_ids([good, bad], log_fn=_silent)
    assert result["ok"] is False
    assert result["code"] == "parse_error"
    assert "L36程序" in result["payload"]["damaged"]
    assert load_model_config(good)[0] == "l50"
    assert (bad / "型号配置.toml").read_bytes() == original


def test_write_failed_stops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    r1 = tmp_path / "L36程序"
    r1.mkdir()

    def boom(_src: str, _dst: str) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(config_io.os, "replace", boom)
    result = ensure_model_ids([r1], log_fn=_silent)
    assert result["ok"] is False
    assert result["code"] == "write_failed"
    assert not (r1 / "型号配置.toml").exists()
    assert list(r1.glob(".型号配置.toml.*.tmp")) == []
