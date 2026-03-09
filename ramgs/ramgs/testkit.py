"""
Test Automation Library for RAMViewer

Provides McuConnection class for automated MCU testing scripts.
Reads connection config from ~/.ramgs/state.json (set by 'ramgs open' and 'ramgs create').

Usage:
    from ramgs.testkit import McuConnection

    with McuConnection() as mcu:
        val = mcu.get("counter")
        mcu.set("counter", 0)
        mcu.wait_until("cal_done", 1, timeout_s=10.0)
"""

import builtins
import os
import time
from typing import Any, Callable, Dict, List, Optional, Union

from .config import NO_BITFIELD
from .protocol import Protocol, VarInfo
from .serial_manager import SerialManager
from .state_manager import StateManager
from .symbol_resolver import ResolvedSymbol, SymbolResolver
from .type_converter import TypeConverter
from .variable_parser import VariableParser


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class RamgsError(Exception):
    """Base class for all ramgs testkit errors."""
    pass


class ConnectionError(RamgsError):
    """Serial connection failure (open failed, connection lost, state.json missing)."""
    pass


class SymbolError(RamgsError):
    """Symbol file loading or variable name resolution failure."""
    pass


class CommunicationError(RamgsError):
    """MCU did not respond or returned a protocol-level error."""
    pass


class TimeoutError(CommunicationError):
    """wait_until() timed out before the condition was met.

    Attributes:
        var_name:   The variable being polled.
        timeout_s:  The timeout that elapsed.
        last_value: The last value read before giving up.
    """

    def __init__(self, message: str, var_name: str, timeout_s: float,
                 last_value: Any):
        super().__init__(message)
        self.var_name = var_name
        self.timeout_s = timeout_s
        self.last_value = last_value


