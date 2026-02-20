# -*- coding: utf-8 -*-
from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from .main_window import MainWindow
from .qa_system import RegulationQASystem
from .runtime import logger
from .ui_style import DARK_STYLE


def main():
    try:
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
        app.setStyleSheet(DARK_STYLE)

        qa = RegulationQASystem()
        window = MainWindow(qa)
        window.show()

        sys.exit(app.exec())
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
