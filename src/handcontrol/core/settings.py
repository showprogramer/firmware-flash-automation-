from pathlib import Path

def _find_project_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return start


PROJECT_ROOT = _find_project_root(Path(__file__).resolve())
CONFIG_PATH = PROJECT_ROOT / "config.toml"

# Built-in defaults (used when config file is missing/invalid)
_DEFAULTS = {
    "paths": {
        "root_dir": "",
        "excel_path": "data/handcontrol_ui_template.xlsx",
    },
    "excel": {
        "sheet": "Sheet1",
        "header_row": 2,
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
        "exclude_dir_keywords": ["CH341SER", "主板程序"],
        "model_patterns": [r"(?:^|[_\-])((L\d+[A-Za-z]*))(?![A-Za-z0-9])"],
        "version_patterns": [
            r"[Vv](\d+\.\d+(?:\.\d+)?(?:_\d+)?)",
            r"_(\d+\.\d+(?:\.\d+)?(?:_\d+)?)$",
            r"_UI_(\d+\.\d+(?:\.\d+)?(?:_\d+)?)",
            r"_(\d+\.\d+\.\d+(?:_\d+))$",
            r"_(\d+\.\d+\.\d+(?:_\d+)?)$",
        ],
        "path_model_patterns": [r"(L\d+[A-Za-z]*(?:max|pro|s)?)(?![A-Za-z0-9])"],
        "path_version_patterns": [
            r"(?:^|[_\-])([Vv]\d+\.\d+(?:\.\d+)?(?:_\d+)?)(?:[_\-]|$)",
            r"\b(\d+\.\d+(?:\.\d+)?(?:_\d+))\b",
            r"\b(\d+\.\d+\.\d+(?:_\d+))\b",
            r"\b(\d+\.\d+\.\d+)\b",
        ],
    },
}


def load_toml_config(path: Path) -> tuple[dict, str, str]:
    """
    Load TOML config from file.
    Returns: (config_dict, status, error_message)
    status: ok | missing | parser_missing | parse_error
    """
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
        with open(path, "rb") as f:
            data = toml_loader.load(f)
        if isinstance(data, dict):
            return data, "ok", ""
        return {}, "parse_error", "config.toml 顶层结构必须是 TOML 表（table）"
    except Exception as e:
        return {}, "parse_error", str(e)


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


_cfg, CONFIG_LOAD_STATUS, CONFIG_LOAD_ERROR = load_toml_config(CONFIG_PATH)
CONFIG_LOAD_SOURCE = str(CONFIG_PATH)

_root_dir = _cfg_get(_cfg, "paths", "root_dir", _DEFAULTS["paths"]["root_dir"])
_excel_path_cfg = _cfg_get(_cfg, "paths", "excel_path", _DEFAULTS["paths"]["excel_path"])
if isinstance(_excel_path_cfg, str) and not Path(_excel_path_cfg).is_absolute():
    _excel_path = str((PROJECT_ROOT / _excel_path_cfg).resolve())
else:
    _excel_path = str(_excel_path_cfg)

DEFAULT_ROOT = str(_root_dir)
DEFAULT_EXCEL = _excel_path
EXCEL_SHEET = str(_cfg_get(_cfg, "excel", "sheet", _DEFAULTS["excel"]["sheet"]))
EXCEL_HEADER_ROW = _as_int(_cfg_get(_cfg, "excel", "header_row", _DEFAULTS["excel"]["header_row"]), 2)

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




