# -*- coding: utf-8 -*-
"""Backward-compatible entry wrapper."""

from regfinder.app_main import main
from regfinder.app_types import AppConfig, FileInfo, FileStatus, TaskResult, TaskStatus
from regfinder.main_window import MainWindow
from regfinder.qa_system import RegulationQASystem

__all__ = [
    'main',
    'AppConfig',
    'FileInfo',
    'FileStatus',
    'TaskResult',
    'TaskStatus',
    'MainWindow',
    'RegulationQASystem',
]


if __name__ == '__main__':
    main()
