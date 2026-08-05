"""Tests for shared_modules load/save on 型号配置.toml (Phase B1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fwasset.core import config_io
from fwasset.core.model_config import (
    SharedModuleRef,
    load_model_config,
    load_shared_modules,
    remove_shared_module,
    save_model_id,
    save_shared_module,
)


def _ref(
    key: str = "快捷键程序",
    *,
    sid: str = "l36",
    group: str = "l36-single",
    smod: str = "快捷键程序",
    path: str = "L36程序/通用/快捷键/贝乐",
) -> SharedModuleRef:
    return SharedModuleRef(
        module_key=key,
        source_model_id=sid,
        source_group=group,
        source_module=smod,
        source_relative_path=path,
    )


def test_load_empty_when_missing(tmp_path: Path):
    assert load_shared_modules(tmp_path) == []


def test_load_empty_when_no_shared_section(tmp_path: Path):
    save_model_id(tmp_path, "l36")
    assert load_shared_modules(tmp_path) == []


def test_save_and_load_one_ref(tmp_path: Path):
    save_shared_module(tmp_path, _ref())
    refs = load_shared_modules(tmp_path)
    assert len(refs) == 1
    assert refs[0].module_key == "快捷键程序"
    assert refs[0].source_model_id == "l36"
    assert refs[0].source_group == "l36-single"
    assert refs[0].source_relative_path == "L36程序/通用/快捷键/贝乐"


def test_preserves_model_id(tmp_path: Path):
    save_model_id(tmp_path, "x")
    save_shared_module(tmp_path, _ref())
    mid, status, _ = load_model_config(tmp_path)
    assert status == "ok"
    assert mid == "x"


def test_preserves_other_shared_segments(tmp_path: Path):
    save_shared_module(tmp_path, _ref("蓝牙程序", path="L50程序/通用/蓝牙/中文"))
    save_shared_module(tmp_path, _ref("快捷键程序"))
    keys = {r.module_key for r in load_shared_modules(tmp_path)}
    assert keys == {"蓝牙程序", "快捷键程序"}


def test_same_key_overwrite_idempotent(tmp_path: Path):
    save_shared_module(tmp_path, _ref(path="A/B"))
    save_shared_module(tmp_path, _ref(path="C/D"))
    refs = load_shared_modules(tmp_path)
    assert len(refs) == 1
    assert refs[0].source_relative_path == "C/D"


def test_remove_shared_module(tmp_path: Path):
    save_model_id(tmp_path, "keep")
    save_shared_module(tmp_path, _ref("蓝牙程序", path="L50/a"))
    save_shared_module(tmp_path, _ref("快捷键程序"))
    remove_shared_module(tmp_path, "快捷键程序")
    refs = load_shared_modules(tmp_path)
    assert [r.module_key for r in refs] == ["蓝牙程序"]
    assert load_model_config(tmp_path)[0] == "keep"
    remove_shared_module(tmp_path, "不存在")
    assert load_model_config(tmp_path)[0] == "keep"


def test_remove_on_missing_file_is_noop(tmp_path: Path):
    """审查 #1：对无 型号配置.toml 的根 remove，不得凭空建文件。"""
    remove_shared_module(tmp_path, "快捷键程序")
    assert not (tmp_path / "型号配置.toml").exists()


def test_save_model_id_and_shared_roundtrip(tmp_path: Path):
    save_model_id(tmp_path, "first")
    save_shared_module(tmp_path, _ref())
    save_model_id(tmp_path, "second")
    assert load_model_config(tmp_path)[0] == "second"
    refs = load_shared_modules(tmp_path)
    assert len(refs) == 1
    assert refs[0].module_key == "快捷键程序"


def test_atomic_replace_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    save_model_id(tmp_path, "keep")
    path = tmp_path / "型号配置.toml"
    original = path.read_bytes()

    def boom(_s: str, _d: str) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(config_io.os, "replace", boom)
    with pytest.raises(OSError):
        save_shared_module(tmp_path, _ref())
    assert path.read_bytes() == original
    assert list(tmp_path.glob(".型号配置.toml.*.tmp")) == []


def test_unknown_table_preserved(tmp_path: Path):
    path = tmp_path / "型号配置.toml"
    path.write_text(
        'model_id = "x"\n\n[future_section]\nflag = "yes"\n',
        encoding="utf-8",
    )
    save_shared_module(tmp_path, _ref())
    text = path.read_text(encoding="utf-8")
    assert "future_section" in text
    assert 'flag = "yes"' in text or "flag" in text
    assert load_model_config(tmp_path)[0] == "x"


def test_header_comment_rewritten(tmp_path: Path):
    save_shared_module(tmp_path, _ref())
    text = (tmp_path / "型号配置.toml").read_text(encoding="utf-8")
    assert "本文件由 fwasset 管理" in text
    assert "display_name 不落盘" in text


def test_skip_incomplete_entry(tmp_path: Path):
    path = tmp_path / "型号配置.toml"
    path.write_text(
        "\n".join(
            [
                'model_id = "x"',
                '[shared_modules."快捷键程序"]',
                'source_model_id = "l36"',
                # missing other fields
                "",
            ]
        ),
        encoding="utf-8",
    )
    assert load_shared_modules(tmp_path) == []


def test_canonical_module_key_on_save(tmp_path: Path):
    save_shared_module(
        tmp_path,
        _ref(key="3D机芯版程序", smod="3D机芯版程序", path="L50/通用/x"),
    )
    refs = load_shared_modules(tmp_path)
    assert refs[0].module_key == "3D机芯板程序"
