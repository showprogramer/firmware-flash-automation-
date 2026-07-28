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

# USB 操作常量（硬编码，不再从用户配置读取）
JUNK_EXTENSIONS: frozenset[str] = frozenset({".usu", ".tmp", ".bak"})
JUNK_FILENAMES: frozenset[str] = frozenset({"autorun.inf"})

# 扫描常量（硬编码，不再从用户配置读取）
SCAN_ROM_EXTENSIONS: list[str] = [".rom"]
SCAN_PKG_EXTENSIONS: list[str] = [".pkg"]
SCAN_EXCLUDE_DIR_KEYWORDS: list[str] = ["CH341SER", "接线图", "旧", "新建文件夹", "照片"]
SCAN_MODEL_PATTERNS: list[str] = [r"(?:^|[_\-])((L\d+[A-Za-z]*))(?![A-Za-z0-9])"]
SCAN_VERSION_PATTERNS: list[str] = [
    r"[Vv](\d+\.\d+(?:\.\d+)?(?:_\d+)?)",
    r"_(\d+\.\d+(?:\.\d+)?(?:_\d+)?)$",
    r"_UI_(\d+\.\d+(?:\.\d+)?(?:_\d+)?)",
    r"_(\d+\.\d+\.\d+(?:_\d+))$",
    r"_(\d+\.\d+\.\d+(?:_\d+)?)$",
    r"_(\d+_\d+(?:_\d+)?)$",
    r"(?<![0-9A-Za-z])(\d+\.\d+\.\d+(?:_\d+)?)(?![0-9A-Za-z])",
]
SCAN_PATH_MODEL_PATTERNS: list[str] = [r"(L\d+[A-Za-z]*(?:max|pro|s)?)(?![A-Za-z0-9])"]
SCAN_PATH_VERSION_PATTERNS: list[str] = [
    r"(?:^|[_\-])([Vv]\d+\.\d+(?:\.\d+)?(?:_\d+)?)(?:[_\-]|$)",
    r"\b(\d+\.\d+(?:\.\d+)?(?:_\d+))\b",
    r"\b(\d+\.\d+\.\d+(?:_\d+))\b",
    r"\b(\d+\.\d+\.\d+)\b",
]
