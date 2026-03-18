from __future__ import annotations

from .app_types import AppConfig, FileInfo, FileStatus, TaskResult, TaskStatus

__all__ = [
    "AppConfig",
    "FileInfo",
    "FileStatus",
    "TaskResult",
    "TaskStatus",
]


def __getattr__(name: str):
    if name == "RegulationQASystem":
        from .qa_system import RegulationQASystem

        return RegulationQASystem
    if name == "MainWindow":
        from .main_window import MainWindow

        return MainWindow
    if name == "main":
        from .app_main import main

        return main
    raise AttributeError(name)
