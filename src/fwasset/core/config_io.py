"""配置文件原子写盘助手（同目录临时文件 + os.replace）。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """在目标同目录写临时文件，flush/fsync 后用 os.replace 原子替换。

    不自动创建父目录。写入、fsync 或 replace 失败时清理临时文件并上抛异常。
    """
    target = Path(path)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as file_obj:
            file_obj.write(content)
            file_obj.flush()
            os.fsync(file_obj.fileno())
        os.replace(str(temp_path), str(target))
    except BaseException:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
