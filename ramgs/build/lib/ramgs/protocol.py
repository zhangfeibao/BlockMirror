"""
Communication Protocol Implementation

Frame Format:
+------+------+------+-------+----------+------+------+
| SOF  | LEN  | CMD  | SEQ   | PAYLOAD  | CRC_L| CRC_H|
+------+------+------+-------+----------+------+------+
| 0xAA | 2B   | 1B   | 1B    | N Bytes  | 2B (CRC16) |
"""

import struct
from typing import List, Tuple, Optional
from dataclasses import dataclass

from .config import (
    SOF, FRAME_OVERHEAD, MAX_PAYLOAD_SIZE,
    CMD_READ_VAR, CMD_WRITE_VAR, CMD_READ_RESP, CMD_WRITE_RESP,
    CMD_ERROR, CMD_PING, CMD_PONG,
    ERR_OK, ERR_CRC, ERR_TIMEOUT, ERROR_MESSAGES,
    NO_BITFIELD, DEFAULT_TIMEOUT_MS, MAX_RETRIES
)


def crc16_ccitt(data: bytes) -> int:
    """
    Calculate CRC16-CCITT (polynomial 0x1021, init 0xFFFF)

    Args:
        data: Input data bytes

    Returns:
        16-bit CRC value
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


@dataclass
class VarInfo:
    """Variable information for read/write operations"""
    address: int
    size: int
    bit_offset: int = NO_BITFIELD
    bit_size: int = NO_BITFIELD

    def to_bytes(self) -> bytes:
        """Convert to protocol bytes (8 bytes)"""
        return struct.pack("<IHBB",
                           self.address,
                           self.size,
                           self.bit_offset,
                           self.bit_size)

    @classmethod
    def from_bytes(cls, data: bytes) -> "VarInfo":
        """Parse from protocol bytes"""
        addr, size, bit_off, bit_size = struct.unpack("<IHBB", data[:8])
        return cls(addr, size, bit_off, bit_size)


@dataclass
class Frame:
    """Protocol frame"""
    cmd: int
    seq: int
    payload: bytes

    def to_bytes(self) -> bytes:
        """Build complete frame bytes"""
        # Header: SOF + LEN(2) + CMD + SEQ
        header = struct.pack("<BHBB",
                             SOF,
                             len(self.payload),
                             self.cmd,
                             self.seq)
        # Calculate CRC over header + payload (excluding SOF byte for some implementations)
        # Here we include everything before CRC
        data_for_crc = header + self.payload
        crc = crc16_ccitt(data_for_crc)

        return data_for_crc + struct.pack("<H", crc)

    @classmethod
    def from_bytes(cls, data: bytes) -> Optional["Frame"]:
        """
        Parse frame from bytes

        Args:
            data: Raw frame bytes

        Returns:
            Parsed Frame or None if invalid
        """
        if len(data) < FRAME_OVERHEAD:
            return None

        if data[0] != SOF:
            return None

        payload_len = struct.unpack("<H", data[1:3])[0]

        if len(data) < FRAME_OVERHEAD + payload_len:
            return None

        cmd = data[3]
        seq = data[4]
        payload = data[5:5 + payload_len]

        # Verify CRC
        expected_crc = struct.unpack("<H", data[5 + payload_len:7 + payload_len])[0]
        actual_crc = crc16_ccitt(data[:5 + payload_len])

        if expected_crc != actual_crc:
            return None

        return cls(cmd, seq, payload)


class Protocol:
    """Communication protocol handler"""

    def __init__(self, serial_port, little_endian: bool = True):
        """
        Initialize protocol handler

        Args:
            serial_port: Serial port object (from pyserial)
            little_endian: True for little-endian byte order
        """
        self.serial = serial_port
        self.little_endian = little_endian
        self.seq = 0
        self.timeout_ms = DEFAULT_TIMEOUT_MS
        self.max_retries = MAX_RETRIES

    def _next_seq(self) -> int:
        """Get next sequence number (0-255)"""
        self.seq = (self.seq + 1) & 0xFF
        return self.seq

    def _receive_frame(self, timeout: float) -> Optional[Frame]:
        """
        Receive a complete frame with timeout

        Args:
            timeout: Timeout in seconds

        Returns:
            Parsed Frame or None on timeout/error
        """
        self.serial.timeout = timeout
        buffer = bytearray()

        # Wait for SOF
        while True:
            byte = self.serial.read(1)
            if not byte:
                return None
            if byte[0] == SOF:
                buffer.append(SOF)
                break

        # Read LEN (2 bytes)
        len_bytes = self.serial.read(2)
        if len(len_bytes) < 2:
            return None
        buffer.extend(len_bytes)
        payload_len = struct.unpack("<H", len_bytes)[0]

        if payload_len > MAX_PAYLOAD_SIZE:
            return None

        # Read CMD + SEQ + PAYLOAD + CRC
        remaining = 2 + payload_len + 2  # CMD(1) + SEQ(1) + PAYLOAD + CRC(2)
        rest = self.serial.read(remaining)
        if len(rest) < remaining:
            return None
        buffer.extend(rest)

        return Frame.from_bytes(bytes(buffer))

    def send_and_receive(self, frame: Frame) -> Tuple[bool, Optional[Frame], str]:
        """
        Send frame and wait for response with retry

        Args:
            frame: Frame to send

        Returns:
            Tuple of (success, response_frame, error_message)
        """
        frame_bytes = frame.to_bytes()

        for attempt in range(self.max_retries):
            try:
                self.serial.write(frame_bytes)
                self.serial.flush()

                response = self._receive_frame(self.timeout_ms / 1000.0)

                if response is None:
                    if attempt == self.max_retries - 1:
                        return False, None, "Timeout: No response from MCU"
                    continue

                # Check sequence number
                if response.seq != frame.seq:
                    continue

                # Check for error response
                if response.cmd == CMD_ERROR:
                    if response.payload:
                        err_code = response.payload[0]
                        err_msg = ERROR_MESSAGES.get(err_code, f"Unknown error: {err_code}")
                        return False, response, err_msg

                return True, response, ""

            except Exception as e:
                if attempt == self.max_retries - 1:
                    return False, None, str(e)

        return False, None, "Max retries exceeded"

    def read_variables(self, var_infos: List[VarInfo]) -> Tuple[bool, List[bytes], str]:
        """
        Read multiple variables from MCU

        Args:
            var_infos: List of VarInfo describing variables to read

        Returns:
            Tuple of (success, list_of_data_bytes, error_message)
        """
        if not var_infos:
            return False, [], "No variables to read"

        # Build payload: COUNT + VAR_INFO[0] + VAR_INFO[1] + ...
        payload = bytes([len(var_infos)])
        for var_info in var_infos:
            payload += var_info.to_bytes()

        frame = Frame(CMD_READ_VAR, self._next_seq(), payload)
        success, response, error = self.send_and_receive(frame)

        if not success:
            return False, [], error

        if response.cmd != CMD_READ_RESP:
            return False, [], f"Unexpected response command: 0x{response.cmd:02X}"

        # Parse response payload
        if not response.payload:
            return False, [], "Empty response"

        count = response.payload[0]
        if count != len(var_infos):
            return False, [], f"Variable count mismatch: expected {len(var_infos)}, got {count}"

        # Extract data for each variable
        data_list = []
        offset = 1
        for var_info in var_infos:
            if var_info.bit_offset != NO_BITFIELD:
                # Bitfield: 1 byte
                if offset >= len(response.payload):
                    return False, [], "Response too short"
                data_list.append(bytes([response.payload[offset]]))
                offset += 1
            else:
                # Normal: var_info.size bytes
                if offset + var_info.size > len(response.payload):
                    return False, [], "Response too short"
                data_list.append(response.payload[offset:offset + var_info.size])
                offset += var_info.size

        return True, data_list, ""

    def write_variables(self, var_infos: List[VarInfo],
                        data_list: List[bytes]) -> Tuple[bool, str]:
        """
        Write multiple variables to MCU

        Args:
            var_infos: List of VarInfo describing variables to write
            data_list: List of data bytes for each variable

        Returns:
            Tuple of (success, error_message)
        """
        if not var_infos:
            return False, "No variables to write"

        if len(var_infos) != len(data_list):
            return False, "Variable count and data count mismatch"

        # Build payload: COUNT + ENTRY[0] + ENTRY[1] + ...
        # ENTRY = VAR_INFO(8) + DATA(size)
        payload = bytes([len(var_infos)])
        for var_info, data in zip(var_infos, data_list):
            payload += var_info.to_bytes()
            payload += data

        frame = Frame(CMD_WRITE_VAR, self._next_seq(), payload)
        success, response, error = self.send_and_receive(frame)

        if not success:
            return False, error

        if response.cmd != CMD_WRITE_RESP:
            return False, f"Unexpected response command: 0x{response.cmd:02X}"

        # Check status
        if response.payload and response.payload[0] != ERR_OK:
            err_code = response.payload[0]
            return False, ERROR_MESSAGES.get(err_code, f"Error: {err_code}")

        return True, ""

    def ping(self) -> Tuple[bool, str]:
        """
        Send ping to check MCU connection

        Returns:
            Tuple of (success, error_message)
        """
        frame = Frame(CMD_PING, self._next_seq(), b"")
        success, response, error = self.send_and_receive(frame)

        if not success:
            return False, error

        if response.cmd != CMD_PONG:
            return False, f"Unexpected response: 0x{response.cmd:02X}"

        return True, ""
