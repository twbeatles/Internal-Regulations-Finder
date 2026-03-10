# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Protocol


class WorkerLike(Protocol):
    def isRunning(self) -> bool: ...
    def cancel(self) -> None: ...


class WorkerRegistry:
    """작업 종류별 워커 레퍼런스 관리."""

    def __init__(self) -> None:
        self._workers: dict[str, WorkerLike] = {}

    def set(self, key: str, worker: WorkerLike) -> None:
        self._workers[key] = worker

    def get(self, key: str) -> WorkerLike | None:
        return self._workers.get(key)

    def clear(self, key: str) -> None:
        if key in self._workers:
            self._workers.pop(key, None)

    def is_running(self, key: str) -> bool:
        worker = self.get(key)
        try:
            return bool(worker and worker.isRunning())
        except Exception:
            return False

    def cancel(self, key: str) -> None:
        worker = self.get(key)
        if not worker:
            return
        try:
            worker.cancel()
        finally:
            self.clear(key)

    def cancel_all(self) -> None:
        for key in list(self._workers.keys()):
            self.cancel(key)
