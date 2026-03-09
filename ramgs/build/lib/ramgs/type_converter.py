"""
Type Converter - Convert between Python values and byte representations
"""

import struct
from typing import Any, Optional, Dict, Tuple


class TypeConverter:
    """Convert between Python values and MCU byte representations"""

    # Base type to (struct format char, size) mapping
    # Note: sizes may vary by MCU architecture
    TYPE_MAP: Dict[str, Tuple[str, int]] = {
        # Unsigned integers
        "unsigned char": ("B", 1),
        "uint8_t": ("B", 1),
        "unsigned short": ("H", 2),
        "uint16_t": ("H", 2),
        "unsigned int": ("I", 4),
        "uint32_t": ("I", 4),
        "unsigned long": ("L", 4),
        "uint64_t": ("Q", 8),
        "unsigned long long": ("Q", 8),
        # Signed integers
        "signed char": ("b", 1),
        "int8_t": ("b", 1),
        "char": ("b", 1),
        "signed short": ("h", 2),
        "short": ("h", 2),
        "int16_t": ("h", 2),
        "signed int": ("i", 4),
        "int": ("i", 4),
        "int32_t": ("i", 4),
        "signed long": ("l", 4),
        "long": ("l", 4),
        "int64_t": ("q", 8),
        "long long": ("q", 8),
        "signed long long": ("q", 8),
        # Floating point
        "float": ("f", 4),
        "double": ("d", 8),
        # Boolean
        "bool": ("?", 1),
        "_Bool": ("?", 1),
    }

    def __init__(self, little_endian: bool = True):
        """
        Initialize type converter

        Args:
            little_endian: True for little-endian byte order
        """
        self.byte_order = "<" if little_endian else ">"

    def _get_format(self, base_type: str, size: int) -> Optional[str]:
        """
        Get struct format string for a type

        Args:
            base_type: Base data type string
            size: Actual size in bytes

        Returns:
            Struct format string or None if unknown type
        """
        type_info = self.TYPE_MAP.get(base_type)
        if type_info:
            fmt_char, expected_size = type_info
            # Adjust format if size differs (MCU-specific int sizes)
            if size != expected_size:
                fmt_char = self._size_to_format(size, fmt_char.isupper())
            return fmt_char
        return None

    def _size_to_format(self, size: int, unsigned: bool) -> str:
        """
        Get format character based on size

        Args:
            size: Size in bytes
            unsigned: True for unsigned type

        Returns:
            Format character
        """
        if size == 1:
            return "B" if unsigned else "b"
        elif size == 2:
            return "H" if unsigned else "h"
        elif size == 4:
            return "I" if unsigned else "i"
        elif size == 8:
            return "Q" if unsigned else "q"
        else:
            # Fallback: treat as byte array
            return None

    def encode(self, value: Any, base_type: str, size: int) -> bytes:
        """
        Encode Python value to bytes

        Args:
            value: Python value to encode
            base_type: Base data type string
            size: Size in bytes

        Returns:
            Encoded bytes
        """
        fmt_char = self._get_format(base_type, size)
        if fmt_char:
            try:
                return struct.pack(self.byte_order + fmt_char, value)
            except struct.error:
                pass

        # Fallback: treat as integer and pack to bytes
        if isinstance(value, (int, float)):
            int_val = int(value)
            result = int_val.to_bytes(size,
                                       byteorder="little" if self.byte_order == "<" else "big",
                                       signed=(int_val < 0))
            return result

        raise ValueError(f"Cannot encode value {value} as {base_type}")

    def decode(self, data: bytes, base_type: str) -> Any:
        """
        Decode bytes to Python value

        Args:
            data: Raw bytes to decode
            base_type: Base data type string

        Returns:
            Decoded Python value
        """
        size = len(data)
        fmt_char = self._get_format(base_type, size)
        if fmt_char:
            try:
                return struct.unpack(self.byte_order + fmt_char, data)[0]
            except struct.error:
                pass

        # Fallback: treat as unsigned integer
        return int.from_bytes(data,
                              byteorder="little" if self.byte_order == "<" else "big",
                              signed=False)

    def encode_bitfield(self, value: int, current_byte: int,
                        bit_size: int, bit_offset: int) -> int:
        """
        Encode value into bitfield within a byte

        Args:
            value: Value to encode
            current_byte: Current byte value
            bit_size: Number of bits for the field
            bit_offset: Bit offset within the byte

        Returns:
            New byte value with bitfield set
        """
        mask = ((1 << bit_size) - 1) << bit_offset
        return (current_byte & ~mask) | ((value << bit_offset) & mask)

    def decode_bitfield(self, byte_value: int, bit_size: int, bit_offset: int) -> int:
        """
        Extract bitfield value from byte

        Args:
            byte_value: Byte containing the bitfield
            bit_size: Number of bits for the field
            bit_offset: Bit offset within the byte

        Returns:
            Extracted value
        """
        mask = (1 << bit_size) - 1
        return (byte_value >> bit_offset) & mask

    def parse_value(self, value_str: str, base_type: str) -> Any:
        """
        Parse string value to appropriate Python type

        Args:
            value_str: String representation of value
            base_type: Base data type

        Returns:
            Parsed Python value
        """
        value_str = value_str.strip()

        # Handle hex values
        if value_str.startswith("0x") or value_str.startswith("0X"):
            return int(value_str, 16)

        # Handle binary values
        if value_str.startswith("0b") or value_str.startswith("0B"):
            return int(value_str, 2)

        # Handle octal values
        if value_str.startswith("0o") or value_str.startswith("0O"):
            return int(value_str, 8)

        # Handle floating point
        if base_type in ("float", "double") or "." in value_str:
            return float(value_str)

        # Handle boolean
        if base_type in ("bool", "_Bool"):
            lower = value_str.lower()
            if lower in ("true", "1", "yes"):
                return True
            elif lower in ("false", "0", "no"):
                return False

        # Default: integer
        return int(value_str)

    def format_value(self, value: Any, base_type: str) -> str:
        """
        Format value for display

        Args:
            value: Python value
            base_type: Base data type

        Returns:
            Formatted string
        """
        if base_type in ("float", "double"):
            return f"{value:.6g}"
        elif base_type in ("bool", "_Bool"):
            return "true" if value else "false"
        elif isinstance(value, int):
            # Show hex for larger values
            if abs(value) > 255:
                return f"{value} (0x{value & 0xFFFFFFFF:X})"
            return str(value)
        return str(value)