class ValueError(RamgsError):
    """Type conversion error (encode / decode failure)."""
    pass


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class McuConnection:
    """Persistent connection to an MCU for automated test scripts.

    Reads port, baud, endian, and symbols path from ``~/.ramgs/state.json``
    which is written by the CLI commands ``ramgs open`` and ``ramgs create``.

    Example::

        with McuConnection() as mcu:
            mcu.set("counter", 0)
            assert mcu.get("counter") == 0
    """

    def __init__(
        self,
        timeout_ms: int = 500,
        retries: int = 3,
        inter_cmd_delay_ms: int = 0,
    ):
        """Initialize from ``~/.ramgs/state.json``.

        The serial port is **not** opened here -- call :meth:`open` or use
        the instance as a context manager.

        Args:
            timeout_ms: Per-attempt response timeout in milliseconds.
            retries: Maximum number of retries per request.
            inter_cmd_delay_ms: Minimum gap between consecutive commands (ms).

        Raises:
            ConnectionError: state.json does not exist or lacks connection info.
            SymbolError: Symbols file is missing or unreadable.
        """
        # 1. Read state.json
        state = StateManager.load_state()
        if not state or not state.get('port_name'):
            raise ConnectionError(
                "No connection config found. "
                "Run 'ramgs open --name <port> --baud <baud>' first."
            )

        # 2. Stash configuration (do NOT open the port yet)
        self._port_name: str = state['port_name']
        self._baud_rate: int = state.get('baud_rate', 9600)
        self._little_endian: bool = state.get('little_endian', True)
        self._symbols_file: Optional[str] = state.get('symbols_file')

        # 3. Load symbol file
        if not self._symbols_file or not os.path.exists(self._symbols_file):
            raise SymbolError(
                "No symbols file found. "
                "Run 'ramgs create <elf_file>' first."
            )
        try:
            self._resolver = SymbolResolver(self._symbols_file)
        except Exception as exc:
            raise SymbolError(f"Failed to load symbols: {exc}") from exc

        # 4. Timing parameters
        self._timeout_ms = timeout_ms
        self._retries = retries
        self._inter_cmd_delay_ms = inter_cmd_delay_ms
        self._last_cmd_time: Optional[float] = None

        # 5. Connection objects (created on open)
        self._serial_mgr: Optional[SerialManager] = None
        self._protocol: Optional[Protocol] = None
        self._converter = TypeConverter(self._little_endian)

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Open the serial port and prepare the protocol layer.

        Raises:
            ConnectionError: If the serial port cannot be opened.
        """
        if self._serial_mgr is not None and self._serial_mgr.is_open():
            return  # already open

        self._serial_mgr = SerialManager()
        success, error = self._serial_mgr.open(self._port_name, self._baud_rate)
        if not success:
            self._serial_mgr = None
            raise ConnectionError(
                f"Failed to open {self._port_name}: {error}"
            )

        self._protocol = Protocol(
            self._serial_mgr.get_port(), self._little_endian
        )
        self._protocol.timeout_ms = self._timeout_ms
        self._protocol.max_retries = self._retries

    def close(self) -> None:
        """Close the serial port. Safe to call multiple times."""
        if self._serial_mgr is not None:
            self._serial_mgr.close()
            self._serial_mgr = None
        self._protocol = None
        self._last_cmd_time = None

    def __enter__(self) -> "McuConnection":
        self.open()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    @property
    def is_connected(self) -> bool:
        """True when the serial port is open."""
        return (self._serial_mgr is not None
                and self._serial_mgr.is_open())

    def ping(self) -> bool:
        """Send a PING and return True if the MCU answers with PONG."""
        self._ensure_connected()
        self._enforce_delay()
        success, _error = self._protocol.ping()
        return success

    # ------------------------------------------------------------------
    # Core read / write
    # ------------------------------------------------------------------

    def get(self, var_name: str) -> Any:
        """Read a single variable from the MCU.

        Args:
            var_name: Variable path (e.g. ``"struct.member[0]"``).

        Returns:
            Decoded Python value (int, float, bool).

        Raises:
            SymbolError: Variable not found.
            CommunicationError: Read failed.
        """
        self._ensure_connected()
        self._enforce_delay()

        resolved = self._resolve_var(var_name)
        var_info = self._make_var_info(resolved)

        success, data_list, error = self._protocol.read_variables([var_info])
        if not success:
            raise CommunicationError(f"Read '{var_name}' failed: {error}")

        return self._decode_value(resolved, data_list[0])

    def get_many(self, *var_names: str) -> Dict[str, Any]:
        """Read multiple variables in a single protocol transaction.

        Returns:
            ``{var_name: value, ...}`` in the order requested.
        """
        if not var_names:
            return {}

        self._ensure_connected()
        self._enforce_delay()

        resolved_list = [self._resolve_var(n) for n in var_names]
        var_infos = [self._make_var_info(r) for r in resolved_list]

        success, data_list, error = self._protocol.read_variables(var_infos)
        if not success:
            raise CommunicationError(f"Read failed: {error}")

        result: Dict[str, Any] = {}
        for name, resolved, data in zip(var_names, resolved_list, data_list):
            result[name] = self._decode_value(resolved, data)
        return result

    def set(self, var_name: str, value: Any) -> None:
        """Write a single variable to the MCU.

        Args:
            var_name: Variable path.
            value: Python value to write.

        Raises:
            SymbolError: Variable not found.
            ValueError: Encoding failure.
            CommunicationError: Write failed.
        """
        self._ensure_connected()
        self._enforce_delay()

        resolved = self._resolve_var(var_name)
        var_info = self._make_var_info(resolved)
        encoded = self._encode_value(resolved, value)

        success, error = self._protocol.write_variables(
            [var_info], [encoded]
        )
        if not success:
            raise CommunicationError(f"Write '{var_name}' failed: {error}")

    def set_many(self, **assignments: Any) -> None:
        """Write multiple variables using keyword arguments.

        Example::

            mcu.set_many(counter=0, speed=100)

        Note: variable names must be valid Python identifiers. For names
        containing dots or brackets use :meth:`set_dict`.
        """
        if not assignments:
            return
        self._write_dict(assignments)

    def set_dict(self, assignments: Dict[str, Any]) -> None:
        """Write multiple variables from a dict.

        Example::

            mcu.set_dict({"struct.field": 1, "arr[0]": 42})
        """
        if not assignments:
            return
        self._write_dict(assignments)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def wait_until(
        self,
        var_name: str,
        condition: Union[Any, Callable[[Any], bool]],
        timeout_s: float = 5.0,
        poll_interval_ms: int = 100,
    ) -> Any:
        """Poll a variable until *condition* is satisfied.

        Args:
            var_name: Variable to poll.
            condition: Either a concrete value to compare with ``==``,
                       or a callable ``(value) -> bool``.
            timeout_s: Maximum wait time in seconds.
            poll_interval_ms: Delay between polls in milliseconds.

        Returns:
            The value that satisfied the condition.

        Raises:
            TimeoutError: Condition not met within *timeout_s*.
        """
        if callable(condition):
            predicate = condition
        else:
            expected = condition
            predicate = lambda v: v == expected  # noqa: E731

        deadline = time.monotonic() + timeout_s
        last_value = None

        while True:
            last_value = self.get(var_name)
            if predicate(last_value):
                return last_value

            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Timeout waiting for '{var_name}' "
                    f"(last={last_value}, timeout={timeout_s}s)",
                    var_name=var_name,
                    timeout_s=timeout_s,
                    last_value=last_value,
                )

            time.sleep(poll_interval_ms / 1000.0)

    def get_raw(self, var_name: str) -> bytes:
        """Read raw bytes for a variable (no type decoding).

        Args:
            var_name: Variable path.

        Returns:
            Raw bytes as received from the MCU.
        """
        self._ensure_connected()
        self._enforce_delay()

        resolved = self._resolve_var(var_name)
        var_info = self._make_var_info(resolved)

        success, data_list, error = self._protocol.read_variables([var_info])
        if not success:
            raise CommunicationError(f"Read '{var_name}' failed: {error}")

        return data_list[0]

    # ------------------------------------------------------------------
    # Timing configuration
    # ------------------------------------------------------------------

    @property
    def inter_cmd_delay_ms(self) -> int:
        return self._inter_cmd_delay_ms

    @inter_cmd_delay_ms.setter
    def inter_cmd_delay_ms(self, value: int) -> None:
        self._inter_cmd_delay_ms = max(0, value)

    @property
    def timeout_ms(self) -> int:
        return self._timeout_ms

    @timeout_ms.setter
    def timeout_ms(self, value: int) -> None:
        self._timeout_ms = max(1, value)
        if self._protocol is not None:
            self._protocol.timeout_ms = self._timeout_ms

    # ------------------------------------------------------------------
    # Information properties
    # ------------------------------------------------------------------

    @property
    def symbols(self) -> List[str]:
        """All available variable names (sorted)."""
        return self._resolver.list_symbols()

    @property
    def port_name(self) -> str:
        return self._port_name

    @property
    def baud_rate(self) -> int:
        return self._baud_rate

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> None:
        if not self.is_connected:
            raise ConnectionError(
                "Not connected. Call open() or use a context manager."
            )

    def _enforce_delay(self) -> None:
        """Sleep if needed to respect inter_cmd_delay_ms."""
        if self._inter_cmd_delay_ms > 0 and self._last_cmd_time is not None:
            elapsed_ms = (time.time() - self._last_cmd_time) * 1000
            remaining_ms = self._inter_cmd_delay_ms - elapsed_ms
            if remaining_ms > 0:
                time.sleep(remaining_ms / 1000.0)
        self._last_cmd_time = time.time()

    def _resolve_var(self, var_name: str) -> ResolvedSymbol:
        """Parse and resolve a variable name to a ResolvedSymbol."""
        try:
            var_path = VariableParser.parse_variable(var_name)
        except builtins.ValueError:
            raise SymbolError(f"Invalid variable syntax: {var_name}")

        resolved = self._resolver.resolve(var_path)
        if resolved is None:
            raise SymbolError(f"Variable not found: {var_name}")
        return resolved

    @staticmethod
    def _make_var_info(resolved: ResolvedSymbol) -> VarInfo:
        return VarInfo(
            address=resolved.address,
            size=resolved.size,
            bit_offset=resolved.bit_offset,
            bit_size=resolved.bit_size,
        )

    def _decode_value(self, resolved: ResolvedSymbol, data: bytes) -> Any:
        if resolved.bit_offset != NO_BITFIELD:
            return self._converter.decode_bitfield(
                data[0], resolved.bit_size, resolved.bit_offset
            )
        return self._converter.decode(data, resolved.base_type)

    def _encode_value(self, resolved: ResolvedSymbol, value: Any) -> bytes:
        try:
            if resolved.bit_offset != NO_BITFIELD:
                return bytes([int(value) & ((1 << resolved.bit_size) - 1)])
            return self._converter.encode(
                value, resolved.base_type, resolved.size
            )
        except Exception as exc:
            raise ValueError(
                f"Cannot encode {value!r} for '{resolved.name}' "
                f"(type={resolved.base_type}, size={resolved.size}): {exc}"
            ) from exc

    def _write_dict(self, assignments: Dict[str, Any]) -> None:
        """Shared implementation for set_many / set_dict."""
        self._ensure_connected()
        self._enforce_delay()

        resolved_list: List[ResolvedSymbol] = []
        var_infos: List[VarInfo] = []
        data_list: List[bytes] = []

        for name, value in assignments.items():
            resolved = self._resolve_var(name)
            resolved_list.append(resolved)
            var_infos.append(self._make_var_info(resolved))
            data_list.append(self._encode_value(resolved, value))

        success, error = self._protocol.write_variables(var_infos, data_list)
        if not success:
            raise CommunicationError(f"Write failed: {error}")
