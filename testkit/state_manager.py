"""
State Manager - Persistent state management for CLI
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any


class StateManager:
    """Manage persistent state between CLI invocations"""

    STATE_DIR = Path.home() / ".ramgs"
    STATE_FILE = STATE_DIR / "state.json"

    @classmethod
    def _ensure_dir(cls) -> None:
        """Ensure state directory exists"""
        cls.STATE_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def save_state(cls,
                   port_name: str,
                   baud_rate: int,
                   symbols_file: Optional[str] = None,
                   little_endian: bool = True) -> None:
        """
        Save current connection state

        Args:
            port_name: Serial port name (e.g., COM1)
            baud_rate: Baud rate
            symbols_file: Path to symbols.json file
            little_endian: True for little-endian, False for big-endian
        """
        cls._ensure_dir()
        state = {
            "port_name": port_name,
            "baud_rate": baud_rate,
            "symbols_file": symbols_file,
            "little_endian": little_endian,
        }
        cls.STATE_FILE.write_text(json.dumps(state, indent=2))

    @classmethod
    def load_state(cls) -> Optional[Dict[str, Any]]:
        """
        Load saved state

        Returns:
            State dictionary or None if no state exists
        """
        if cls.STATE_FILE.exists():
            try:
                return json.loads(cls.STATE_FILE.read_text())
            except (json.JSONDecodeError, IOError):
                return None
        return None

    @classmethod
    def clear_state(cls) -> None:
        """Clear state on close"""
        if cls.STATE_FILE.exists():
            cls.STATE_FILE.unlink()

    @classmethod
    def is_connected(cls) -> bool:
        """Check if a connection state exists"""
        return cls.STATE_FILE.exists()

    @classmethod
    def get_port_name(cls) -> Optional[str]:
        """Get saved port name"""
        state = cls.load_state()
        return state.get("port_name") if state else None

    @classmethod
    def get_baud_rate(cls) -> Optional[int]:
        """Get saved baud rate"""
        state = cls.load_state()
        return state.get("baud_rate") if state else None

    @classmethod
    def get_symbols_file(cls) -> Optional[str]:
        """Get saved symbols file path"""
        state = cls.load_state()
        return state.get("symbols_file") if state else None

    @classmethod
    def set_symbols_file(cls, symbols_file: str) -> None:
        """Update symbols file path in state"""
        state = cls.load_state()
        if state:
            state["symbols_file"] = symbols_file
            cls.STATE_FILE.write_text(json.dumps(state, indent=2))

    @classmethod
    def is_little_endian(cls) -> bool:
        """Get endianness setting (default: little-endian)"""
        state = cls.load_state()
        if state:
            return state.get("little_endian", True)
        return True
