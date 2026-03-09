"""
Serial Manager - Serial port management wrapper
"""

import serial
import serial.tools.list_ports
from typing import Optional, List, Tuple


class SerialManager:
    """Manage serial port connections"""

    def __init__(self):
        """Initialize serial manager"""
        self.port: Optional[serial.Serial] = None
        self.port_name: Optional[str] = None
        self.baud_rate: int = 9600

    def open(self, port_name: str, baud_rate: int = 9600,
             timeout: float = 0.5) -> Tuple[bool, str]:
        """
        Open serial port

        Args:
            port_name: Serial port name (e.g., COM1, /dev/ttyUSB0)
            baud_rate: Baud rate
            timeout: Read timeout in seconds

        Returns:
            Tuple of (success, error_message)
        """
        if self.port and self.port.is_open:
            self.close()

        try:
            self.port = serial.Serial(
                port=port_name,
                baudrate=baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=timeout,
                write_timeout=timeout,
            )
            self.port_name = port_name
            self.baud_rate = baud_rate
            return True, ""
        except serial.SerialException as e:
            return False, str(e)
        except Exception as e:
            return False, f"Unexpected error: {e}"

    def close(self) -> None:
        """Close serial port"""
        if self.port:
            try:
                self.port.close()
            except Exception:
                pass
            self.port = None
            self.port_name = None

    def is_open(self) -> bool:
        """Check if port is open"""
        return self.port is not None and self.port.is_open

    def get_port(self) -> Optional[serial.Serial]:
        """Get underlying serial port object"""
        return self.port

    def write(self, data: bytes) -> Tuple[bool, str]:
        """
        Write data to serial port

        Args:
            data: Data bytes to write

        Returns:
            Tuple of (success, error_message)
        """
        if not self.is_open():
            return False, "Serial port not open"

        try:
            self.port.write(data)
            self.port.flush()
            return True, ""
        except serial.SerialTimeoutException:
            return False, "Write timeout"
        except serial.SerialException as e:
            return False, str(e)

    def read(self, size: int = 1) -> bytes:
        """
        Read data from serial port

        Args:
            size: Number of bytes to read

        Returns:
            Read bytes (may be less than requested on timeout)
        """
        if not self.is_open():
            return b""

        try:
            return self.port.read(size)
        except Exception:
            return b""

    def read_all(self) -> bytes:
        """
        Read all available data from serial port

        Returns:
            Available data bytes
        """
        if not self.is_open():
            return b""

        try:
            return self.port.read_all()
        except Exception:
            return b""

    def flush_input(self) -> None:
        """Flush input buffer"""
        if self.is_open():
            try:
                self.port.reset_input_buffer()
            except Exception:
                pass

    def flush_output(self) -> None:
        """Flush output buffer"""
        if self.is_open():
            try:
                self.port.reset_output_buffer()
            except Exception:
                pass

    @staticmethod
    def list_ports() -> List[Tuple[str, str, str]]:
        """
        List available serial ports

        Returns:
            List of tuples (port_name, description, hardware_id)
        """
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append((port.device, port.description, port.hwid))
        return ports

    @staticmethod
    def list_port_names() -> List[str]:
        """
        List available serial port names

        Returns:
            List of port names
        """
        return [port.device for port in serial.tools.list_ports.comports()]
