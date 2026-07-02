from __future__ import annotations

from datetime import datetime
from pathlib import Path
import threading

from fwasset.core.settings import APP_LOG_PATH


class FileLogger:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else APP_LOG_PATH
        self._lock = threading.Lock()

    def log(self, message: str, level: str = "INFO") -> None:
        self._write_lines(level=level, lines=str(message or "").splitlines() or [""])

    def exception(self, context: str, exc_text: str) -> None:
        lines = [str(context or "").strip() or "Unhandled exception"]
        tb_lines = str(exc_text or "").splitlines() or [""]
        self._write_lines(level="ERROR", lines=lines + tb_lines)

    def _write_lines(self, level: str, lines: list[str]) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as fh:
                for line in lines:
                    fh.write(f"{timestamp} [{level}] {line}\n")
