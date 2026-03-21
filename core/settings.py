from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
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

    # Python 3.11+ uses tomllib; older Python can use optional tomli if installed.
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


def _as_str_set(values, default: set[str], lower: bool = False) -> set[str]:
    if not isinstance(values, list):
        return default
    out: set[str] = set()
    for item in values:
        if isinstance(item, str):
            out.add(item.lower() if lower else item)
    return out or default


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

