#!/usr/bin/env python
"""
Entry point for PyInstaller build.
This script uses absolute imports to avoid relative import issues.
"""

import sys
import os
import multiprocessing

# Required for Windows + PyInstaller multiprocessing support
# Must be called before any other multiprocessing code
multiprocessing.freeze_support()

# Ensure the package directory is in path
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    app_dir = os.path.dirname(sys.executable)
    # PyInstaller puts bundled packages under _MEIPASS (onedir -> _internal)
    base_dir = getattr(sys, '_MEIPASS', None)
    if not base_dir:
        internal_dir = os.path.join(app_dir, '_internal')
        base_dir = internal_dir if os.path.isdir(internal_dir) else app_dir
    # Set Qt plugin path for PyInstaller
    plugin_path = os.path.join(base_dir, 'PySide6', 'plugins')
    if not os.path.exists(plugin_path):
        # Fallback for legacy layouts
        plugin_path = os.path.join(app_dir, 'PySide6', 'plugins')
    os.environ['QT_PLUGIN_PATH'] = plugin_path
    platform_plugin_path = os.path.join(plugin_path, 'platforms')
    if os.path.isdir(platform_plugin_path):
        os.environ.setdefault('QT_QPA_PLATFORM_PLUGIN_PATH', platform_plugin_path)
    # Ensure bundled DLLs are discoverable on Windows
    if sys.platform == 'win32' and hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(base_dir)
        pyside_dir = os.path.join(base_dir, 'PySide6')
        if os.path.isdir(pyside_dir):
            os.add_dll_directory(pyside_dir)
else:
    # Running as script
    app_dir = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, app_dir)

from ramgs.cli import cli
cli()
