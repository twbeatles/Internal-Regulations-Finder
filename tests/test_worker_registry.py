# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

from regfinder.worker_registry import WorkerRegistry


class _FakeWorker:
    def __init__(self, running: bool = True):
        self._running = running
        self.canceled = False

    def isRunning(self):
        return self._running

    def cancel(self):
        self.canceled = True
        self._running = False


class WorkerRegistryTest(unittest.TestCase):
    def test_set_get_and_cancel(self):
        reg = WorkerRegistry()
        worker = _FakeWorker()
        reg.set("search", worker)
        self.assertTrue(reg.is_running("search"))
        reg.cancel("search")
        self.assertTrue(worker.canceled)
        self.assertFalse(reg.is_running("search"))


if __name__ == "__main__":
    unittest.main()
