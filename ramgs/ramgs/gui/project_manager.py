"""
Project Manager - Save and load project configurations
"""

import json
import os
from typing import Dict, Any, Optional


class ProjectManager:
    """Manage project file operations"""

    PROJECT_VERSION = "1.0"

    def save_project(self, file_path: str, data: Dict[str, Any]):
        """
        Save project configuration to file

        Args:
            file_path: Path to save project file
            data: Project data dictionary
        """
        # Ensure version is set
        data['version'] = self.PROJECT_VERSION

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_project(self, file_path: str) -> Dict[str, Any]:
        """
        Load project configuration from file

        Args:
            file_path: Path to project file

        Returns:
            Project data dictionary

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file is not valid JSON
            ValueError: If project format is invalid
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Project file not found: {file_path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Validate basic structure
        if not isinstance(data, dict):
            raise ValueError("Invalid project file format")

        # Check version (for future compatibility)
        version = data.get('version', '1.0')
        # Currently we only support version 1.0

        return data

    def validate_project(self, data: Dict[str, Any]) -> tuple:
        """
        Validate project data structure

        Args:
            data: Project data dictionary

        Returns:
            (is_valid, error_message) tuple
        """
        # Check required fields
        if 'connection' not in data:
            return False, "Missing 'connection' field"

        connection = data['connection']
        if not isinstance(connection, dict):
            return False, "'connection' must be a dictionary"

        # Validate monitored variables if present
        if 'monitoredVariables' in data:
            vars_list = data['monitoredVariables']
            if not isinstance(vars_list, list):
                return False, "'monitoredVariables' must be a list"

            for i, var in enumerate(vars_list):
                if not isinstance(var, dict):
                    return False, f"Variable at index {i} must be a dictionary"
                if 'path' not in var and 'id' not in var:
                    return False, f"Variable at index {i} missing 'path' or 'id'"

        return True, ""

    def migrate_project(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate project data from older versions

        Args:
            data: Project data dictionary

        Returns:
            Migrated project data
        """
        version = data.get('version', '1.0')

        # Future version migrations would go here
        # if version < '2.0':
        #     # Migrate from 1.0 to 2.0
        #     pass

        return data
