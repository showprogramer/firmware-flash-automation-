"""C0：SharedModuleRef schema 扩展——mode / source_platform 可选字段兼容读写。"""

from __future__ import annotations

from pathlib import Path

import tomli_w

from fwasset.core.model_config import (
    SharedModuleRef,
    load_shared_modules,
    save_model_id,
    save_shared_module,
)

# ---------------------------------------------------------------------------
# 辅助：直接落盘一份 Phase B 格式的 toml（无 mode / source_platform 键）
# ---------------------------------------------------------------------------


def _write_phase_b_toml(model_root: Path, key: str, entry: dict) -> None:
    model_root.mkdir(parents=True, exist_ok=True)
    data = {"model_id": "test-model", "shared_modules": {key: entry}}
    (model_root / "型号配置.toml").write_bytes(tomli_w.dumps(data).encode())


_PHASE_B_ENTRY = {
    "source_model_id": "l50s",
    "source_group": "l50s",
    "source_module": "手控UI",
    "source_relative_path": "L50S程序/通用/手控UI/v2.0",
}


# ---------------------------------------------------------------------------
# 1. Phase B toml 无 mode 键 → 读出 mode="static", source_platform=""
# ---------------------------------------------------------------------------


def test_phase_b_toml_reads_as_static(tmp_path: Path):
    root = tmp_path / "model"
    _write_phase_b_toml(root, "手控UI", _PHASE_B_ENTRY)

    refs = load_shared_modules(root)
    assert len(refs) == 1
    assert refs[0].mode == "static"
    assert refs[0].source_platform == ""


# ---------------------------------------------------------------------------
# 2. follow_default + source_platform round-trip
# ---------------------------------------------------------------------------


def test_follow_default_round_trip(tmp_path: Path):
    root = tmp_path / "model"
    root.mkdir()
    save_model_id(root, "l36-dual")
    ref = SharedModuleRef(
        module_key="手控UI",
        source_model_id="l50s",
        source_group="l50s",
        source_module="手控UI",
        source_relative_path="L50S程序/通用/手控UI",
        mode="follow_default",
        source_platform="标准单机芯",
    )
    save_shared_module(root, ref)
    refs = load_shared_modules(root)
    assert len(refs) == 1
    r = refs[0]
    assert r.mode == "follow_default"
    assert r.source_platform == "标准单机芯"
    assert r.source_relative_path == "L50S程序/通用/手控UI"


# ---------------------------------------------------------------------------
# 3. toml 中遗留 mode="pinned" → 容错回退为 "static"
# ---------------------------------------------------------------------------


def test_legacy_pinned_falls_back_to_static(tmp_path: Path):
    root = tmp_path / "model"
    entry = {**_PHASE_B_ENTRY, "mode": "pinned"}
    _write_phase_b_toml(root, "主板程序", entry)

    refs = load_shared_modules(root)
    assert len(refs) == 1
    assert refs[0].mode == "static"


# ---------------------------------------------------------------------------
# 4. mode="static" 写入时 toml 不含 mode 键（Phase B 格式兼容）
# ---------------------------------------------------------------------------


def test_static_mode_not_written_to_toml(tmp_path: Path):
    root = tmp_path / "model"
    root.mkdir()
    save_model_id(root, "l36")
    ref = SharedModuleRef(
        module_key="快捷键程序",
        source_model_id="l50s",
        source_group="l50s",
        source_module="快捷键程序",
        source_relative_path="L50S程序/通用/快捷键/贝乐",
        mode="static",
    )
    save_shared_module(root, ref)
    raw = (root / "型号配置.toml").read_text(encoding="utf-8")
    # 检查独立键 "mode ="，避免 model_id 中的子串误判
    assert "mode =" not in raw


# ---------------------------------------------------------------------------
# 5. source_platform 为空时不写入 toml
# ---------------------------------------------------------------------------


def test_empty_source_platform_not_written(tmp_path: Path):
    root = tmp_path / "model"
    root.mkdir()
    save_model_id(root, "l36")
    ref = SharedModuleRef(
        module_key="语音程序",
        source_model_id="l50s",
        source_group="l50s",
        source_module="语音程序",
        source_relative_path="L50S程序/通用/语音/v1.0",
        mode="follow_default",
        source_platform="",
    )
    save_shared_module(root, ref)
    raw = (root / "型号配置.toml").read_text(encoding="utf-8")
    assert "source_platform" not in raw


# ---------------------------------------------------------------------------
# 6. toml 中 mode 为无效值 → 容错回退为 "static"
# ---------------------------------------------------------------------------


def test_invalid_mode_falls_back_to_static(tmp_path: Path):
    root = tmp_path / "model"
    entry = {**_PHASE_B_ENTRY, "mode": "unknown_future_mode"}
    _write_phase_b_toml(root, "手控UI", entry)

    refs = load_shared_modules(root)
    assert len(refs) == 1
    assert refs[0].mode == "static"


# ---------------------------------------------------------------------------
# 7. follow_default 不带 source_platform（空串）round-trip
# ---------------------------------------------------------------------------


def test_follow_default_without_source_platform(tmp_path: Path):
    root = tmp_path / "model"
    root.mkdir()
    save_model_id(root, "l36-dual")
    ref = SharedModuleRef(
        module_key="手控UI",
        source_model_id="l50s",
        source_group="l50s",
        source_module="手控UI",
        source_relative_path="L50S程序/通用/手控UI",
        mode="follow_default",
        source_platform="",
    )
    save_shared_module(root, ref)
    refs = load_shared_modules(root)
    assert len(refs) == 1
    assert refs[0].mode == "follow_default"
    assert refs[0].source_platform == ""


# ---------------------------------------------------------------------------
# 8. 同一 toml 混合 Phase B 与 Phase C 引用
# ---------------------------------------------------------------------------


def test_mixed_phase_b_and_phase_c_refs(tmp_path: Path):
    root = tmp_path / "model"
    root.mkdir()
    save_model_id(root, "l36-dual")

    # Phase B 格式手写入
    _write_phase_b_toml(root, "手控UI", _PHASE_B_ENTRY)

    # 追加一条 Phase C 引用（save_shared_module 走 merge-write，不会删掉 Phase B 条目）
    ref_c = SharedModuleRef(
        module_key="主板程序",
        source_model_id="l50s",
        source_group="l50s",
        source_module="主板程序",
        source_relative_path="L50S程序/通用/主板程序",
        mode="follow_default",
        source_platform="标准单机芯",
    )
    save_shared_module(root, ref_c)

    refs = load_shared_modules(root)
    assert len(refs) == 2
    by_key = {r.module_key: r for r in refs}

    assert by_key["手控UI"].mode == "static"
    assert by_key["手控UI"].source_platform == ""
    assert by_key["主板程序"].mode == "follow_default"
    assert by_key["主板程序"].source_platform == "标准单机芯"
