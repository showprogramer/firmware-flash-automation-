"""Tests for SchemeWorkbenchModel: scheme module listing with platform fallback.

These tests build a fake L36-like directory tree on disk, scan it into a temp
SQLite index, then verify the view-model returns the correct custom + fallback
module lists. They are pure data-layer tests (no display), so not marked ui.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fwasset.core.asset_index import save_assets
from fwasset.core.file_scan import scan_firmware_assets
from fwasset.ui.view_models.scheme_workbench_model import SchemeWorkbenchModel


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture()
def l36_tree(tmp_path: Path) -> Path:
    """Build a minimal L36-shaped firmware tree.

    通用 has 主板程序 (量产_默认 default + 防夹功能 variant), a single-variant
    3D机芯版程序 and 腿部程序 (no _默认 subdir → dir itself is the asset).
    定制/西班牙 only ships 主板程序 → everything else should fall back.
    """
    root = tmp_path / "L36程序"

    # platform config at the model root
    _write(
        root / "平台配置.toml",
        "\n".join(
            [
                "[[platform]]",
                'name = "标准单机芯3D"',
                "[platform.defaults]",
                '"主板程序" = "量产_默认"',
                '"3D机芯版程序" = ""',
                '"腿部程序" = ""',
            ]
        ),
    )

    # 通用 modules
    _write(root / "通用" / "主板程序" / "量产_默认" / "YJ_3DMain_L36_V40.bin")
    _write(root / "通用" / "主板程序" / "防夹功能" / "YJ_3DMain_L36_V24.bin")
    _write(root / "通用" / "3D机芯版程序" / "YJ_ZD_3D_Core_L36_V20.mot")
    _write(root / "通用" / "腿部程序" / "Yj_Foot_L36_V5.hex")

    # 定制 scheme: only ships its own 主板程序
    scheme = root / "定制" / "西班牙"
    _write(scheme / "方案配置.toml", 'name = "西班牙"\nplatform = "标准单机芯3D"\n')
    _write(scheme / "主板程序" / "YJ_3DMain_L36_西班牙_V40.bin")

    return root


def _bind_model(root: Path, tmp_path: Path) -> SchemeWorkbenchModel:
    db = tmp_path / "index.db"
    assets, _errors = scan_firmware_assets(str(root))
    save_assets(assets, str(root), path=db)
    model = SchemeWorkbenchModel()
    model.bind(db, root)
    return model


def test_platform_config_is_loaded_from_scan_root(l36_tree: Path, tmp_path: Path) -> None:
    model = _bind_model(l36_tree, tmp_path)
    assert model._platforms, "平台配置.toml should be loaded from the scan root"
    names = {p.platform_name for p in model._platforms}
    assert "标准单机芯3D" in names


def test_scheme_includes_custom_exclusive_module(l36_tree: Path, tmp_path: Path) -> None:
    model = _bind_model(l36_tree, tmp_path)
    cards = model.get_scheme_modules("L36", "西班牙")
    exclusive = [c for c in cards if c.source_type == "custom_exclusive"]
    labels = {c.asset["firmware_label"] for c in exclusive}
    assert "主板程序" in labels


def test_scheme_falls_back_to_common_default_variant(l36_tree: Path, tmp_path: Path) -> None:
    """主板 is custom, but the scheme has no 3D机芯/腿部 → fall back to 通用."""
    model = _bind_model(l36_tree, tmp_path)
    cards = model.get_scheme_modules("L36", "西班牙")
    fallback = [c for c in cards if c.is_fallback]
    fb_labels = {c.asset["firmware_label"] for c in fallback}
    # single-variant modules with empty default_dir must still fall back.
    # NOTE: firmware_label comes from the catalog ("3D机芯板程序", 板), while the
    # 通用/ directory and 平台配置.toml key are "3D机芯版程序" (版) — the matcher
    # tolerates this discrepancy, so we assert on the catalog label here.
    assert "3D机芯板程序" in fb_labels
    assert "腿部程序" in fb_labels


def test_load_all_models_filters_filename_noise(tmp_path: Path) -> None:
    """A file whose name contains 'L50' under the L36 tree must not create an L50 model.

    The dropdown should reflect the structural model root (L36), not noisy
    per-file parsed models.
    """
    root = tmp_path / "L36程序"
    _write(root / "平台配置.toml", '[[platform]]\nname = "标准单机芯3D"\n[platform.defaults]\n')
    # 通用 mainboard whose filename mentions L50S → would parse model as L50S
    _write(root / "通用" / "主板程序" / "量产_默认" / "YJ_3DMain_L36_V40.bin")
    _write(root / "通用" / "主板程序" / "同L50S" / "YJ_3DMain_L50S_V9.bin")

    model = _bind_model(root, tmp_path)
    models = model.load_all_models()
    assert models == ["L36"], f"expected only structural model L36, got {models}"


def test_scheme_module_tree_groups_variants_under_one_row(tmp_path: Path) -> None:
    """手控UI 有多个变体时，应收成 ONE module row with children, not铺平."""
    root = tmp_path / "L36程序"
    _write(root / "平台配置.toml", '[[platform]]\nname = "标准单机芯3D"\n[platform.defaults]\n')
    # scheme with 3 手控UI variants + 1 主板
    scheme = root / "定制" / "马来" / "方案配置.toml"
    _write(scheme, 'name = "马来"\nplatform = "标准单机芯3D"\n')
    base = root / "定制" / "马来"
    _write(base / "主板程序" / "YJ_3DMain_L36_V40.bin")
    _write(base / "手控UI" / "L36 手控UI-A" / "a.rom")
    _write(base / "手控UI" / "L36 手控UI-A" / "a.pkg")
    _write(base / "手控UI" / "L36 手控UI-B" / "b.rom")
    _write(base / "手控UI" / "L36 手控UI-B" / "b.pkg")
    _write(base / "手控UI" / "L36 手控UI-C" / "c.rom")
    _write(base / "手控UI" / "L36 手控UI-C" / "c.pkg")

    model = _bind_model(root, tmp_path)
    tree = model.get_scheme_module_tree("L36", "马来")

    by_label = {row.label: row for row in tree}
    assert "主板程序" in by_label
    assert "手控UI" in by_label
    # 主板 single variant → 1 child (or treated as leaf)
    assert len(by_label["主板程序"].variants) == 1
    # 手控UI three variants grouped under ONE row
    assert len(by_label["手控UI"].variants) == 3


def test_scheme_module_tree_marks_custom_vs_common(l36_tree: Path, tmp_path: Path) -> None:
    """每个模块行应标明是 定制专属 还是 通用默认（不含'回源'字样）。"""
    model = _bind_model(l36_tree, tmp_path)
    tree = model.get_scheme_module_tree("L36", "西班牙")
    by_label = {row.label: row for row in tree}
    # 西班牙 ships 主板程序 → 定制专属
    assert by_label["主板程序"].source_kind == "custom"
    # 西班牙 lacks 3D机芯/腿部 → 通用默认
    assert by_label["3D机芯板程序"].source_kind == "common"
    # the literal word "回源" must never appear in any user-facing label
    for row in tree:
        assert "回源" not in row.source_label
        for v in row.variants:
            assert "回源" not in v.source_label


def test_covered_module_is_not_duplicated_by_fallback(l36_tree: Path, tmp_path: Path) -> None:
    """主板程序 is shipped by the scheme → it must NOT also appear as a fallback."""
    model = _bind_model(l36_tree, tmp_path)
    cards = model.get_scheme_modules("L36", "西班牙")
    mainboard_fallbacks = [
        c for c in cards if c.is_fallback and c.asset["firmware_label"] == "主板程序"
    ]
    assert mainboard_fallbacks == []


# ---------------------------------------------------------------------------
# Asset cache (P1-2) — single-bind, no-repeated-SQLite discipline
# ---------------------------------------------------------------------------

from typing import Any  # noqa: E402  (kept near its only use)


def _make_asset(
    *,
    path: str,
    model: str = "L36",
    category: str = "common",
    firmware_label: str = "主板程序",
    firmware_type: str = "mainboard",
    scheme_name: str = "",
    directory_name: str = "量产_默认",
    label: str = "",
    model_directory_path: str = "/scan/L36程序",
    platform: str = "",
) -> dict[str, Any]:
    return {
        "series": "",
        "model": model,
        "version": "V40",
        "firmware_type": firmware_type,
        "firmware_label": firmware_label,
        "flash_mode": "tool_launch",
        "usb_flow": "",
        "path": path,
        "directory_name": directory_name,
        "model_directory_name": "L36程序",
        "model_directory_path": model_directory_path,
        "files": ["f.bin"],
        "modified_time": 0.0,
        "tool_name": "",
        "tool_path": "",
        "tool_dir": "",
        "label": label or directory_name,
        "category": category,
        "platform": platform,
        "scheme_name": scheme_name,
        "scheme_path": "",
    }


class _CountingQueryAssets:
    """Counting replacement for fwasset.core.asset_index.query_assets.

    Records every call (so tests can assert the call count) and returns a
    pre-supplied asset list. Tests monkeypatch the module-level binding
    `fwasset.core.asset_index.query_assets` to this instance.
    """

    def __init__(self, assets: list[dict[str, Any]]) -> None:
        self.assets = assets
        self.calls: list[dict[str, Any]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append({"args": args, "kwargs": kwargs})
        # Apply the same filters the real query_assets does, so the model
        # exercises the same code path as in production.
        keyword = (kwargs.get("keyword") or "").lower().strip()
        category = kwargs.get("category") or ""
        scheme_name = kwargs.get("scheme_name") or ""
        out: list[dict[str, Any]] = []
        for a in self.assets:
            if category and a.get("category") != category:
                continue
            if scheme_name and a.get("scheme_name") != scheme_name:
                continue
            if keyword:
                hay = " ".join(
                    str(a.get(k, "")) for k in ("label", "directory_name", "firmware_label", "firmware_type", "version", "model", "series", "path")
                ).lower()
                if keyword not in hay:
                    continue
            out.append(a)
        return out


@pytest.fixture()
def cached_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[SchemeWorkbenchModel, _CountingQueryAssets]:
    """Build a SchemeWorkbenchModel whose query_assets is a counting fake.

    No real scan, no real SQLite — pure logic + cache discipline tests.
    """
    import fwasset.core.asset_index as asset_index_module
    import fwasset.ui.view_models.scheme_workbench_model as model_module

    assets = [
        # 通用 mainboard: 2 variants under 通用/主板程序/
        _make_asset(
            path="/scan/L36程序/通用/主板程序/量产_默认/YJ_3DMain_L36_V40.bin",
            directory_name="量产_默认",
            label="量产_默认",
        ),
        _make_asset(
            path="/scan/L36程序/通用/主板程序/防夹功能/YJ_3DMain_L36_V24.bin",
            directory_name="防夹功能",
            label="防夹功能",
        ),
        # 通用 single-variant module
        _make_asset(
            path="/scan/L36程序/通用/3D机芯版程序/YJ_ZD_3D_Core_L36_V20.mot",
            firmware_label="3D机芯板程序",
            directory_name="YJ_ZD_3D_Core_L36_V20",
            label="3D机芯版程序",
        ),
        # 定制 scheme: only ships its own mainboard
        _make_asset(
            path="/scan/L36程序/定制/西班牙/主板程序/YJ_3DMain_L36_西班牙_V40.bin",
            category="custom",
            scheme_name="西班牙",
            directory_name="西班牙_主板",
            label="西班牙_主板",
            platform="标准单机芯3D",
        ),
    ]
    counter = _CountingQueryAssets(assets)
    monkeypatch.setattr(asset_index_module, "query_assets", counter)
    # The model imports the symbol by name — patch that binding too.
    monkeypatch.setattr(model_module, "query_assets", counter)
    # Provide a minimal platform config so the 西班牙 fallback path still runs.
    from fwasset.core.platform_config import PlatformDefaults

    platform = PlatformDefaults(platform_name="标准单机芯3D", defaults={"3D机芯版程序": ""})
    monkeypatch.setattr(model_module, "load_platform_config", lambda _dir: [platform])

    model = SchemeWorkbenchModel()
    model.bind(tmp_path / "index.db", tmp_path / "L36程序")
    return model, counter


def test_bind_populates_cache_without_repeated_query_assets(cached_model) -> None:
    """bind() may call query_assets once to load the model-root map, but never
    on the hot path. After bind, view methods must NOT call query_assets again.
    """
    model, counter = cached_model
    initial_calls = len(counter.calls)

    # Build the sidebar tree and inspect modules — both should read from the cache.
    model.build_sidebar_tree("L36")
    model.get_common_modules("L36", "主板程序")
    model.get_scheme_modules("L36", "西班牙")
    model.get_all_modules("L36")
    model.load_all_models()

    assert len(counter.calls) == initial_calls, (
        f"view methods must not hit query_assets when cache is populated; "
        f"got {len(counter.calls) - initial_calls} extra calls"
    )


def test_cache_preserves_keyword_filter_semantics(cached_model) -> None:
    """The cache must NOT weaken the keyword filter. A user search must still
    exclude assets whose label/directory_name does not contain the keyword.
    """
    model, _counter = cached_model

    # 量产_默认 matches "量产" (part of label + directory_name).
    matches = model.get_common_modules("L36", "主板程序", keyword="量产")
    assert len(matches) == 1
    assert "量产" in matches[0].asset["label"]

    # No mainboard variant matches "xyzzy" — must return empty.
    assert model.get_common_modules("L36", "主板程序", keyword="xyzzy") == []


def test_cache_keyword_supports_space_split_AND_with_OR_per_token(cached_model) -> None:
    """BUG-2: the cache must replicate query_assets' 「空格分词 AND 跨字段 OR」 semantics.

    Examples:
        "主板 防夹"  → (any field contains "主板") AND (any field contains "防夹")
        "主板 xyzzy" → empty (second token matches nothing)
        "xyzzy"      → empty (single token matches nothing)

    The previous implementation did a single substring match on a joined
    field string, so "主板 防夹" required the literal string "主板 防夹" to
    appear in the haystack — effectively killing the flexible multi-word
    search.
    """
    model, _counter = cached_model

    # 主板 mainboard variants: 量产_默认 (label=量产_默认, no 防夹) and 防夹功能 (label=防夹功能, no 主板)
    # The first token "主板" matches the 主板 mainboard row; the second token
    # "防夹" then narrows to the variant whose directory_name contains 防夹.
    cards = model.get_common_modules("L36", "主板程序", keyword="主板 防夹")
    dirs = [c.asset["directory_name"] for c in cards]
    assert dirs == ["防夹功能"], (
        f"expected only 防夹功能 to match '主板 防夹', got {dirs!r}"
    )

    # Reverse: a token that doesn't match anything must yield an empty list,
    # not silently return everything (the bug we are fixing).
    assert model.get_common_modules("L36", "主板程序", keyword="主板 xyzzy") == []
    assert model.get_common_modules("L36", "主板程序", keyword="xyzzy") == []

    # Single token still works.
    only_zhujiao = model.get_common_modules("L36", "主板程序", keyword="主板")
    assert len(only_zhujiao) >= 1


def test_cache_keyword_matches_across_fields_not_just_directory_name(cached_model) -> None:
    """A user search for a version string like V40 must hit assets whose
    'version' field contains V40 — not only those whose directory_name does.
    This is the '跨字段' half of the contract.
    """
    model, _counter = cached_model
    # Both mainboard assets have version V40; the custom 西班牙 one too.
    cards = model.get_all_modules("L36", keyword="V40")
    assert len(cards) >= 1
    for c in cards:
        assert "V40" in str(c.asset.get("version", "")).upper()


def test_cache_preserves_scheme_fallback_behavior(cached_model) -> None:
    """The 西班牙 scheme ships only 主板程序; 3D机芯 must still come from 通用
    via the platform-config fallback. Caching must not break this.
    """
    model, _counter = cached_model
    cards = model.get_scheme_modules("L36", "西班牙")
    by_label: dict[str, list] = {}
    for c in cards:
        by_label.setdefault(c.asset["firmware_label"], []).append(c)

    assert "主板程序" in by_label
    assert "3D机芯板程序" in by_label
    # 3D机芯 should be a fallback (no _默认 directory but platform_config
    # covered it).
    assert by_label["3D机芯板程序"][0].is_fallback is True
    # 主板 must be 定制专属, not fallback.
    assert all(c.source_type == "custom_exclusive" for c in by_label["主板程序"])
    by_label: dict[str, list] = {}
    for c in cards:
        by_label.setdefault(c.asset["firmware_label"], []).append(c)

    assert "主板程序" in by_label
    assert "3D机芯板程序" in by_label
    # 3D机芯 should be a fallback (no _默认 directory but platform_config
    # covered it).
    assert by_label["3D机芯板程序"][0].is_fallback is True
    # 主板 must be 定制专属, not fallback.
    assert all(c.source_type == "custom_exclusive" for c in by_label["主板程序"])


def test_common_module_cards_carry_source_kind_common(cached_model) -> None:
    """BUG-1: a 通用 mainboard variant must report source_kind='common' so the
    workbench can mark it 通用默认 — not 定制专属.

    The previous code inferred source_kind from is_fallback only, so any
    non-fallback card (which all 通用 cards are) was mis-labeled as custom.
    """
    model, _counter = cached_model
    cards = model.get_common_modules("L36", "主板程序")
    assert cards, "fixture should yield at least one mainboard card"
    for c in cards:
        assert getattr(c, "source_kind", None) == "common", (
            f"mainboard variant {c.asset.get('directory_name')!r} should be "
            f"common but got source_kind={getattr(c, 'source_kind', None)!r}"
        )


def test_scheme_module_tree_marks_common_assets_as_common_default(cached_model) -> None:
    """BUG-1: when viewing a 西班牙 scheme that ships its own 主板, the OTHER
    mainboard variants under 通用 (防夹功能, 量产_默认 etc.) shown by get_all_modules
    must be tagged 通用默认 — never 定制专属.

    The test is end-to-end through the public method that the UI consumes.
    """
    model, _counter = cached_model
    all_cards = model.get_all_modules("L36")
    common_only = [c for c in all_cards if c.source_type.startswith("common_")]
    assert common_only, "fixture should yield common cards"
    for c in common_only:
        assert c.source_kind == "common", (
            f"common card {c.asset.get('directory_name')!r} leaked into custom: "
            f"source_kind={c.source_kind!r} source_type={c.source_type!r}"
        )


def test_unbound_model_falls_back_to_query_assets(monkeypatch: pytest.MonkeyPatch) -> None:
    """If someone calls a view method before bind() (or with an empty cache),
    the model must still work by going to the DB. This protects against the
    'cache missed' regression where the view would silently return empty.
    """
    import fwasset.core.asset_index as asset_index_module
    import fwasset.ui.view_models.scheme_workbench_model as model_module

    assets = [
        _make_asset(
            path="/scan/X/通用/主板程序/量产_默认/f.bin",
            model="X",
            directory_name="量产_默认",
        )
    ]
    counter = _CountingQueryAssets(assets)
    monkeypatch.setattr(asset_index_module, "query_assets", counter)
    monkeypatch.setattr(model_module, "query_assets", counter)

    model = SchemeWorkbenchModel()  # never bound
    tree = model.build_sidebar_tree("X")
    assert tree["common"] == {"主板程序": 1}
    assert counter.calls, "unbound model must hit query_assets to stay correct"


def test_cache_invalidates_on_rebind(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Calling bind() again must reload the cache (e.g. after a rescan added
    new assets). A stale cache from a previous bind is a silent bug — a
    rescan would not show up in the UI.
    """
    import fwasset.core.asset_index as asset_index_module
    import fwasset.ui.view_models.scheme_workbench_model as model_module

    first_assets = [_make_asset(path="/scan/L36程序/通用/主板程序/量产_默认/f.bin")]
    second_assets = first_assets + [
        _make_asset(
            path="/scan/L36程序/通用/语音程序/默认/v.bin",
            firmware_label="语音程序",
            directory_name="默认",
        )
    ]

    first = _CountingQueryAssets(first_assets)
    second = _CountingQueryAssets(second_assets)

    # Initial bind uses the first counter.
    monkeypatch.setattr(asset_index_module, "query_assets", first)
    monkeypatch.setattr(model_module, "query_assets", first)
    monkeypatch.setattr(model_module, "load_platform_config", lambda _dir: [])

    model = SchemeWorkbenchModel()
    model.bind(tmp_path / "index.db", tmp_path / "L36程序")
    assert "语音程序" not in model.build_sidebar_tree("L36")["common"]

    # Rebind against a new DB that has the new asset.
    monkeypatch.setattr(asset_index_module, "query_assets", second)
    monkeypatch.setattr(model_module, "query_assets", second)
    model.bind(tmp_path / "index2.db", tmp_path / "L36程序")
    assert "语音程序" in model.build_sidebar_tree("L36")["common"]
