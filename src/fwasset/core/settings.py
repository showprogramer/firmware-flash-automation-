import os
import sys
from pathlib import Path


def _find_project_root(start: Path) -> Path:
    probe = Path(start).resolve()
    for parent in [probe, *probe.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return probe


def _find_app_root(start: Path | None = None) -> Path:
    """返回应用程序根目录（配置文件和 exe 所在目录）。

    开发模式：pyproject.toml 所在目录。
    打包模式（PyInstaller）：exe 所在目录。
    """
    if start is not None:
        return _find_project_root(start)
    if getattr(sys, "frozen", False):
        # PyInstaller 打包后运行
        return Path(sys.executable).resolve().parent
    # 开发模式：向上查找 pyproject.toml
    return _find_project_root(Path(__file__).resolve())


APP_ROOT = _find_app_root()
"""应用程序根目录。配置文件和可执行文件同目录。"""

CONFIG_PATH = APP_ROOT / "config.toml"


def _default_runtime_dir(app_root: Path | None = None) -> Path:
    root = Path(app_root or APP_ROOT)
    if getattr(sys, "frozen", False):
        return root / "runtime"
    return root / ".runtime"


def _resolve_runtime_dir(app_root: Path | None = None, env_value: str | None = None) -> Path:
    root = Path(app_root or APP_ROOT)
    raw = os.environ.get("FWASSET_RUNTIME_DIR") if env_value is None else env_value
    if raw and str(raw).strip():
        path = Path(str(raw).strip())
        if path.is_absolute():
            return path
        return (root / path).resolve()
    return _default_runtime_dir(root).resolve()


def ensure_runtime_dir(path: str | Path | None = None) -> Path:
    target = Path(path) if path is not None else _resolve_runtime_dir()
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(f"运行时目录创建失败: {target} ({exc})") from exc
    return target


RUNTIME_DIR = ensure_runtime_dir()
ASSET_INDEX_PATH = RUNTIME_DIR / "fwasset.db"
LOG_DIR = RUNTIME_DIR / "logs"
APP_LOG_PATH = LOG_DIR / "app.log"

_DEFAULTS = {
    "paths": {
        "root_dir": "",
        "tool_root": "",
    },
    "usb": {
        "junk_extensions": [".usu", ".tmp", ".bak"],
        "junk_filenames": ["autorun.inf"],
        "auto_diagnose_on_insert": True,
        "health_check_interval_sec": 3,
    },
    "scan": {
        "rom_extensions": [".rom"],
        "pkg_extensions": [".pkg"],
        "exclude_dir_keywords": ["CH341SER", "接线图", "旧", "新建文件夹", "照片"],
        "model_patterns": [r"(?:^|[_\-])((L\d+[A-Za-z]*))(?![A-Za-z0-9])"],
        "version_patterns": [
            r"[Vv](\d+\.\d+(?:\.\d+)?(?:_\d+)?)",
            r"_(\d+\.\d+(?:\.\d+)?(?:_\d+)?)$",
            r"_UI_(\d+\.\d+(?:\.\d+)?(?:_\d+)?)",
            r"_(\d+\.\d+\.\d+(?:_\d+))$",
            r"_(\d+\.\d+\.\d+(?:_\d+)?)$",
            r"_(\d+_\d+(?:_\d+)?)$",
            r"(?<![0-9A-Za-z])(\d+\.\d+\.\d+(?:_\d+)?)(?![0-9A-Za-z])",
        ],
        "path_model_patterns": [r"(L\d+[A-Za-z]*(?:max|pro|s)?)(?![A-Za-z0-9])"],
        "path_version_patterns": [
            r"(?:^|[_\-])([Vv]\d+\.\d+(?:\.\d+)?(?:_\d+)?)(?:[_\-]|$)",
            r"\b(\d+\.\d+(?:\.\d+)?(?:_\d+))\b",
            r"\b(\d+\.\d+\.\d+(?:_\d+))\b",
            r"\b(\d+\.\d+\.\d+)\b",
        ],
    },
    "music": {
        "default_source_dir": "",
    },
    "serial": {
        "default_baudrate": 115200,
        "at_presets": [
            "AT+NM=Premium XZ8",
            "AT+MP=8888",
            "AT+FUN=PIN=EN",
            "AT+BD=38400",
        ],
    },
}


def load_toml_config(path: Path) -> tuple[dict, str, str]:
    if not path.exists():
        return {}, "missing", ""

    toml_loader = None
    try:
        import tomllib  # type: ignore

        toml_loader = tomllib
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore

            toml_loader = tomllib
        except ModuleNotFoundError:
            return {}, "parser_missing", "Python<3.11 需要安装 tomli 才能读取 config.toml"

    try:
        with open(path, "rb") as file_obj:
            data = toml_loader.load(file_obj)
        if isinstance(data, dict):
            return data, "ok", ""
        return {}, "parse_error", "config.toml 顶层结构必须是 TOML 表（table）"
    except Exception as exc:
        return {}, "parse_error", str(exc)


def _cfg_get(cfg: dict, section: str, key: str, default):
    node = cfg.get(section, {})
    if not isinstance(node, dict):
        return default
    return node.get(key, default)


def _as_int(value, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _as_bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    return default


def _as_str_set(values, default: set[str], lower: bool = False) -> set[str]:
    if not isinstance(values, list):
        return default
    out: set[str] = set()
    for item in values:
        if isinstance(item, str):
            out.add(item.lower() if lower else item)
    return out or default


def _as_str_list(values, default: list[str], lower: bool = False) -> list[str]:
    if not isinstance(values, list):
        return list(default)
    out: list[str] = []
    for item in values:
        if isinstance(item, str):
            out.append(item.lower() if lower else item)
    return out or list(default)


def _resolve_path(value, default: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return str(default or "")
    path = Path(text)
    if not path.is_absolute():
        return str((APP_ROOT / path).resolve())
    return str(path)


_cfg, CONFIG_LOAD_STATUS, CONFIG_LOAD_ERROR = load_toml_config(CONFIG_PATH)
CONFIG_LOAD_SOURCE = str(CONFIG_PATH)

DEFAULT_ROOT = str(_cfg_get(_cfg, "paths", "root_dir", _DEFAULTS["paths"]["root_dir"]))
TOOL_ROOT = _resolve_path(
    _cfg_get(_cfg, "paths", "tool_root", _DEFAULTS["paths"]["tool_root"]),
    _DEFAULTS["paths"]["tool_root"],
)

JUNK_EXTENSIONS = _as_str_set(
    _cfg_get(_cfg, "usb", "junk_extensions", _DEFAULTS["usb"]["junk_extensions"]),
    set(_DEFAULTS["usb"]["junk_extensions"]),
    lower=True,
)
JUNK_FILENAMES = _as_str_set(
    _cfg_get(_cfg, "usb", "junk_filenames", _DEFAULTS["usb"]["junk_filenames"]),
    set(_DEFAULTS["usb"]["junk_filenames"]),
    lower=True,
)
USB_AUTO_DIAGNOSE_ON_INSERT = _as_bool(
    _cfg_get(_cfg, "usb", "auto_diagnose_on_insert", _DEFAULTS["usb"]["auto_diagnose_on_insert"]),
    True,
)
USB_HEALTH_CHECK_INTERVAL_SEC = max(
    2,
    _as_int(
        _cfg_get(_cfg, "usb", "health_check_interval_sec", _DEFAULTS["usb"]["health_check_interval_sec"]),
        3,
    ),
)

SCAN_ROM_EXTENSIONS = _as_str_list(
    _cfg_get(_cfg, "scan", "rom_extensions", _DEFAULTS["scan"]["rom_extensions"]),
    _DEFAULTS["scan"]["rom_extensions"],
    lower=True,
)
SCAN_PKG_EXTENSIONS = _as_str_list(
    _cfg_get(_cfg, "scan", "pkg_extensions", _DEFAULTS["scan"]["pkg_extensions"]),
    _DEFAULTS["scan"]["pkg_extensions"],
    lower=True,
)
SCAN_EXCLUDE_DIR_KEYWORDS = _as_str_list(
    _cfg_get(_cfg, "scan", "exclude_dir_keywords", _DEFAULTS["scan"]["exclude_dir_keywords"]),
    _DEFAULTS["scan"]["exclude_dir_keywords"],
)
SCAN_MODEL_PATTERNS = _as_str_list(
    _cfg_get(_cfg, "scan", "model_patterns", _DEFAULTS["scan"]["model_patterns"]),
    _DEFAULTS["scan"]["model_patterns"],
)
SCAN_VERSION_PATTERNS = _as_str_list(
    _cfg_get(_cfg, "scan", "version_patterns", _DEFAULTS["scan"]["version_patterns"]),
    _DEFAULTS["scan"]["version_patterns"],
)
SCAN_PATH_MODEL_PATTERNS = _as_str_list(
    _cfg_get(_cfg, "scan", "path_model_patterns", _DEFAULTS["scan"]["path_model_patterns"]),
    _DEFAULTS["scan"]["path_model_patterns"],
)
SCAN_PATH_VERSION_PATTERNS = _as_str_list(
    _cfg_get(_cfg, "scan", "path_version_patterns", _DEFAULTS["scan"]["path_version_patterns"]),
    _DEFAULTS["scan"]["path_version_patterns"],
)

MUSIC_DEFAULT_SOURCE_DIR = _resolve_path(
    _cfg_get(_cfg, "music", "default_source_dir", _DEFAULTS["music"]["default_source_dir"]),
    _DEFAULTS["music"]["default_source_dir"],
)
SERIAL_DEFAULT_BAUDRATE = max(
    1200,
    _as_int(_cfg_get(_cfg, "serial", "default_baudrate", _DEFAULTS["serial"]["default_baudrate"]), 115200),
)
SERIAL_AT_PRESETS = _as_str_list(
    _cfg_get(_cfg, "serial", "at_presets", _DEFAULTS["serial"]["at_presets"]),
    _DEFAULTS["serial"]["at_presets"],
)
