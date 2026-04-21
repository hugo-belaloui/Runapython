"""
Runna — Training Plan Manager
Entry point: python main.py
"""

import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from db.database import get_database
from ui.main_window import MainWindow


def main():
    # High-DPI support
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

    app = QApplication(sys.argv)

    # Global application style
    app.setStyle("Fusion")

    # Default font
    font = QFont("Segoe UI", 13)
    app.setFont(font)

    # Global stylesheet for consistent look
    app.setStyleSheet("""
        QMainWindow {
            background: #F5F5FA;
        }
        QToolTip {
            background: #1A1A2E;
            color: white;
            border: 1px solid #6C63FF;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 12px;
        }
        QScrollBar:vertical {
            background: transparent;
            width: 8px;
            margin: 0;
        }
        QScrollBar::handle:vertical {
            background: #C8C8D8;
            border-radius: 4px;
            min-height: 40px;
        }
        QScrollBar::handle:vertical:hover {
            background: #A8A8B8;
        }
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {
            height: 0;
        }
        QScrollBar:horizontal {
            background: transparent;
            height: 8px;
            margin: 0;
        }
        QScrollBar::handle:horizontal {
            background: #C8C8D8;
            border-radius: 4px;
            min-width: 40px;
        }
        QScrollBar::handle:horizontal:hover {
            background: #A8A8B8;
        }
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {
            width: 0;
        }
    """)

    # Initialize database (creates schema + seed data if needed)
    db = get_database()

    # Create and show main window
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
