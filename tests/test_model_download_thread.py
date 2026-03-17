# -*- coding: utf-8 -*-
from __future__ import annotations

import sys

from regfinder.workers import ModelDownloadThread


def test_model_download_thread_run_frozen_in_process(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        "regfinder.workers.get_models_directory",
        lambda: str(tmp_path / "models"),
    )

    def fake_import_module(name: str):
        class FakeTorch:
            class cuda:
                @staticmethod
                def is_available() -> bool:
                    return False

        assert name == "torch"
        return FakeTorch

    called: list[tuple[str, str, str]] = []

    def fake_run(self, model_id: str, cache_dir: str, device: str):
        called.append((model_id, cache_dir, device))

    monkeypatch.setattr("regfinder.workers._import_module", fake_import_module)
    monkeypatch.setattr(ModelDownloadThread, "_run_download_in_process", fake_run)

    worker = ModelDownloadThread([("테스트", "demo/model")])
    results = []
    worker.finished.connect(results.append)

    worker.run()

    assert called == [("demo/model", str(tmp_path / "models"), "cpu")]
    assert len(results) == 1
    assert results[0].success is True
    assert results[0].error_code == ""
