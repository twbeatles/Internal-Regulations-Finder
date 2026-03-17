# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from regfinder.qa_system import RegulationQASystem
from regfinder.workers import ModelDownloadThread


def test_model_download_thread_validate_embedding_runtime_reports_pillow(monkeypatch):
    def fake_import_module(name: str):
        if name == "PIL.Image":
            raise ModuleNotFoundError("No module named 'PIL'")
        return object()

    monkeypatch.setattr("regfinder.workers._import_module", fake_import_module)

    worker = ModelDownloadThread([("테스트", "demo/model")])

    with pytest.raises(ImportError, match="Pillow import 실패"):
        worker._validate_embedding_runtime()


def test_qa_system_validate_embedding_runtime_reports_pillow(monkeypatch):
    def fake_import_module(name: str):
        if name == "PIL.Image":
            raise ModuleNotFoundError("No module named 'PIL'")
        return object()

    monkeypatch.setattr("regfinder.qa_system._import_module", fake_import_module)

    qa = RegulationQASystem()

    with pytest.raises(ImportError, match="Pillow import 실패"):
        qa._validate_embedding_runtime()
