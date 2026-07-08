from __future__ import annotations

from pathlib import Path

from fwasset.core.platform_config import (
    PlatformDefaults,
    load_platform_config,
    save_platform_config,
)


def set_default_variant(
    model_root: str,
    platform_name: str,
    module_dir: str,
    variant_name: str,
    log_fn=print,
) -> dict:
    """把某平台下某模块的默认变体写入 `平台配置.toml`。

    - 平台不存在时新建 `[[platform]]` 条目（文件缺失时整体新建）。
    - 已存在的其他平台/模块条目原样保留。
    - variant_name 允许为空串（表示该模块在通用区唯一，回源时按模块匹配）。
    """
    root = str(model_root or "").strip()
    platform = str(platform_name or "").strip()
    module = str(module_dir or "").strip()
    if not root or not platform or not module:
        return {
            "ok": False,
            "code": "invalid_args",
            "message": "设置默认失败：型号根目录、平台名与模块名均不能为空",
            "payload": {},
        }

    root_path = Path(root)
    if not root_path.is_dir():
        return {
            "ok": False,
            "code": "invalid_args",
            "message": f"设置默认失败：型号根目录不存在 ({root})",
            "payload": {},
        }

    try:
        platforms = load_platform_config(root_path)
        target = next((p for p in platforms if p.platform_name == platform), None)
        if target is None:
            target = PlatformDefaults(platform_name=platform)
            platforms.append(target)
        previous = target.defaults.get(module, "")
        target.defaults[module] = str(variant_name or "")
        toml_path = save_platform_config(root_path, platforms)
    except Exception as exc:  # noqa: BLE001
        message = f"写入平台配置失败: {exc}"
        log_fn(message)
        return {"ok": False, "code": "write_failed", "message": message, "payload": {}}

    shown = variant_name or module
    message = f"已将「{shown}」设为平台「{platform}」的默认程序"
    log_fn(message)
    return {
        "ok": True,
        "code": "ok",
        "message": message,
        "payload": {
            "config_path": str(toml_path),
            "platform": platform,
            "module_dir": module,
            "variant_name": str(variant_name or ""),
            "previous_variant": previous,
        },
    }
