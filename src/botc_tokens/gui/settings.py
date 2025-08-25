# Standard Library Imports
import json
from pathlib import Path
from dataclasses import dataclass

# Third Party Imports
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, QDialog,
                               QPushButton, QMessageBox)

# Application Specific Imports

@dataclass
class Settings:
    config_file: Path = Path.home() / '.botc_tokens/config.json'
    page_height: int = 3300
    page_width: int = 2550

    def to_file(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.asdict(), f, indent=4)

    def load_from_file(self):
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                data = json.load(f)
                for key, value in data.items():
                    setattr(self, key, value)


class SettingsForm(QWidget):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        self.page_width_input = QLineEdit(str(self.settings.page_width))
        self.page_height_input = QLineEdit(str(self.settings.page_height))
        save_button = QPushButton("Save Settings")
        save_button.clicked.connect(self.save_settings)

        layout.addWidget(QLabel("Page Width:"))
        layout.addWidget(self.page_width_input)
        layout.addWidget(QLabel("Page Height:"))
        layout.addWidget(self.page_height_input)
        layout.addWidget(save_button)

        self.setLayout(layout)

    def save_settings(self):
        try:
            self.settings.page_width = int(self.page_width_input.text())
            self.settings.page_height = int(self.page_height_input.text())
            self.settings.to_file()
            QMessageBox.information(self, "Settings Saved", "Settings have been saved successfully.")
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid integer values for width and height.")

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.settings = Settings()
        self.settings.load_from_file()
        self.form = SettingsForm(self.settings)
        layout = QVBoxLayout()
        layout.addWidget(self.form)
        self.setLayout(layout)