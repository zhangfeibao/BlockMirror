"""
Session - Maintains connection state during interactive session
"""

import os
from typing import Optional, List, Tuple

from ..serial_manager import SerialManager
from ..symbol_resolver import SymbolResolver
from ..protocol import Protocol
from ..type_converter import TypeConverter
from ..state_manager import StateManager


class ReplSession:
    """
    Interactive session state manager.

    Maintains serial port connection and symbol resolver across commands,
    avoiding the need to reopen/reload for each operation.
    """

    def __init__(self):
        self.serial_manager: Optional[SerialManager] = None
        self.symbol_resolver: Optional[SymbolResolver] = None
        self.protocol: Optional[Protocol] = None
        self.type_converter: Optional[TypeConverter] = None

        self.port_name: Optional[str] = None
        self.baud_rate: int = 9600
        self.little_endian: bool = True
        self.symbols_file: Optional[str] = None

    @property
    def is_connected(self) -> bool:
        """Check if serial port is connected"""
        return (self.serial_manager is not None and
                self.serial_manager.is_open())

    @property
    def has_symbols(self) -> bool:
        """Check if symbols file is loaded"""
        return self.symbol_resolver is not None

    def open_port(self, port_name: str, baud_rate: int = 9600,
                  endian: str = 'little') -> Tuple[bool, str]:
        """
        Open serial port and keep it open for the session.

        Args:
            port_name: Serial port name (e.g., 'COM1')
            baud_rate: Baud rate (default: 9600)
            endian: Byte order ('little' or 'big')

        Returns:
            (success, error_message)
        """
        # Close existing connection if any
        self.close_port()

        self.serial_manager = SerialManager()
        success, error = self.serial_manager.open(port_name, baud_rate)

        if not success:
            self.serial_manager = None
            return False, error

        self.port_name = port_name
        self.baud_rate = baud_rate
        self.little_endian = (endian == 'little')

        # Create protocol and type converter
        self.protocol = Protocol(self.serial_manager.get_port(), self.little_endian)
        self.type_converter = TypeConverter(self.little_endian)

        # Save state for persistence
        StateManager.save_state(port_name, baud_rate, self.symbols_file, self.little_endian)

        return True, ''

    def close_port(self) -> None:
        """Close serial port connection and clear state"""
        if self.serial_manager:
            self.serial_manager.close()
            self.serial_manager = None

        self.protocol = None
        self.port_name = None

        # Clear persisted state
        StateManager.clear_state()

    def close_port_preserve_state(self) -> None:
        """Close serial port connection but preserve state for next session"""
        if self.serial_manager:
            self.serial_manager.close()
            self.serial_manager = None

        self.protocol = None
        self.port_name = None
        # Note: State file is NOT cleared, allowing next session to restore

    def load_symbols(self, symbols_file: str) -> Tuple[bool, str]:
        """
        Load symbols from JSON file.

        Args:
            symbols_file: Path to symbols.json

        Returns:
            (success, error_message)
        """
        if not os.path.exists(symbols_file):
            return False, f"File not found: {symbols_file}"

        try:
            self.symbol_resolver = SymbolResolver(symbols_file)
            self.symbols_file = os.path.abspath(symbols_file)

            # Update persisted state if connected
            if self.port_name:
                StateManager.save_state(
                    self.port_name, self.baud_rate,
                    self.symbols_file, self.little_endian
                )

            return True, ''
        except Exception as e:
            self.symbol_resolver = None
            self.symbols_file = None
            return False, str(e)

    def restore_from_state(self) -> Tuple[bool, str]:
        """
        Restore session from persisted state.

        Automatically reconnects to last serial port and loads symbols.

        Returns:
            (success, message) - message describes what was restored
        """
        state = StateManager.load_state()
        if not state:
            return False, ''

        messages = []

        # Load symbols first (doesn't require port)
        symbols_file = state.get('symbols_file')
        if symbols_file and os.path.exists(symbols_file):
            success, error = self.load_symbols(symbols_file)
            if success:
                count = self.get_symbol_count()
                messages.append(f"Loaded {count} symbols from {symbols_file}")
            else:
                messages.append(f"Failed to load symbols: {error}")

        # Try to reconnect to port
        port_name = state.get('port_name')
        baud_rate = state.get('baud_rate', 9600)
        little_endian = state.get('little_endian', True)

        if port_name:
            endian = 'little' if little_endian else 'big'
            success, error = self.open_port(port_name, baud_rate, endian)
            if success:
                messages.append(f"Connected to {port_name} at {baud_rate} baud")
            else:
                messages.append(f"Failed to connect to {port_name}: {error}")

        return len(messages) > 0, '\n'.join(messages)

    def get_symbol_count(self) -> int:
        """Get total number of loaded symbols"""
        if self.symbol_resolver:
            return len(self.symbol_resolver.symbols)
        return 0

    def get_all_variable_names(self) -> List[str]:
        """Get all variable names for auto-completion"""
        if self.symbol_resolver:
            return list(self.symbol_resolver.name_index.keys())
        return []

    def get_struct_members(self, var_name: str) -> List[str]:
        """
        Get struct member names for auto-completion.

        Args:
            var_name: Base variable name

        Returns:
            List of member names, or empty list if not a struct
        """
        if not self.symbol_resolver:
            return []

        symbols = self.symbol_resolver.name_index.get(var_name, [])
        if symbols and symbols[0].get('isStruct'):
            members = symbols[0].get('members', [])
            return [m['name'] for m in members]
        return []

    def get_symbol_at_path(self, path: str):
        """
        Get symbol information at a given path.

        Used by completer to understand the current context.

        Args:
            path: Variable path like 'struct.member' or 'struct'

        Returns:
            Symbol dict or None
        """
        if not self.symbol_resolver:
            return None

        # Parse path to get base name and accessors
        parts = path.replace('[', '.').replace(']', '').split('.')
        parts = [p for p in parts if p]  # Remove empty parts

        if not parts:
            return None

        # Get base symbol
        base_name = parts[0]
        symbols = self.symbol_resolver.name_index.get(base_name, [])
        if not symbols:
            return None

        current = symbols[0]

        # Traverse path
        for part in parts[1:]:
            if not current.get('isStruct'):
                return None

            members = current.get('members', [])
            found = None
            for m in members:
                if m['name'] == part:
                    found = m
                    break

            if not found:
                return None
            current = found

        return current

    def get_members_at_path(self, path: str) -> List[str]:
        """
        Get member names at a given path.

        Args:
            path: Variable path like 'struct' or 'struct.nested'

        Returns:
            List of member names at that path
        """
        symbol = self.get_symbol_at_path(path)
        if symbol and symbol.get('isStruct'):
            members = symbol.get('members', [])
            return [m['name'] for m in members]
        return []
