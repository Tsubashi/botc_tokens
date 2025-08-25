# Standard library imports

# Third party imports
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QFileDialog, QLabel, QLineEdit, QMessageBox

# Application specific imports

class RolesTab(QWidget):
    def __init__(self):
        super().__init__()
        # Layout
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Input Directory
        self.input_label = QLabel("Input Directory:")
        self.input_line_edit = QLineEdit()
        self.input_browse_button = QPushButton("Browse")
        self.input_browse_button.clicked.connect(self.browse_input_directory)

        layout.addWidget(self.input_label)
        layout.addWidget(self.input_line_edit)
        layout.addWidget(self.input_browse_button)

        # Output Directory
        self.output_label = QLabel("Output Directory:")
        self.output_line_edit = QLineEdit()
        self.output_browse_button = QPushButton("Browse")
        self.output_browse_button.clicked.connect(self.browse_output_directory)

        layout.addWidget(self.output_label)
        layout.addWidget(self.output_line_edit)
        layout.addWidget(self.output_browse_button)

        # Create Tokens Button
        self.create_tokens_button = QPushButton("Create Tokens")
        self.create_tokens_button.clicked.connect(self.create_tokens)

        layout.addWidget(self.create_tokens_button)

    def browse_input_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Input Directory")
        if directory:
            self.input_line_edit.setText(directory)

    def browse_output_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_line_edit.setText(directory)

    def create_tokens(self):
        input_dir = self.input_line_edit.text()
        output_dir = self.output_line_edit.text()

        if not input_dir or not output_dir:
            QMessageBox.warning(self, "Input Error", "Please specify both input and output directories.")
            return

        # Here you would call the token creation logic, e.g.:
        # create_tokens(input_dir, output_dir)

        QMessageBox.information(self, "Success", f"Tokens created from {input_dir} to {output_dir}.")