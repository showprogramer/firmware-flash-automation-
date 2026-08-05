"""C2：set_shared_module service 扩展 mode / source_platform 参数。"""

from __future__ import annotations

from pathlib import Path

from fwasset.core.model_config import load_shared_modules, save_model_id
from fwasset.core.platform_config import PlatformDefaults, save_platform_config
from fwasset.core.services.shared_module_service import set_shared_module
from fwasset.core.types import FirmwareAsset

# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------


def _make_asset(
    path: Path, *, firmware_label: str = "手控UI", model: str = "L50S"
) -> FirmwareAsset:
    path.mkdir(parents=True, exist_ok=True)
    (path / "fw.bin").write_bytes(b"X")
    return {
        "series": model,
        "model": model,
        "version": "V1.0",
        "firmware_type": "handcontrol_ui",  # type: ignore[typeddict-item]
        "firmware_label": firmware_label,
        "flash_mode": "tool_launch",
        "usb_flow": "",
        "model_directory_name": path.parents[1].name,
        "model_directory_path": str(path.parents[1]),
        "path": str(path),
        "directory_name": path.name,
        "files": ["fw.bin"],
        "modified_time": 0.0,
        "tool_name": "t",
        "tool_path": "t.exe",
        "tool_dir": "t",
        "label": "lbl",
        "category": "common",
        "platform": "",
        "scheme_name": "",
        "scheme_path": "",
    }


def _setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    """ws / L50S程序（src）/ 双机芯程序（tgt）"""
    ws = tmp_path / "ws"
    src = ws / "L50S程序"
    tgt = ws / "双机芯程序"
    src.mkdir(parents=True, exist_ok=True)
    tgt.mkdir(parents=True, exist_ok=True)
    save_model_id(src, "l50s")
    return ws, src, tgt


def _setup_with_platform(tmp_path: Path) -> tuple[Path, Path, Path]:
    """同上，并写入平台配置。"""
    ws, src, tgt = _setup(tmp_path)
    save_platform_config(src, [PlatformDefaults("标准单机芯", {})])
    return ws, src, tgt


# ---------------------------------------------------------------------------
# 1. follow_default — 多变体资产存模块目录（parent.name 非 通用/定制）
# ---------------------------------------------------------------------------


def test_follow_default_stores_module_dir(tmp_path: Path):
    ws, src, tgt = _setup_with_platform(tmp_path)
    variant = src / "通用" / "手控UI" / "v2.0"
    asset = _make_asset(variant)

    result = set_shared_module(tgt, asset, ws, mode="follow_default")
    assert result["ok"] is True, result["message"]

    refs = load_shared_modules(tgt)
    assert refs[0].source_relative_path == "L50S程序/通用/手控UI"
    assert refs[0].mode == "follow_default"


# ---------------------------------------------------------------------------
# 2. follow_default — 唯一变体（parent.name == "通用"），资产路径本身是模块目录
# ---------------------------------------------------------------------------


def test_follow_default_leaf_asset_stores_asset_path(tmp_path: Path):
    ws, src, tgt = _setup_with_platform(tmp_path)
    module_dir = src / "通用" / "语音程序"
    asset = _make_asset(module_dir, firmware_label="语音程序")

    result = set_shared_module(tgt, asset, ws, mode="follow_default")
    assert result["ok"] is True, result["message"]

    refs = load_shared_modules(tgt)
    assert refs[0].source_relative_path == "L50S程序/通用/语音程序"
    assert refs[0].mode == "follow_default"


# ---------------------------------------------------------------------------
# 3. follow_default + 有效 source_platform → ok，写入 source_platform
# ---------------------------------------------------------------------------


def test_follow_default_with_valid_source_platform(tmp_path: Path):
    ws, src, tgt = _setup(tmp_path)
    variant = src / "通用" / "手控UI" / "v2.0"
    asset = _make_asset(variant)
    save_platform_config(src, [PlatformDefaults("标准单机芯", {"手控UI": "v2.0"})])

    result = set_shared_module(
        tgt, asset, ws, mode="follow_default", source_platform="标准单机芯"
    )
    assert result["ok"] is True, result["message"]

    refs = load_shared_modules(tgt)
    assert refs[0].source_platform == "标准单机芯"


# ---------------------------------------------------------------------------
# 4. follow_default + source_platform 不存在于源平台配置 → invalid_args
# ---------------------------------------------------------------------------


def test_follow_default_invalid_source_platform(tmp_path: Path):
    ws, src, tgt = _setup(tmp_path)
    variant = src / "通用" / "手控UI" / "v2.0"
    asset = _make_asset(variant)
    save_platform_config(src, [PlatformDefaults("标准单机芯", {})])

    result = set_shared_module(
        tgt, asset, ws, mode="follow_default", source_platform="不存在的平台"
    )
    assert result["ok"] is False
    assert result["code"] == "invalid_args"


# ---------------------------------------------------------------------------
# 5. follow_default + 有平台配置 + source_platform 为空 → 登记成功（自动检测）
# ---------------------------------------------------------------------------


def test_follow_default_auto_detect_with_platform_config(tmp_path: Path):
    ws, src, tgt = _setup_with_platform(tmp_path)
    variant = src / "通用" / "手控UI" / "v2.0"
    asset = _make_asset(variant)

    result = set_shared_module(
        tgt, asset, ws, mode="follow_default", source_platform=""
    )
    assert result["ok"] is True


# ---------------------------------------------------------------------------
# 5b. follow_default + 无平台配置 + source_platform 为空 → no_platform_config
# ---------------------------------------------------------------------------


def test_follow_default_no_platform_config_rejected(tmp_path: Path):
    ws, src, tgt = _setup(tmp_path)  # 无平台配置
    variant = src / "通用" / "手控UI" / "v2.0"
    asset = _make_asset(variant)

    result = set_shared_module(
        tgt, asset, ws, mode="follow_default", source_platform=""
    )
    assert result["ok"] is False
    assert result["code"] == "no_platform_config"


# ---------------------------------------------------------------------------
# 6. static 模式（默认）— 存变体目录，Phase B 行为
# ---------------------------------------------------------------------------


def test_static_mode_stores_variant_path(tmp_path: Path):
    ws, src, tgt = _setup(tmp_path)
    variant = src / "通用" / "手控UI" / "v2.0"
    asset = _make_asset(variant)

    result = set_shared_module(tgt, asset, ws, mode="static")
    assert result["ok"] is True

    refs = load_shared_modules(tgt)
    assert refs[0].source_relative_path == "L50S程序/通用/手控UI/v2.0"
    assert refs[0].mode == "static"


# ---------------------------------------------------------------------------
# 7. 固定版本模式忽略 source_platform（不校验，不写入）
# ---------------------------------------------------------------------------


def test_static_ignores_source_platform(tmp_path: Path):
    ws, src, tgt = _setup(tmp_path)
    variant = src / "通用" / "手控UI" / "v2.0"
    asset = _make_asset(variant)

    result = set_shared_module(
        tgt, asset, ws, mode="static", source_platform="任意平台名"
    )
    assert result["ok"] is True

    refs = load_shared_modules(tgt)
    assert refs[0].source_platform == ""  # 未写入
