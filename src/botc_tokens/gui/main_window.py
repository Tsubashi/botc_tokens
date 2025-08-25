# Standard Library Imports

# Third Party Imports
from PySide6.QtWidgets import QMainWindow, QTabWidget, QDialog, QVBoxLayout, QLabel, QPushButton
from PySide6.QtGui import QAction

# Application Specific Imports
from .roles_tab import RolesTab
from .settings import SettingsDialog
from ..__version__ import version

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BotC Tokens GUI")
        self.create_menu_bar()

        # Central widget
        tab_widget = QTabWidget()
        self.setCentralWidget(tab_widget)
        tab_widget.addTab(RolesTab(), "Roles")

    def create_menu_bar(self):
        menu_bar = self.menuBar()

        # Create File menu
        file_menu = menu_bar.addMenu("&File")

        # Add actions to File menu
        settings_action = QAction("&Settings", self)
        settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()  # Add a separator line

        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Create Help menu
        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def open_settings(self):
        settings_dialog = SettingsDialog(self)
        settings_dialog.exec()

    def show_about_dialog(self):
        about_dialog = QDialog(self)
        about_dialog.setWindowTitle("About BotC Tokens GUI")
        about_dialog_layout = QVBoxLayout()
        about_dialog_layout.addWidget(QLabel(f"BotC Tokens GUI\nVersion {version}"))
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(about_dialog.accept)
        about_dialog_layout.addWidget(ok_button)
        about_dialog.setLayout(about_dialog_layout)
        about_dialog.exec()

