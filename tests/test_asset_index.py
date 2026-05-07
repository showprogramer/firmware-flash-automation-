from pathlib import Path

import pytest

from fwasset.core.asset_index import (
    SCHEMA_VERSION,
    AssetIndexError,
    delete_missing_assets,
    hide_item,
    init_asset_index,
    load_assets,
    load_hidden_items,
    load_scan_meta,
    prune_missing_hidden_items,
    query_assets,
    save_assets,
    schema_version,
    unhide_item,
)
from fwasset.core.types import FirmwareAsset


def make_asset(
    base: Path,
    *,
    firmware_type: str = "mainboard",
    model: str = "L36",
    directory_name: str = "mainboard_v1",
) -> FirmwareAsset:
    model_dir = base / f"{model} test"
    asset_dir = model_dir / directory_name
    return {
        "series": "L36",
        "firmware_type": firmware_type,  # type: ignore[typeddict-item]
        "firmware_label": "主板程序" if firmware_type == "mainboard" else "手控UI",
        "flash_mode": "tool_launch",
        "model": model,
        "version": "V1.0.0",
        "model_directory_name": model_dir.name,
        "model_directory_path": str(model_dir),
        "path": str(asset_dir),
        "directory_name": directory_name,
        "files": ["firmware.bin"],
        "modified_time": 123.0,
        "tool_name": "writer",
        "tool_path": "D:/tools/writer.exe",
        "tool_dir": "writer",
        "label": f"{model} V1.0.0 [{directory_name}]",
    }


def test_init_asset_index_creates_schema_and_version(tmp_path: Path):
    db_path = tmp_path / "fwasset.db"

    init_asset_index(db_path)

    assert db_path.exists()
    assert schema_version(db_path) == SCHEMA_VERSION


def test_save_and_load_assets_roundtrip(tmp_path: Path):
    db_path = tmp_path / "fwasset.db"
    asset = make_asset(tmp_path)

    save_assets([asset], str(tmp_path), db_path, scanned_at=1000.0)

    loaded = load_assets(db_path)
    assert loaded == [asset]
    assert load_scan_meta(db_path) == [
        {"root_dir": str(tmp_path), "last_scan_at": 1000.0, "schema_version": SCHEMA_VERSION}
    ]


def test_query_assets_by_keyword_and_type(tmp_path: Path):
    db_path = tmp_path / "fwasset.db"
    mainboard = make_asset(tmp_path, firmware_type="mainboard", model="L36", directory_name="mainboard_v1")
    handcontrol = make_asset(
        tmp_path,
        firmware_type="handcontrol_ui",
        model="L39",
        directory_name="handcontrol_v2",
    )
    save_assets([mainboard, handcontrol], str(tmp_path), db_path)

    assert [item["model"] for item in query_assets("L39", path=db_path)] == ["L39"]
    assert [item["firmware_type"] for item in query_assets(firmware_types=["mainboard"], path=db_path)] == ["mainboard"]
    assert query_assets("no-match", firmware_types=["mainboard"], path=db_path) == []


def test_delete_missing_assets_prunes_hidden_items(tmp_path: Path):
    db_path = tmp_path / "fwasset.db"
    keep_asset = make_asset(tmp_path, model="L36", directory_name="keep")
    removed_asset = make_asset(tmp_path, model="L39", directory_name="removed")
    save_assets([keep_asset, removed_asset], str(tmp_path), db_path)
    hide_item(removed_asset["path"], "asset", db_path)

    removed = delete_missing_assets([keep_asset["path"]], db_path)

    assert removed == 1
    assert [item["path"] for item in load_assets(db_path)] == [keep_asset["path"]]
    assert load_hidden_items(db_path) == {}


def test_hidden_items_persist_and_can_be_pruned(tmp_path: Path):
    db_path = tmp_path / "fwasset.db"
    asset = make_asset(tmp_path)
    save_assets([asset], str(tmp_path), db_path)

    hide_item(asset["model_directory_path"], "model_directory", db_path, created_at=100.0)
    assert load_hidden_items(db_path) == {asset["model_directory_path"]: "model_directory"}

    unhide_item(asset["model_directory_path"], db_path)
    assert load_hidden_items(db_path) == {}

    hide_item(asset["path"], "asset", db_path)
    save_assets([], str(tmp_path), db_path)
    assert prune_missing_hidden_items(db_path) == 0
    assert load_hidden_items(db_path) == {}


def test_schema_version_mismatch_raises_chinese_recovery_message(tmp_path: Path):
    db_path = tmp_path / "fwasset.db"
    init_asset_index(db_path)
    with pytest.raises(AssetIndexError, match="重新扫描生成"):
        import sqlite3

        with sqlite3.connect(db_path) as conn:
            conn.execute("UPDATE schema_meta SET value = '999' WHERE key = 'schema_version'")
        init_asset_index(db_path)
