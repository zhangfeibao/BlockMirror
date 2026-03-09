"""
Symbol Manager - Widget for loading and managing symbol files
"""

import os
import subprocess
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QGroupBox, QFileDialog, QMessageBox
)
from PySide6.QtCore import Signal, Slot

from ..symbol_resolver import SymbolResolver


class SymbolManager(QWidget):
    """Widget for managing symbol files"""

    symbols_loaded = Signal(object)  # Emits SymbolResolver instance

    def __init__(self, parent=None):
        super().__init__(parent)

        self._resolver: Optional[SymbolResolver] = None
        self._symbols_file: Optional[str] = None

        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface"""
        group = QGroupBox("Symbols")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(group)

        group_layout = QHBoxLayout(group)
        group_layout.setSpacing(8)

        # Generate button
        self.generate_btn = QPushButton("Generate from ELF")
        self.generate_btn.clicked.connect(self._on_generate)
        group_layout.addWidget(self.generate_btn)

        # Load button
        self.load_btn = QPushButton("Load Symbols")
        self.load_btn.clicked.connect(self._on_load)
        group_layout.addWidget(self.load_btn)

        # Status label
        self.status_label = QLabel("No symbols loaded")
        self.status_label.setStyleSheet("color: gray;")
        group_layout.addWidget(self.status_label)

    @Slot()
    def _on_generate(self):
        """Generate symbols from ELF file"""
        elf_path, _ = QFileDialog.getOpenFileName(
            self, "Select ELF File", "",
            "ELF Files (*.elf *.out *.axf);;All Files (*)"
        )

        if not elf_path:
            return

        # Find elfsym.exe
        elfsym_path = self._find_elfsym()
        if not elfsym_path:
            QMessageBox.critical(
                self, "Tool Not Found",
                "elfsym.exe not found. Please ensure elfsymbol/elfsym.exe exists."
            )
            return

        # Generate output path next to ELF file
        elf_dir = os.path.dirname(elf_path)
        output_path = os.path.join(elf_dir, "symbols.json")

        # Run elfsym.exe
        try:
            result = subprocess.run(
                [elfsym_path, elf_path, '-o', output_path],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or f"Exit code: {result.returncode}"
                QMessageBox.critical(
                    self, "Generation Failed",
                    f"Failed to generate symbols: {error_msg}"
                )
                return

            # Load the generated file
            self.load_symbols(output_path)

        except Exception as e:
            QMessageBox.critical(
                self, "Generation Failed",
                f"Failed to run elfsym.exe: {e}"
            )

    def _find_elfsym(self) -> Optional[str]:
        """Find elfsym.exe path"""
        # Try relative to this module
        module_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        elfsym_path = os.path.join(module_dir, 'elfsymbol', 'elfsym.exe')

        if os.path.exists(elfsym_path):
            return elfsym_path

        # Try relative to current directory
        elfsym_path = os.path.join('elfsymbol', 'elfsym.exe')
        if os.path.exists(elfsym_path):
            return elfsym_path

        return None

    @Slot()
    def _on_load(self):
        """Load symbols from JSON file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Symbols File", "",
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            self.load_symbols(file_path)

    def load_symbols(self, file_path: str):
        """Load symbols from specified file"""
        try:
            self._resolver = SymbolResolver(file_path)
            self._symbols_file = file_path

            count = len(self._resolver.symbols)
            filename = os.path.basename(file_path)
            self.status_label.setText(f"{filename} ({count} symbols)")
            self.status_label.setStyleSheet("color: green;")

            self.symbols_loaded.emit(self._resolver)

        except Exception as e:
            self._resolver = None
            self._symbols_file = None
            self.status_label.setText("Load failed")
            self.status_label.setStyleSheet("color: red;")

            QMessageBox.critical(
                self, "Load Failed",
                f"Failed to load symbols: {e}"
            )

    @property
    def resolver(self) -> Optional[SymbolResolver]:
        """Get the symbol resolver"""
        return self._resolver

    @property
    def symbols_file(self) -> Optional[str]:
        """Get the loaded symbols file path"""
        return self._symbols_file
