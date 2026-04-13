"""Application entry point."""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from .gui.theme import DARK_STYLESHEET
from .gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("LensTool")
    app.setOrganizationName("LensTool")

    # Apply dark theme
    app.setStyleSheet(DARK_STYLESHEET)

    # Set default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
