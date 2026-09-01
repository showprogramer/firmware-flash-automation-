import os
import re
import threading
from pathlib import Path
from typing import Literal, cast

from fwasset.core.firmware_catalog import (
    DEFAULT_FIRMWARE_CATALOG_PATH,
    FirmwareTypeConfig,
    enabled_firmware_types,
)
from fwasset.core.path_guard import assert_within_workspace
from fwasset.core.scheme_config import discover_schemes, scheme_for_path
from fwasset.core.settings import (
    SCAN_EXCLUDE_DIR_KEYWORDS,
    SCAN_MODEL_PATTERNS,
    SCAN_PATH_MODEL_PATTERNS,
    SCAN_PATH_VERSION_PATTERNS,
    SCAN_PKG_EXTENSIONS,
    SCAN_ROM_EXTENSIONS,
    SCAN_VERSION_PATTERNS,
)
from fwasset.core.types import FirmwareAsset, HandcontrolFolder

# 通用/定制 的一级目录名
_COMMON_DIR = "通用"
_CUSTOM_DIR = "定制"
# 双机芯平台的专属子目录名（在通用区内部）
_DUAL_CORE_DIR = "双机芯-上3D-下2D"


def _match_first_group(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        try:
            match = re.search(pattern, text, re.IGNORECASE)
        except re.error:
            continue
        if match:
            return match.group(1)
    return ""


def _normalize_version(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text.upper() if text[:1].upper() == "V" else f"V{text}"


def _has_allowed_extension(filename: str, extensions: list[str]) -> bool:
    lower_name = filename.lower()
    return any(lower_name.endswith(ext) for ext in extensions)


def _is_excluded_dir(dirpath: str) -> bool:
    lower_path = str(dirpath or "").lower()
    return any(
        keyword and str(keyword).lower() in lower_path
        for keyword in SCAN_EXCLUDE_DIR_KEYWORDS
    )


def _files_match_extensions(filenames: list[str], extensions: list[str]) -> bool:
    normalized_exts = [ext.lower() for ext in extensions if str(ext).strip()]
    if not normalized_exts:
        return False
    for name in filenames:
        lower_name = name.lower()
        if any(lower_name.endswith(ext) for ext in normalized_exts):
            return True
    return False


def _match_catalog_type(
    dirpath: str, filenames: list[str], type_configs: list[FirmwareTypeConfig]
) -> FirmwareTypeConfig | None:
    lower_parts = [part.lower() for part in Path(dirpath).parts]
    for cfg in type_configs:
        keywords = [
            str(item).strip().lower()
            for item in cfg.get("dir_keywords", [])
            if str(item).strip()
        ]
        if cfg.get("key") == "handcontrol_ui":
            has_rom = _files_match_extensions(filenames, SCAN_ROM_EXTENSIONS)
            has_pkg = _files_match_extensions(filenames, SCAN_PKG_EXTENSIONS)
            if has_rom and has_pkg:
                return cfg
        if keywords and not any(
            keyword in part for keyword in keywords for part in lower_parts
        ):
            continue
        if not _files_match_extensions(filenames, cfg.get("file_extensions", [])):
            continue
        return cfg
    return None


def _extract_model_version(dirpath: str, filenames: list[str]) -> tuple[str, str]:
    for name in filenames:
        model, version = parse_rom_filename(name)
        if model or version:
            return model or guess_model_from_path(
                dirpath
            ), version or guess_version_from_path(dirpath)
    return guess_model_from_path(dirpath), guess_version_from_path(dirpath)


def guess_series_from_model_or_path(model: str, dirpath: str) -> str:
    """Infer series from model first, then path segments, using the [A-Z]+[0-9]+ prefix rule."""
    candidates = [str(model or "")]
    candidates.extend(reversed([str(part) for part in Path(dirpath).parts]))
    for candidate in candidates:
        match = re.search(r"([A-Za-z]+\d+)", candidate)
        if match:
            return match.group(1).upper()
    return "未知系列"


def _model_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _is_known_model(model: str) -> bool:
    token = _model_token(model)
    return bool(re.search(r"(?:[a-z]+\d|\d+[a-z])", token))


def _part_contains_model(part: str, model: str) -> bool:
    model_token = _model_token(model)
    if not model_token:
        return False
    return model_token in _model_token(part)


def _model_directory_for_asset(
    root_path: Path, folder_path: Path, model: str = "", firmware_type: str = ""
) -> Path:
    try:
        relative_parts = folder_path.relative_to(root_path).parts
        base_path = root_path
    except ValueError:
        relative_parts = folder_path.parts
        base_path = Path(folder_path.anchor)
    if not relative_parts:
        return folder_path
    if _is_known_model(model):
        candidate = base_path
        matches: list[Path] = []
        for part in relative_parts:
            candidate = Path(candidate) / part
            if _part_contains_model(part, model):
                matches.append(candidate)
        if matches:
            if firmware_type == "handcontrol_ui":
                return matches[-1]
            return matches[0]
        if firmware_type == "handcontrol_ui":
            return folder_path
        return root_path / relative_parts[0]
    return root_path / relative_parts[0]


def _prefer_handcontrol_directory_model(folder_path: Path, model: str) -> str:
    path_model = guess_model_from_path(str(folder_path))
    if not _is_known_model(path_model):
        return model
    if not _is_known_model(model) or _part_contains_model(folder_path.name, path_model):
        return path_model
    return model


def _require_scan_root(root_path: Path, label: str) -> None:
    if not root_path.exists():
        raise FileNotFoundError(f"扫描根目录不存在: {label}")
    if not root_path.is_dir():
        raise NotADirectoryError(f"扫描根目录不是目录: {label}")


def _load_scan_context(
    root_path: Path, catalog_path: str | Path | None
) -> tuple[list[FirmwareTypeConfig], list]:
    """加载固件类型目录配置与方案元数据（方案按工作区根发现）。"""
    type_configs = enabled_firmware_types(
        Path(catalog_path) if catalog_path else DEFAULT_FIRMWARE_CATALOG_PATH
    )
    return type_configs, discover_schemes(root_path)


def scan_firmware_assets(
    root: str,
    catalog_path: str | Path | None = None,
    last_scan_at: float | None = None,
    cancel_event: "threading.Event | None" = None,
) -> tuple[list[FirmwareAsset], list[str]]:
    """
    Scan root using catalog-configured directory keywords and file extensions.
    Returns recognized assets plus explicit directory read errors.

    If last_scan_at is provided, directories whose mtime is older than
    last_scan_at will be skipped (incremental mode).
    If cancel_event is provided, scanning can be interrupted by setting the event.
    """
    root_path = Path(root)
    _require_scan_root(root_path, root)
    type_configs, schemes = _load_scan_context(root_path, catalog_path)
    return _scan_assets(
        root_path, root_path, type_configs, schemes, last_scan_at, cancel_event
    )


def scan_firmware_subtree(
    workspace_root: str,
    subtree_root: str,
    catalog_path: str | Path | None = None,
    cancel_event: "threading.Event | None" = None,
) -> tuple[list[FirmwareAsset], list[str]]:
    """局部子树扫描（REVIEW-20260728 R3）：仅遍历 ``subtree_root``。

    - 归属推导（category/platform/scheme_name/scheme_path/model_directory）
      按 ``workspace_root`` 计算，必须与 :func:`scan_firmware_assets` 的
      全根扫描对同一路径给出字段级一致的结果——本函数与全根扫描共享同一
      推导实现（:func:`_scan_assets`），不得在调用方手写字段映射。
    - ``subtree_root`` 必须位于 ``workspace_root`` 之下（经路径守卫校验）；
      子树不存在返回空快照（支撑删除恢复），存在但不是目录则报错。
    - 不支持 ``last_scan_at`` 增量跳过：局部重建必须拿到该子树的完整快照。
    """
    ws_path = Path(workspace_root)
    _require_scan_root(ws_path, workspace_root)
    sub_path = Path(subtree_root)
    assert_within_workspace(sub_path, ws_path)
    if not sub_path.exists():
        return [], []
    if not sub_path.is_dir():
        raise NotADirectoryError(f"扫描子树不是目录: {subtree_root}")
    type_configs, schemes = _load_scan_context(ws_path, catalog_path)
    return _scan_assets(ws_path, sub_path, type_configs, schemes, None, cancel_event)


def _scan_assets(
    context_root: Path,
    walk_root: Path,
    type_configs: list[FirmwareTypeConfig],
    schemes: list,
    last_scan_at: float | None,
    cancel_event: "threading.Event | None",
) -> tuple[list[FirmwareAsset], list[str]]:
    """从 ``walk_root`` 遍历扫描，归属按 ``context_root`` 推导。"""
    root_path = context_root
    results: list[FirmwareAsset] = []
    errors: list[str] = []

    def _on_walk_error(exc: OSError) -> None:
        if exc.filename:
            errors.append(f"{exc.filename}: {exc.strerror}")
        else:
            errors.append(str(exc))

    for dirpath, dirnames, filenames in os.walk(walk_root, onerror=_on_walk_error):
        if cancel_event is not None and cancel_event.is_set():
            errors.append("扫描已被用户取消")
            break

        if last_scan_at is not None and dirpath != str(walk_root):
            try:
                dir_mtime = Path(dirpath).stat().st_mtime
                if dir_mtime < last_scan_at:
                    # 仅跳过本目录的资产匹配，**不**剪枝子树：父目录 mtime 旧
                    # 不代表子孙未更新（改深层文件常不抬祖先 mtime）。
                    continue
            except OSError:
                pass

        if _is_excluded_dir(dirpath):
            # 排除目录整棵子树可剪（排除语义是整枝不要，与 mtime 无关）
            dirnames[:] = []
            continue
        cfg = _match_catalog_type(dirpath, filenames, type_configs)
        if cfg is None:
            continue

        folder_path = Path(dirpath)
        model, version = _extract_model_version(dirpath, filenames)
        if str(cfg["key"]) == "handcontrol_ui":
            model = _prefer_handcontrol_directory_model(folder_path, model)
        model_directory = _model_directory_for_asset(
            root_path, folder_path, model, str(cfg["key"])
        )
        series = guess_series_from_model_or_path(model, str(model_directory))
        files = sorted(filenames)
        label = f"{model}  {version or '-'}  [{folder_path.name}]  {cfg['label']}"

        # --- 推断 category / platform / scheme ---
        category, platform, scheme_name, scheme_path = _infer_asset_context(
            root_path, folder_path, schemes
        )

        results.append(
            {
                "series": series,
                "firmware_type": cfg["key"],
                "firmware_label": cfg["label"],
                "flash_mode": cast(
                    Literal["auto_usb", "tool_launch", "manual_doc", "disabled"],
                    cfg["flash_mode"],
                ),
                "usb_flow": cfg.get("usb_flow", ""),
                "model": model,
                "version": version,
                "model_directory_name": model_directory.name,
                "model_directory_path": str(model_directory),
                "path": str(folder_path),
                "directory_name": folder_path.name,
                "files": files,
                "modified_time": folder_path.stat().st_mtime,
                "tool_name": cfg["tool_name"],
                "tool_path": cfg["tool_path"],
                "tool_dir": cfg.get("tool_dir", ""),
                "label": label,
                "category": cast(Literal["common", "custom", ""], category),
                "platform": platform,
                "scheme_name": scheme_name,
                "scheme_path": scheme_path,
            }
        )

    results.sort(key=lambda item: (item["path"], item["firmware_type"]))
    return results, errors


def _infer_asset_context(
    root_path: Path,
    folder_path: Path,
    schemes: list,
) -> tuple[str, str, str, str]:
    """
    根据资产路径推断 (category, platform, scheme_name, scheme_path)。

    规则：
    - 路径相对 root 中包含 '通用' 段 → category='common'
    - 路径相对 root 中包含 '定制' 段 → category='custom'，向 scheme_for_path 查询方案
    - 在 '通用/双机芯-上3D-下2D/' 下 → platform='双机芯-上3D-下2D'
    - 其他通用区 → platform=''
    - 旧目录（无法推断）→ 全部留空字符串（向后兼容）
    """
    try:
        rel_parts = folder_path.relative_to(root_path).parts
    except ValueError:
        return "", "", "", ""

    if not rel_parts:
        return "", "", "", ""

    # 查找路径中 通用/定制 段的位置，支持多级嵌套
    # 如根目录/型号目录/通用/... 或 根目录/通用/... 两种
    common_idx = None
    custom_idx = None
    for i, part in enumerate(rel_parts):
        if part == _COMMON_DIR:
            common_idx = i
            break
        if part == _CUSTOM_DIR:
            custom_idx = i
            break

    if common_idx is not None:
        # 在通用区
        category = "common"
        # 检查是否在双机芯专属子目录下
        platform = (
            _DUAL_CORE_DIR
            if (
                len(rel_parts) > common_idx + 1
                and rel_parts[common_idx + 1] == _DUAL_CORE_DIR
            )
            else ""
        )
        return category, platform, "", ""

    if custom_idx is not None:
        # 在定制区，查找所属方案
        category = "custom"
        scheme = scheme_for_path(schemes, folder_path)
        if scheme is not None:
            return category, scheme.platform, scheme.name, str(scheme.path)
        return category, "", "", ""

    # 旧目录结构（既不是 通用 也不是 定制），向后兼容留空
    return "", "", "", ""


def parse_rom_filename(name: str) -> tuple[str, str]:
    """
    Parse model and version from ROM filename using configurable regex rules.
    """
    name_no_ext = Path(name).stem

    model = _match_first_group(name_no_ext, SCAN_MODEL_PATTERNS).upper()
    version = _normalize_version(_match_first_group(name_no_ext, SCAN_VERSION_PATTERNS))

    return model, version


def guess_model_from_path(dirpath: str) -> str:
    """Guess model from path segments using configurable regex rules."""
    for part in reversed(Path(dirpath).parts):
        matched = _match_first_group(part, SCAN_PATH_MODEL_PATTERNS)
        if matched:
            return matched.upper()
    return "未知型号"


def guess_version_from_path(dirpath: str) -> str:
    """Guess version from folder name/path segments when ROM filename has no version."""
    for part in reversed(Path(dirpath).parts):
        matched = _match_first_group(part, SCAN_PATH_VERSION_PATTERNS)
        if matched:
            return _normalize_version(matched)
    return ""


def handcontrol_folders_from_assets(
    assets: list[FirmwareAsset],
) -> list[HandcontrolFolder]:
    """从已扫描资产派生手控文件夹列表（不再二次 os.walk）。"""
    results: list[HandcontrolFolder] = []
    for asset in assets:
        if asset.get("firmware_type") != "handcontrol_ui":
            continue
        rom_files = [
            name
            for name in asset.get("files", [])
            if _has_allowed_extension(name, SCAN_ROM_EXTENSIONS)
        ]
        pkg_files = [
            name
            for name in asset.get("files", [])
            if _has_allowed_extension(name, SCAN_PKG_EXTENSIONS)
        ]
        if not rom_files or not pkg_files:
            continue
        results.append(
            {
                "path": str(asset.get("path", "")),
                "rom_file": rom_files[0],
                "pkg_file": pkg_files[0],
                "model": str(asset.get("model", "")),
                "version": str(asset.get("version", "")),
                "label": (
                    f"{asset.get('model', '')}  {asset.get('version', '')}  "
                    f"[{Path(str(asset.get('path', ''))).name}]"
                ),
            }
        )
    results.sort(key=lambda x: x["path"])
    return results


def find_handcontrol_folders(root: str) -> list[HandcontrolFolder]:
    """
    Recursively scan root and find folders containing both configured ROM and PKG files.
    Priority: ROM filename -> folder/path fallback.
    """
    assets, _errors = scan_firmware_assets(root)
    return handcontrol_folders_from_assets(assets)
