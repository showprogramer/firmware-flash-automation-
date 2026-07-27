"""C1：follow_default 模式解析器测试。"""
from __future__ import annotations

from pathlib import Path

from fwasset.core.model_config import SharedModuleRef, save_model_id
from fwasset.core.platform_config import PlatformDefaults, save_platform_config
from fwasset.core.shared_module_resolver import resolve_shared_module


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _make_source_root(ws: Path, dir_name: str, model_id: str) -> Path:
    root = ws / dir_name
    root.mkdir(parents=True, exist_ok=True)
    save_model_id(root, model_id)
    return root


def _make_variant(module_dir: Path, variant_name: str) -> Path:
    v = module_dir / variant_name
    v.mkdir(parents=True, exist_ok=True)
    (v / "fw.bin").write_bytes(b"X")
    return v


def _make_ref(
    *,
    source_root_dir: str,
    module_rel: str,
    source_model_id: str = "l50s",
    source_module: str = "手控UI",
    mode: str = "follow_default",
    source_platform: str = "",
) -> SharedModuleRef:
    return SharedModuleRef(
        module_key=source_module,
        source_model_id=source_model_id,
        source_group=source_model_id,
        source_module=source_module,
        source_relative_path=f"{source_root_dir}/{module_rel}",
        mode=mode,  # type: ignore[arg-type]
        source_platform=source_platform,
    )


# ---------------------------------------------------------------------------
# 1. follow_default — 显式 source_platform，命中正确变体
# ---------------------------------------------------------------------------

def test_follow_default_explicit_platform_hit(tmp_path: Path):
    ws = tmp_path / "ws"
    src = _make_source_root(ws, "L50S程序", "l50s")
    module_dir = src / "通用" / "手控UI"
    _make_variant(module_dir, "v2.0")
    _make_variant(module_dir, "v3.0")
    save_platform_config(src, [
        PlatformDefaults("标准单机芯", {"手控UI": "v2.0"}),
    ])

    ref = _make_ref(
        source_root_dir="L50S程序",
        module_rel="通用/手控UI",
        source_platform="标准单机芯",
    )
    res = resolve_shared_module(ref, ws)
    assert res.status == "hit"
    assert res.resolved_path == (src / "通用" / "手控UI" / "v2.0").resolve()
    assert res.variants == [res.resolved_path]


# ---------------------------------------------------------------------------
# 2. follow_default — 空 source_platform，自动检测（第一个含该模块的块）
# ---------------------------------------------------------------------------

def test_follow_default_auto_detect_platform(tmp_path: Path):
    ws = tmp_path / "ws"
    src = _make_source_root(ws, "L50S程序", "l50s")
    module_dir = src / "通用" / "手控UI"
    _make_variant(module_dir, "v3.0")
    save_platform_config(src, [
        PlatformDefaults("无关平台", {}),           # 无该模块，跳过
        PlatformDefaults("标准单机芯", {"手控UI": "v3.0"}),
    ])

    ref = _make_ref(
        source_root_dir="L50S程序",
        module_rel="通用/手控UI",
        source_platform="",
    )
    res = resolve_shared_module(ref, ws)
    assert res.status == "hit"
    assert res.resolved_path == (src / "通用" / "手控UI" / "v3.0").resolve()


# ---------------------------------------------------------------------------
# 3. follow_default — defaults[module] = ""（唯一变体），resolved = 模块目录本身
# ---------------------------------------------------------------------------

def test_follow_default_leaf_module(tmp_path: Path):
    ws = tmp_path / "ws"
    src = _make_source_root(ws, "L50S程序", "l50s")
    module_dir = src / "通用" / "语音程序"
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "voice.bin").write_bytes(b"V")
    save_platform_config(src, [
        PlatformDefaults("标准单机芯", {"语音程序": ""}),
    ])

    ref = _make_ref(
        source_root_dir="L50S程序",
        module_rel="通用/语音程序",
        source_module="语音程序",
        source_platform="标准单机芯",
    )
    res = resolve_shared_module(ref, ws)
    assert res.status == "hit"
    assert res.resolved_path == module_dir.resolve()


# ---------------------------------------------------------------------------
# 4. follow_default — 源无 平台配置.toml → missing, no_source_platform
# ---------------------------------------------------------------------------

def test_follow_default_no_platform_config(tmp_path: Path):
    ws = tmp_path / "ws"
    src = _make_source_root(ws, "L50S程序", "l50s")
    module_dir = src / "通用" / "手控UI"
    _make_variant(module_dir, "v2.0")
    # 不写 平台配置.toml

    ref = _make_ref(
        source_root_dir="L50S程序",
        module_rel="通用/手控UI",
        source_platform="标准单机芯",
    )
    res = resolve_shared_module(ref, ws)
    assert res.status == "missing"
    assert res.reason == "no_source_platform"


# ---------------------------------------------------------------------------
# 5. follow_default — 显式 source_platform 不存在于平台配置 → missing, no_source_platform
# ---------------------------------------------------------------------------

def test_follow_default_explicit_platform_not_found(tmp_path: Path):
    ws = tmp_path / "ws"
    src = _make_source_root(ws, "L50S程序", "l50s")
    module_dir = src / "通用" / "手控UI"
    _make_variant(module_dir, "v2.0")
    save_platform_config(src, [
        PlatformDefaults("标准单机芯", {"手控UI": "v2.0"}),
    ])

    ref = _make_ref(
        source_root_dir="L50S程序",
        module_rel="通用/手控UI",
        source_platform="不存在的平台",
    )
    res = resolve_shared_module(ref, ws)
    assert res.status == "missing"
    assert res.reason == "no_source_platform"


