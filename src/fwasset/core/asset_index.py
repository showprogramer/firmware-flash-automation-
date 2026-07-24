from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Iterable, Literal

from fwasset.core.settings import ASSET_INDEX_PATH
from fwasset.core.sort_config import SortKey, apply_sort
from fwasset.core.types import FirmwareAsset


SCHEMA_VERSION = 3
HiddenItemType = Literal["model_directory", "firmware_type", "asset"]

# 连接 busy 等待秒数。扫描写库（DELETE+INSERT）可能较长；默认 5s 易在
# 读路径（query/缓存加载）上提前抛 OperationalError。
CONNECT_TIMEOUT_SEC = 30.0

# ---------------------------------------------------------------------------
# 单工作区语义（非多根并存）
#
# 本索引一次只服务一个固件根目录（工作区）。真相源是整理后的目录树 + TOML；
# SQLite 是搜索/浏览缓存。全量扫描会用当前根的快照整库替换 assets，
# scan_meta 也只保留当前根一行。换根扫描 = 切换工作区，旧根资产不保留。
#
# 并发模型（单写者）：
# - 预期：同一库文件由本应用单进程使用；写主要在扫描（及未来 CRUD）线程，
#   读在 UI 查询路径。勿多开多个 fwasset 实例同时写同一 fwasset.db。
# - 连接 timeout 只缓解短暂锁等待，不替代单写者纪律。
#
# 未来应用内 CRUD 落地后，日常走行级写；全量 save_assets 退化为
# 首次导入 / 索引修复 / 强制对账的冷路径，语义仍是「当前工作区快照」。
# ---------------------------------------------------------------------------


class AssetIndexError(RuntimeError):
    """Raised when the local SQLite index cannot be opened or migrated."""


def default_index_path() -> Path:
    return ASSET_INDEX_PATH


def _db_path(path: str | Path | None = None) -> Path:
    return Path(path) if path is not None else default_index_path()


