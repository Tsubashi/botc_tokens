# Standard library imports
import sys

# Third party imports
try:
    from PySide6.QtWidgets import QApplication, QMainWindow, QWidget
except ImportError:
    sys.exit(1)

# Application specific imports
from .main_window import MainWindow

def main():
    """Entry point for the GUI application."""
    app = QApplication()
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