# ---------------------------------------------------------------------------
# 6. follow_default — 平台块存在但模块不在 defaults → missing, no_source_default
# ---------------------------------------------------------------------------

def test_follow_default_no_source_default(tmp_path: Path):
    ws = tmp_path / "ws"
    src = _make_source_root(ws, "L50S程序", "l50s")
    module_dir = src / "通用" / "手控UI"
    _make_variant(module_dir, "v2.0")
    save_platform_config(src, [
        PlatformDefaults("标准单机芯", {"主板程序": "v1.0"}),  # 没有 手控UI
    ])

    ref = _make_ref(
        source_root_dir="L50S程序",
        module_rel="通用/手控UI",
        source_platform="标准单机芯",
    )
    res = resolve_shared_module(ref, ws)
    assert res.status == "missing"
    assert res.reason == "no_source_default"


# ---------------------------------------------------------------------------
# 7. follow_default — 自动检测回落首块，但首块也无该模块 → no_source_default
# ---------------------------------------------------------------------------

def test_follow_default_auto_detect_falls_back_to_first_block(tmp_path: Path):
    ws = tmp_path / "ws"
    src = _make_source_root(ws, "L50S程序", "l50s")
    module_dir = src / "通用" / "手控UI"
    _make_variant(module_dir, "v2.0")
    save_platform_config(src, [
        PlatformDefaults("标准单机芯", {"主板程序": "v1.0"}),  # 无 手控UI
    ])

    ref = _make_ref(
        source_root_dir="L50S程序",
        module_rel="通用/手控UI",
        source_platform="",
    )
    res = resolve_shared_module(ref, ws)
    assert res.status == "missing"
    assert res.reason == "no_source_default"


# ---------------------------------------------------------------------------
# 8. follow_default — defaults 指向的变体目录不存在 → missing, path_not_found
# ---------------------------------------------------------------------------

def test_follow_default_variant_dir_not_found(tmp_path: Path):
    ws = tmp_path / "ws"
    src = _make_source_root(ws, "L50S程序", "l50s")
    module_dir = src / "通用" / "手控UI"
    module_dir.mkdir(parents=True, exist_ok=True)
    # 不创建 v99 目录
    save_platform_config(src, [
        PlatformDefaults("标准单机芯", {"手控UI": "v99"}),
    ])

    ref = _make_ref(
        source_root_dir="L50S程序",
        module_rel="通用/手控UI",
        source_platform="标准单机芯",
    )
    res = resolve_shared_module(ref, ws)
    assert res.status == "missing"
    assert res.reason == "path_not_found"


# ---------------------------------------------------------------------------
# 9. static 行为不退化（Phase B 基线）
# ---------------------------------------------------------------------------

def test_static_behavior_unchanged(tmp_path: Path):
    ws = tmp_path / "ws"
    src = _make_source_root(ws, "L50S程序", "l50s")
    module_dir = src / "通用" / "手控UI"
    v1 = _make_variant(module_dir, "v1.0")
    v2 = _make_variant(module_dir, "v2.0")

    ref = _make_ref(
        source_root_dir="L50S程序",
        module_rel="通用/手控UI",
        mode="static",
    )
    res = resolve_shared_module(ref, ws)
    assert res.status == "hit"
    assert res.resolved_path == module_dir.resolve()
    assert set(res.variants) == {v1.resolve(), v2.resolve()}


# ---------------------------------------------------------------------------
# 10. follow_default — model_id 不符仍返回 id_mismatch
# ---------------------------------------------------------------------------

def test_follow_default_id_mismatch(tmp_path: Path):
    ws = tmp_path / "ws"
    src = _make_source_root(ws, "L50S程序", "l50s-real")  # 盘上 id 是 l50s-real
    module_dir = src / "通用" / "手控UI"
    _make_variant(module_dir, "v2.0")
    save_platform_config(src, [PlatformDefaults("标准单机芯", {"手控UI": "v2.0"})])

    ref = SharedModuleRef(
        module_key="手控UI",
        source_model_id="l50s-wrong",   # 与盘上不符
        source_group="l50s-wrong",
        source_module="手控UI",
        source_relative_path="L50S程序/通用/手控UI",
        mode="follow_default",
        source_platform="标准单机芯",
    )
    res = resolve_shared_module(ref, ws)
    assert res.status == "missing"
    assert res.reason == "id_mismatch"


# ---------------------------------------------------------------------------
# 11. follow_default — 目录名（快捷键）与 catalog label（快捷键程序）匹配
# ---------------------------------------------------------------------------

def test_follow_default_catalog_label_vs_dir_name(tmp_path: Path):
    """默认键写「快捷键」但 source_module 是「快捷键程序」→ 规范化匹配命中。"""
    ws = tmp_path / "ws"
    src = _make_source_root(ws, "L50S程序", "l50s")
    module_dir = src / "通用" / "快捷键"
    _make_variant(module_dir, "量产_默认")
    # 键名用目录名「快捷键」
    save_platform_config(src, [
        PlatformDefaults("标准单机芯", {"快捷键": "量产_默认"}),
    ])

    ref = _make_ref(
        source_root_dir="L50S程序",
        module_rel="通用/快捷键",
        source_module="快捷键程序",   # catalog label
        source_platform="标准单机芯",
    )
    res = resolve_shared_module(ref, ws)
    assert res.status == "hit"
    assert res.resolved_path == (module_dir / "量产_默认").resolve()
