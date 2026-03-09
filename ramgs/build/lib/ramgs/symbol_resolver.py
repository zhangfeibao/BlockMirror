"""
Symbol Resolver - Resolve variable names to memory addresses using symbols.json
"""

import json
import os
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

from .variable_parser import VariablePath, Accessor
from .config import NO_BITFIELD


@dataclass
class ResolvedSymbol:
    """Resolved symbol with all necessary information for read/write"""
    name: str
    address: int
    size: int
    base_type: str
    data_type: str
    source_file: str
    is_pointer: bool = False
    is_array: bool = False
    is_struct: bool = False
    is_enum: bool = False
    bit_offset: int = NO_BITFIELD
    bit_size: int = NO_BITFIELD
    enum_values: Optional[Dict[str, int]] = None


class SymbolResolver:
    """Resolve variable paths to symbol information"""

    def __init__(self, symbols_file: str):
        """
        Initialize symbol resolver

        Args:
            symbols_file: Path to symbols.json file
        """
        self.symbols_file = symbols_file
        self._load_symbols()

    def _load_symbols(self) -> None:
        """Load and index symbols from JSON file"""
        with open(self.symbols_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.schema_version = data.get('schemaVersion', '1.0')
        self.tool_version = data.get('toolVersion', 'unknown')
        self.source_elf = data.get('sourceElfFile', '')
        self.symbols: List[Dict] = data.get('symbols', [])

        # Build lookup indices
        self._build_indices()

    def _build_indices(self) -> None:
        """Build lookup indices for fast symbol resolution"""
        # name -> [symbols] (multiple files may have same name)
        self.name_index: Dict[str, List[Dict]] = {}
        # (name, source_file_basename) -> symbol
        self.name_file_index: Dict[Tuple[str, str], Dict] = {}

        for sym in self.symbols:
            name = sym.get('name', '')
            source = sym.get('sourceFile', '')
            # Get basename without extension for matching
            source_base = os.path.splitext(os.path.basename(source))[0]

            if name:
                if name not in self.name_index:
                    self.name_index[name] = []
                self.name_index[name].append(sym)

                if source_base:
                    self.name_file_index[(name, source_base)] = sym

    def _parse_address(self, addr_str: str) -> int:
        """Parse address string (e.g., '0x20001000') to integer"""
        if isinstance(addr_str, int):
            return addr_str
        if addr_str.startswith('0x') or addr_str.startswith('0X'):
            return int(addr_str, 16)
        return int(addr_str)

    def _find_base_symbol(self, name: str,
                          file_filter: Optional[str] = None) -> Optional[Dict]:
        """
        Find base symbol by name and optional file filter

        Args:
            name: Variable name
            file_filter: Optional source file filter (basename without extension)

        Returns:
            Symbol dictionary or None
        """
        if file_filter:
            # Try exact file match first
            key = (name, file_filter)
            if key in self.name_file_index:
                return self.name_file_index[key]
            # Try with .c extension removed
            key = (name, file_filter.replace('.c', '').replace('.h', ''))
            if key in self.name_file_index:
                return self.name_file_index[key]

        # Return first match
        if name in self.name_index and self.name_index[name]:
            return self.name_index[name][0]

        return None

    def _find_member(self, symbol: Dict, member_name: str) -> Optional[Dict]:
        """
        Find member within a struct/union symbol

        Args:
            symbol: Parent symbol (must be struct/union)
            member_name: Member name to find

        Returns:
            Member symbol dictionary or None
        """
        members = symbol.get('members', [])
        for member in members:
            if member.get('name') == member_name:
                return member
        return None

    def _calculate_array_element(self, symbol: Dict, index: int) -> Optional[Dict]:
        """
        Calculate array element information

        Args:
            symbol: Array symbol
            index: Array index

        Returns:
            Symbol-like dict for the array element or None
        """
        if not symbol.get('isArray'):
            return None

        dimensions = symbol.get('arrayDimensions', [])
        if not dimensions:
            return None

        # Check bounds
        if index < 0 or index >= dimensions[0]:
            return None

        # Calculate element address
        base_addr = self._parse_address(symbol.get('memoryAddress', '0'))
        element_size = symbol.get('sizeInBytes', 1)

        # For multi-dimensional arrays, element_size is the size of sub-array
        # For simple arrays, it's the base type size
        if len(dimensions) > 1:
            # Calculate size of remaining dimensions
            sub_size = element_size
            for dim in dimensions[1:]:
                sub_size *= dim
            element_addr = base_addr + index * sub_size
            # Return as sub-array
            return {
                'name': f"{symbol.get('name')}[{index}]",
                'dataType': symbol.get('dataType'),
                'baseDataType': symbol.get('baseDataType'),
                'sizeInBytes': sub_size,
                'memoryAddress': f"0x{element_addr:08X}",
                'sourceFile': symbol.get('sourceFile'),
                'isArray': True,
                'arrayDimensions': dimensions[1:],
            }
        else:
            # Simple array element
            element_addr = base_addr + index * element_size
            return {
                'name': f"{symbol.get('name')}[{index}]",
                'dataType': symbol.get('baseDataType', symbol.get('dataType')),
                'baseDataType': symbol.get('baseDataType'),
                'sizeInBytes': element_size,
                'memoryAddress': f"0x{element_addr:08X}",
                'sourceFile': symbol.get('sourceFile'),
            }

    def resolve(self, var_path: VariablePath) -> Optional[ResolvedSymbol]:
        """
        Resolve variable path to symbol information

        Args:
            var_path: Parsed variable path

        Returns:
            ResolvedSymbol or None if not found
        """
        # Find base symbol
        symbol = self._find_base_symbol(var_path.base_name, var_path.file_filter)
        if not symbol:
            return None

        # Apply accessors
        current = symbol
        for accessor in var_path.accessors:
            if accessor.type == 'member':
                if not current.get('isStruct'):
                    return None
                member = self._find_member(current, accessor.value)
                if not member:
                    return None
                current = member
            elif accessor.type == 'index':
                index = int(accessor.value)
                element = self._calculate_array_element(current, index)
                if not element:
                    return None
                current = element

        # Build resolved symbol
        return ResolvedSymbol(
            name=str(var_path),
            address=self._parse_address(current.get('memoryAddress', '0')),
            size=current.get('sizeInBytes', 1),
            base_type=current.get('baseDataType', current.get('dataType', '')),
            data_type=current.get('dataType', ''),
            source_file=current.get('sourceFile', ''),
            is_pointer=current.get('isPointer', False),
            is_array=current.get('isArray', False),
            is_struct=current.get('isStruct', False),
            is_enum=current.get('isEnum', False),
            bit_offset=current.get('bitOffset', NO_BITFIELD),
            bit_size=current.get('bitSize', NO_BITFIELD),
            enum_values=current.get('enumValues'),
        )

    def list_symbols(self, pattern: Optional[str] = None) -> List[str]:
        """
        List available symbol names

        Args:
            pattern: Optional filter pattern (simple substring match)

        Returns:
            List of symbol names
        """
        names = list(self.name_index.keys())
        if pattern:
            pattern_lower = pattern.lower()
            names = [n for n in names if pattern_lower in n.lower()]
        return sorted(names)

    def get_symbol_info(self, name: str) -> List[Dict]:
        """
        Get all symbols with given name

        Args:
            name: Symbol name

        Returns:
            List of symbol dictionaries
        """
        return self.name_index.get(name, [])

    def get_members(self, var_name: str) -> List[str]:
        """
        Get struct member names for auto-completion.

        Args:
            var_name: Base variable name

        Returns:
            List of member names, or empty list if not a struct
        """
        symbols = self.name_index.get(var_name, [])
        if symbols and symbols[0].get('isStruct'):
            members = symbols[0].get('members', [])
            return [m['name'] for m in members]
        return []

    def get_symbol_at_path(self, path: str) -> Optional[Dict]:
        """
        Get symbol information at a given path for completion.

        Args:
            path: Variable path like 'struct.member' or 'struct'

        Returns:
            Symbol dict or None
        """
        # Parse path to get base name and accessors
        parts = path.replace('[', '.').replace(']', '').split('.')
        parts = [p for p in parts if p]  # Remove empty parts

        if not parts:
            return None

        # Get base symbol
        base_name = parts[0]
        symbols = self.name_index.get(base_name, [])
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
        Get member names at a given path for auto-completion.

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

    def get_array_dimensions(self, path: str) -> Optional[List[int]]:
        """
        Get array dimensions at a given path.

        Args:
            path: Variable path

        Returns:
            List of dimensions or None if not an array
        """
        symbol = self.get_symbol_at_path(path)
        if symbol and symbol.get('isArray'):
            return symbol.get('arrayDimensions', [])
        return None