def connect_asset_index(path: str | Path | None = None) -> sqlite3.Connection:
    """打开本地资产索引连接。

    使用 :data:`CONNECT_TIMEOUT_SEC` 作为 busy timeout，减轻扫描写事务与
    并发读之间的短暂争用。仍假定单进程单写者（见模块顶部说明）。
    """
    db_path = _db_path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(db_path, timeout=CONNECT_TIMEOUT_SEC)
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
                    usb_flow TEXT NOT NULL DEFAULT '',
                    version TEXT NOT NULL,
                    directory_name TEXT NOT NULL,
                    files_json TEXT NOT NULL,
                    modified_time REAL NOT NULL,
                    scanned_at REAL NOT NULL,
                    tool_name TEXT NOT NULL,
                    tool_path TEXT NOT NULL,
                    tool_dir TEXT NOT NULL,
                    label TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    platform TEXT NOT NULL DEFAULT '',
                    scheme_name TEXT NOT NULL DEFAULT '',
                    scheme_path TEXT NOT NULL DEFAULT ''
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
                conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_category ON assets(category)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_platform ON assets(platform)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_scheme ON assets(scheme_name)")
                return
            current_version = int(current["value"])
            if current_version == 1:
                conn.execute("ALTER TABLE assets ADD COLUMN usb_flow TEXT NOT NULL DEFAULT ''")
                current_version = 2
                conn.execute(
                    "UPDATE schema_meta SET value = '2' WHERE key = 'schema_version'"
                )
            if current_version == 2:
                conn.execute("ALTER TABLE assets ADD COLUMN category TEXT NOT NULL DEFAULT ''")
                conn.execute("ALTER TABLE assets ADD COLUMN platform TEXT NOT NULL DEFAULT ''")
                conn.execute("ALTER TABLE assets ADD COLUMN scheme_name TEXT NOT NULL DEFAULT ''")
                conn.execute("ALTER TABLE assets ADD COLUMN scheme_path TEXT NOT NULL DEFAULT ''")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_category ON assets(category)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_platform ON assets(platform)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_scheme ON assets(scheme_name)")
                current_version = 3
                conn.execute(
                    "UPDATE schema_meta SET value = '3' WHERE key = 'schema_version'"
                )
            if current_version != SCHEMA_VERSION:
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
    """用当前工作区根目录的全量快照重建索引（单根语义）。

    - ``DELETE FROM assets`` 后写入 ``assets``：整库替换，不是按根增量合并。
    - ``scan_meta`` 先清空再写入当前 ``root_dir`` 一行：不保留历史根，避免
      「多行 scan_meta + 单表 assets」被误读成多根并存。
    - 换根再次扫描会丢弃上一工作区的资产与 meta，这是切换工作区，不是 bug。
    """
    init_asset_index(path)
    now = float(scanned_at if scanned_at is not None else time.time())
    asset_rows = [_asset_to_row(asset, now) for asset in assets]
    with connect_asset_index(path) as conn:
        # 单工作区：当前根的快照覆盖整库（见模块顶部注释）。
        conn.execute("DELETE FROM assets")
        conn.executemany(
            """
            INSERT INTO assets (
                path, series, model, model_directory_name, model_directory_path,
                firmware_type, firmware_label, flash_mode, usb_flow, version, directory_name,
                files_json, modified_time, scanned_at, tool_name, tool_path, tool_dir, label,
                category, platform, scheme_name, scheme_path
            )
            VALUES (
                :path, :series, :model, :model_directory_name, :model_directory_path,
                :firmware_type, :firmware_label, :flash_mode, :usb_flow, :version, :directory_name,
                :files_json, :modified_time, :scanned_at, :tool_name, :tool_path, :tool_dir, :label,
                :category, :platform, :scheme_name, :scheme_path
            )
            """,
            asset_rows,
        )
        # 只保留当前工作区一行，清掉历史 root_dir（旧库可能多行）。
        conn.execute("DELETE FROM scan_meta")
        conn.execute(
            """
            INSERT INTO scan_meta(root_dir, last_scan_at, schema_version)
            VALUES(?, ?, ?)
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
    category: str = "",
    scheme_name: str = "",
    platform: str = "",
) -> list[FirmwareAsset]:
    init_asset_index(path)
    clauses: list[str] = []
    params: list[str] = []
    selected_types = [str(item) for item in (firmware_types or []) if str(item).strip()]
    if selected_types:
        placeholders = ", ".join("?" for _ in selected_types)
        clauses.append(f"firmware_type IN ({placeholders})")
        params.extend(selected_types)
    if category.strip():
        clauses.append("category = ?")
        params.append(category.strip())
    if platform.strip():
        clauses.append("platform = ?")
        params.append(platform.strip())
    if scheme_name.strip():
        clauses.append("lower(scheme_name) LIKE ?")
        params.append(f"%{scheme_name.strip().lower()}%")
    # 空格分词：每个词都要命中（任意字段 OR），词间 AND。
    # 这样 "手控 V13" = (任意字段含"手控") AND (任意字段含"V13")，
    # 解决"既想搜模块、又想搜版本号"。单个词时退化为原来的跨字段模糊。
    keyword_fields = (
        "series",
        "model",
        "version",
        "firmware_label",
        "directory_name",
        "model_directory_name",
        "path",
        "flash_mode",
        "scheme_name",
        "platform",
    )
    for token in keyword.split():
        pattern = f"%{token.lower()}%"
        ors = " OR ".join(f"lower({field}) LIKE ?" for field in keyword_fields)
        clauses.append(f"({ors})")
        params.extend([pattern] * len(keyword_fields))
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
    """返回工作区扫描元数据。

    正常经 :func:`save_assets` 写入后至多一行（当前工作区根）。
    列表形式保留兼容；调用方取 ``[0]`` 即当前根。
    未清理的旧库可能短暂多行，按 ``last_scan_at DESC`` 排序，首条为最近一次。
    """
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


def active_workspace_root(path: str | Path | None = None) -> str | None:
    """当前工作区根目录；无扫描记录时返回 ``None``。"""
    meta = load_scan_meta(path)
    if not meta:
        return None
    root = str(meta[0].get("root_dir", "")).strip()
    return root or None


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
        "usb_flow": str(asset.get("usb_flow", "")),
        "version": str(asset.get("version", "")),
        "directory_name": str(asset.get("directory_name", "")),
        "files_json": json.dumps(list(asset.get("files", [])), ensure_ascii=False),
        "modified_time": float(asset.get("modified_time", 0) or 0),
        "scanned_at": scanned_at,
        "tool_name": str(asset.get("tool_name", "")),
        "tool_path": str(asset.get("tool_path", "")),
        "tool_dir": str(asset.get("tool_dir", "")),
        "label": str(asset.get("label", "")),
        "category": str(asset.get("category", "")),
        "platform": str(asset.get("platform", "")),
        "scheme_name": str(asset.get("scheme_name", "")),
        "scheme_path": str(asset.get("scheme_path", "")),
    }


def _row_to_asset(row: sqlite3.Row) -> FirmwareAsset:
    try:
        files = json.loads(str(row["files_json"]))
    except json.JSONDecodeError:
        files = []
    if not isinstance(files, list):
        files = []
    keys = row.keys()
    return {
        "series": str(row["series"]),
        "firmware_type": str(row["firmware_type"]),  # type: ignore[typeddict-item]
        "firmware_label": str(row["firmware_label"]),
        "flash_mode": str(row["flash_mode"]),  # type: ignore[typeddict-item]
        "usb_flow": str(row["usb_flow"]),  # type: ignore[typeddict-item]
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
        "category": str(row["category"]) if "category" in keys else "",
        "platform": str(row["platform"]) if "platform" in keys else "",
        "scheme_name": str(row["scheme_name"]) if "scheme_name" in keys else "",
        "scheme_path": str(row["scheme_path"]) if "scheme_path" in keys else "",
    }
