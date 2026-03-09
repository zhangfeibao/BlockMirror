"""
File Manager - Load and save panel design files

Handles reading and writing .panel.json files with validation.
"""

import json
import os
from typing import Optional, Tuple

from .panel_schema import PanelDesign, SCHEMA_VERSION


class FileManager:
    """Manages panel design file operations"""

    # File extension for panel design files
    FILE_EXTENSION = ".panel.json"

    @staticmethod
    def load(file_path: str) -> Tuple[Optional[PanelDesign], Optional[str]]:
        """
        Load a panel design from file.

        Args:
            file_path: Path to the .panel.json file

        Returns:
            Tuple of (PanelDesign or None, error message or None)
        """
        if not os.path.exists(file_path):
            return None, f"File not found: {file_path}"

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            design = PanelDesign.from_json(content)

            # Version compatibility check
            if design.version != SCHEMA_VERSION:
                # For now, accept older versions
                pass

            return design, None

        except json.JSONDecodeError as e:
            return None, f"Invalid JSON format: {e}"
        except KeyError as e:
            return None, f"Missing required field: {e}"
        except Exception as e:
            return None, f"Failed to load file: {e}"

    @staticmethod
    def save(file_path: str, design: PanelDesign) -> Optional[str]:
        """
        Save a panel design to file.

        Args:
            file_path: Path to save the file
            design: PanelDesign to save

        Returns:
            Error message or None on success
        """
        try:
            # Ensure correct extension
            if not file_path.endswith(FileManager.FILE_EXTENSION):
                file_path += FileManager.FILE_EXTENSION

            # Ensure directory exists
            dir_path = os.path.dirname(file_path)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path)

            # Update version to current
            design.version = SCHEMA_VERSION

            # Write file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(design.to_json(indent=2))

            return None

        except PermissionError:
            return f"Permission denied: {file_path}"
        except Exception as e:
            return f"Failed to save file: {e}"

    @staticmethod
    def validate(file_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a panel design file without fully loading it.

        Args:
            file_path: Path to the file to validate

        Returns:
            Tuple of (is_valid, error message or None)
        """
        design, error = FileManager.load(file_path)
        if error:
            return False, error
        return True, None

    @staticmethod
    def get_file_filter() -> str:
        """Get file dialog filter string"""
        return f"Panel Design (*{FileManager.FILE_EXTENSION});;All Files (*)"
