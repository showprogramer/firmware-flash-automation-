from __future__ import annotations

import threading


class ScanStateModel:
    def __init__(self) -> None:
        self._cancel_event: threading.Event | None = None

    @property
    def cancel_event(self) -> threading.Event | None:
        return self._cancel_event

    @property
    def is_scanning(self) -> bool:
        return self._cancel_event is not None

    def begin(self) -> threading.Event:
        if self._cancel_event is None:
            self._cancel_event = threading.Event()
        return self._cancel_event

    def request_cancel(self) -> bool:
        if self._cancel_event is None:
            return False
        self._cancel_event.set()
        return True

    def finish(self, event: threading.Event) -> None:
        if self._cancel_event is event:
            self._cancel_event = None

    def replace(self, event: threading.Event | None) -> None:
        self._cancel_event = event
