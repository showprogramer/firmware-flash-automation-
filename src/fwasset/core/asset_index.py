from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Iterable, Literal

from fwasset.core.settings import ASSET_INDEX_PATH
from fwasset.core.sort_config import SortKey, apply_sort
from fwasset.core.types import FirmwareAsset


SCHEMA_VERSION = 1
HiddenItemType = Literal["model_directory", "firmware_type", "asset"]


class AssetIndexError(RuntimeError):
    """Raised when the local SQLite index cannot be opened or migrated."""


def default_index_path() -> Path:
    return ASSET_INDEX_PATH


def _db_path(path: str | Path | None = None) -> Path:
    return Path(path) if path is not None else default_index_path()


def connect_asset_index(path: str | Path | None = None) -> sqlite3.Connection:
    db_path = _db_path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.DatabaseError as exc:
        raise AssetIndexError(f"本地资产索引无法打开，请重新扫描生成：{exc}") from exc


def init_asset_index(path: str | Path | None = None) -> None:
    try:
        with connect_asset_index(path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS assets (
                    path TEXT PRIMARY KEY,
                    series TEXT NOT NULL,
                    model TEXT NOT NULL,
                    model_directory_name TEXT NOT NULL,
                    model_directory_path TEXT NOT NULL,
                    firmware_type TEXT NOT NULL,
                    firmware_label TEXT NOT NULL,
                    flash_mode TEXT NOT NULL,
                    version TEXT NOT NULL,
                    directory_name TEXT NOT NULL,
                    files_json TEXT NOT NULL,
                    modified_time REAL NOT NULL,
                    scanned_at REAL NOT NULL,
                    tool_name TEXT NOT NULL,
                    tool_path TEXT NOT NULL,
                    tool_dir TEXT NOT NULL,
                    label TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(firmware_type);
                CREATE INDEX IF NOT EXISTS idx_assets_model ON assets(model);
                CREATE INDEX IF NOT EXISTS idx_assets_directory ON assets(model_directory_path);
                CREATE TABLE IF NOT EXISTS hidden_items (
                    path TEXT PRIMARY KEY,
                    hide_type TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS scan_meta (
                    root_dir TEXT PRIMARY KEY,
                    last_scan_at REAL NOT NULL,
                    schema_version INTEGER NOT NULL
                );
                """
            )
            current = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
            if current is None:
                conn.execute(
                    "INSERT INTO schema_meta(key, value) VALUES('schema_version', ?)",
                    (str(SCHEMA_VERSION),),
                )
                return
            if int(current["value"]) != SCHEMA_VERSION:
                raise AssetIndexError(
                    f"本地资产索引版本不兼容：当前 {current['value']}，需要 {SCHEMA_VERSION}。请重新扫描生成。"
                )
    except sqlite3.DatabaseError as exc:
        raise AssetIndexError(f"本地资产索引损坏，请重新扫描生成：{exc}") from exc


def schema_version(path: str | Path | None = None) -> int:
    init_asset_index(path)
    with connect_asset_index(path) as conn:
        row = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
        return int(row["value"])


def save_assets(
    assets: Iterable[FirmwareAsset],
    root_dir: str,
    path: str | Path | None = None,
    scanned_at: float | None = None,
) -> None:
    init_asset_index(path)
    now = float(scanned_at if scanned_at is not None else time.time())
    asset_rows = [_asset_to_row(asset, now) for asset in assets]
    with connect_asset_index(path) as conn:
        conn.execute("DELETE FROM assets")
        conn.executemany(
            """
            INSERT INTO assets (
                path, series, model, model_directory_name, model_directory_path,
                firmware_type, firmware_label, flash_mode, version, directory_name,
                files_json, modified_time, scanned_at, tool_name, tool_path, tool_dir, label
            )
            VALUES (
                :path, :series, :model, :model_directory_name, :model_directory_path,
                :firmware_type, :firmware_label, :flash_mode, :version, :directory_name,
                :files_json, :modified_time, :scanned_at, :tool_name, :tool_path, :tool_dir, :label
            )
            """,
            asset_rows,
        )
        conn.execute(
            """
            INSERT INTO scan_meta(root_dir, last_scan_at, schema_version)
            VALUES(?, ?, ?)
            ON CONFLICT(root_dir) DO UPDATE SET
                last_scan_at = excluded.last_scan_at,
                schema_version = excluded.schema_version
            """,
            (str(root_dir), now, SCHEMA_VERSION),
        )
        prune_missing_hidden_items(conn=conn)


def load_assets(path: str | Path | None = None) -> list[FirmwareAsset]:
    init_asset_index(path)
    with connect_asset_index(path) as conn:
        rows = conn.execute("SELECT * FROM assets ORDER BY path, firmware_type").fetchall()
        return [_row_to_asset(row) for row in rows]


def count_assets(path: str | Path | None = None) -> int:
    init_asset_index(path)
    with connect_asset_index(path) as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM assets").fetchone()
        return int(row["count"])


def query_assets(
    keyword: str = "",
    firmware_types: Iterable[str] | None = None,
    path: str | Path | None = None,
    sort_key: SortKey | str = SortKey.PATH,
    ascending: bool = True,
) -> list[FirmwareAsset]:
    init_asset_index(path)
    clauses: list[str] = []
    params: list[str] = []
    selected_types = [str(item) for item in (firmware_types or []) if str(item).strip()]
    if selected_types:
        placeholders = ", ".join("?" for _ in selected_types)
        clauses.append(f"firmware_type IN ({placeholders})")
        params.extend(selected_types)
    if keyword.strip():
        pattern = f"%{keyword.strip().lower()}%"
        clauses.append(
            """(
                lower(series) LIKE ?
                OR lower(model) LIKE ?
                OR lower(version) LIKE ?
                OR lower(firmware_label) LIKE ?
                OR lower(directory_name) LIKE ?
                OR lower(model_directory_name) LIKE ?
                OR lower(path) LIKE ?
                OR lower(flash_mode) LIKE ?
            )"""
        )
        params.extend([pattern] * 8)
    sql = "SELECT * FROM assets"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY path, firmware_type"
    with connect_asset_index(path) as conn:
        assets = [_row_to_asset(row) for row in conn.execute(sql, params).fetchall()]
    try:
        selected_sort_key = SortKey(sort_key)
    except ValueError:
        selected_sort_key = SortKey.PATH
    return apply_sort(assets, sort_key=selected_sort_key, ascending=ascending)


def delete_missing_assets(existing_paths: Iterable[str], path: str | Path | None = None) -> int:
    init_asset_index(path)
    keep = {str(item) for item in existing_paths}
    with connect_asset_index(path) as conn:
        rows = conn.execute("SELECT path FROM assets").fetchall()
        removed = 0
        for row in rows:
            asset_path = str(row["path"])
            if asset_path in keep:
                continue
            conn.execute("DELETE FROM assets WHERE path = ?", (asset_path,))
            removed += 1
        prune_missing_hidden_items(conn=conn)
        return removed


def hide_item(
    item_path: str,
    hide_type: HiddenItemType = "asset",
    path: str | Path | None = None,
    created_at: float | None = None,
) -> None:
    init_asset_index(path)
    now = float(created_at if created_at is not None else time.time())
    with connect_asset_index(path) as conn:
        conn.execute(
            """
            INSERT INTO hidden_items(path, hide_type, created_at)
            VALUES(?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                hide_type = excluded.hide_type,
                created_at = excluded.created_at
            """,
            (str(item_path), hide_type, now),
        )


def unhide_item(item_path: str, path: str | Path | None = None) -> None:
    init_asset_index(path)
    with connect_asset_index(path) as conn:
        conn.execute("DELETE FROM hidden_items WHERE path = ?", (str(item_path),))


def load_hidden_items(path: str | Path | None = None) -> dict[str, str]:
    init_asset_index(path)
    with connect_asset_index(path) as conn:
        rows = conn.execute("SELECT path, hide_type FROM hidden_items ORDER BY path").fetchall()
        return {str(row["path"]): str(row["hide_type"]) for row in rows}


def prune_missing_hidden_items(
    path: str | Path | None = None,
    conn: sqlite3.Connection | None = None,
) -> int:
    close_conn = False
    if conn is None:
        init_asset_index(path)
        conn = connect_asset_index(path)
        close_conn = True
    try:
        asset_paths = {str(row["path"]) for row in conn.execute("SELECT path FROM assets").fetchall()}
        model_paths = {
            str(row["model_directory_path"])
            for row in conn.execute("SELECT DISTINCT model_directory_path FROM assets").fetchall()
        }
        hidden_rows = conn.execute("SELECT path, hide_type FROM hidden_items").fetchall()
        removed = 0
        for row in hidden_rows:
            item_path = str(row["path"])
            hide_type = str(row["hide_type"])
            if hide_type == "asset":
                exists = item_path in asset_paths
            elif hide_type == "model_directory":
                exists = item_path in model_paths
            else:
                exists = any(asset_path.startswith(item_path) for asset_path in asset_paths)
            if exists:
                continue
            conn.execute("DELETE FROM hidden_items WHERE path = ?", (item_path,))
            removed += 1
        if close_conn:
            conn.commit()
        return removed
    finally:
        if close_conn:
            conn.close()


def load_scan_meta(path: str | Path | None = None) -> list[dict[str, float | int | str]]:
    init_asset_index(path)
    with connect_asset_index(path) as conn:
        rows = conn.execute(
            "SELECT root_dir, last_scan_at, schema_version FROM scan_meta ORDER BY last_scan_at DESC"
        ).fetchall()
        return [
            {
                "root_dir": str(row["root_dir"]),
                "last_scan_at": float(row["last_scan_at"]),
                "schema_version": int(row["schema_version"]),
            }
            for row in rows
        ]


def _asset_to_row(asset: FirmwareAsset, scanned_at: float) -> dict[str, object]:
    return {
        "path": str(asset.get("path", "")),
        "series": str(asset.get("series", "")),
        "model": str(asset.get("model", "")),
        "model_directory_name": str(asset.get("model_directory_name", "")),
        "model_directory_path": str(asset.get("model_directory_path", "")),
        "firmware_type": str(asset.get("firmware_type", "")),
        "firmware_label": str(asset.get("firmware_label", "")),
        "flash_mode": str(asset.get("flash_mode", "")),
        "version": str(asset.get("version", "")),
        "directory_name": str(asset.get("directory_name", "")),
        "files_json": json.dumps(list(asset.get("files", [])), ensure_ascii=False),
        "modified_time": float(asset.get("modified_time", 0) or 0),
        "scanned_at": scanned_at,
        "tool_name": str(asset.get("tool_name", "")),
        "tool_path": str(asset.get("tool_path", "")),
        "tool_dir": str(asset.get("tool_dir", "")),
        "label": str(asset.get("label", "")),
    }


def _row_to_asset(row: sqlite3.Row) -> FirmwareAsset:
    try:
        files = json.loads(str(row["files_json"]))
    except json.JSONDecodeError:
        files = []
    if not isinstance(files, list):
        files = []
    return {
        "series": str(row["series"]),
        "firmware_type": str(row["firmware_type"]),  # type: ignore[typeddict-item]
        "firmware_label": str(row["firmware_label"]),
        "flash_mode": str(row["flash_mode"]),  # type: ignore[typeddict-item]
        "model": str(row["model"]),
        "version": str(row["version"]),
        "model_directory_name": str(row["model_directory_name"]),
        "model_directory_path": str(row["model_directory_path"]),
        "path": str(row["path"]),
        "directory_name": str(row["directory_name"]),
        "files": [str(item) for item in files],
        "modified_time": float(row["modified_time"]),
        "tool_name": str(row["tool_name"]),
        "tool_path": str(row["tool_path"]),
        "tool_dir": str(row["tool_dir"]),
        "label": str(row["label"]),
    }
