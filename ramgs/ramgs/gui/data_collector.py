"""
Data Collector - Background thread for sampling MCU variables
"""

import time
from typing import List, Dict, Optional

from PySide6.QtCore import QThread, Signal, Slot

from ..serial_manager import SerialManager
from ..protocol import Protocol, VarInfo
from ..symbol_resolver import SymbolResolver
from ..variable_parser import parse_variables
from ..type_converter import TypeConverter
from ..config import NO_BITFIELD


class DataCollector(QThread):
    """Background thread for collecting variable data"""

    data_received = Signal(dict)  # Emits data point with timestamp and values
    error_occurred = Signal(str)  # Emits error message
    collection_stopped = Signal()  # Emitted when collection stops

    # Stop collection after this many consecutive errors
    MAX_CONSECUTIVE_ERRORS = 10

    def __init__(
        self,
        port_name: str,
        baud_rate: int,
        little_endian: bool,
        symbols_file: str,
        variables: List[dict],
        interval_ms: int,
        parent=None
    ):
        super().__init__(parent)

        self._port_name = port_name
        self._baud_rate = baud_rate
        self._little_endian = little_endian
        self._symbols_file = symbols_file
        self._variables = variables
        self._interval_ms = interval_ms

        self._running = False
        self._error_count = 0
        self._consecutive_errors = 0

    @property
    def is_running(self) -> bool:
        """Check if collection is running"""
        return self._running

    @property
    def error_count(self) -> int:
        """Get total error count"""
        return self._error_count

    def stop(self):
        """Request collection to stop"""
        self._running = False

    def run(self):
        """Main collection loop"""
        self._running = True
        self._error_count = 0
        self._consecutive_errors = 0

        # Open serial connection
        serial_mgr = SerialManager()
        success, error = serial_mgr.open(self._port_name, self._baud_rate)

        if not success:
            self.error_occurred.emit(f"Failed to open port: {error}")
            self._running = False
            self.collection_stopped.emit()
            return

        try:
            # Initialize protocol and converter
            protocol = Protocol(serial_mgr.get_port(), self._little_endian)
            converter = TypeConverter(self._little_endian)

            # Load symbols and resolve variables
            resolver = SymbolResolver(self._symbols_file)
            resolved_vars = self._resolve_variables(resolver)

            if not resolved_vars:
                self.error_occurred.emit("No valid variables to monitor")
                self._running = False
                self.collection_stopped.emit()
                return

            # Create VarInfo list
            var_infos = [vi for _, _, vi in resolved_vars]

            interval_sec = self._interval_ms / 1000.0

            while self._running:
                start_time = time.time()

                # Read variables
                success, data_list, error = protocol.read_variables(var_infos)

                if not success:
                    self._error_count += 1
                    self._consecutive_errors += 1
                    self.error_occurred.emit(error or "Read failed")

                    if self._consecutive_errors >= self.MAX_CONSECUTIVE_ERRORS:
                        self.error_occurred.emit(
                            f"Too many consecutive errors ({self.MAX_CONSECUTIVE_ERRORS}), stopping"
                        )
                        break
                else:
                    self._consecutive_errors = 0

                    # Build data point
                    data_point = {
                        'timestamp': time.time()
                    }

                    for (var_id, resolved, _), data in zip(resolved_vars, data_list):
                        if resolved.bit_offset != NO_BITFIELD:
                            value = converter.decode_bitfield(
                                data[0], resolved.bit_size, resolved.bit_offset
                            )
                        else:
                            value = converter.decode(data, resolved.base_type)

                        data_point[var_id] = float(value)

                    self.data_received.emit(data_point)

                # Sleep for remaining interval
                elapsed = time.time() - start_time
                sleep_time = max(0, interval_sec - elapsed)
                if sleep_time > 0 and self._running:
                    time.sleep(sleep_time)

        except Exception as e:
            self.error_occurred.emit(f"Collection error: {e}")

        finally:
            serial_mgr.close()
            self._running = False
            self.collection_stopped.emit()

    def _resolve_variables(self, resolver: SymbolResolver) -> List[tuple]:
        """Resolve variable configs to (var_id, resolved_symbol, var_info) tuples"""
        results = []

        for var_config in self._variables:
            var_path = var_config.get('path', '')
            var_id = var_config.get('id', var_path)

            try:
                # Parse the variable path
                var_paths = parse_variables(var_path)
                if not var_paths:
                    continue

                var_path_obj = var_paths[0]
                resolved = resolver.resolve(var_path_obj)

                if not resolved:
                    self.error_occurred.emit(f"Variable not found: {var_path}")
                    continue

                var_info = VarInfo(
                    address=resolved.address,
                    size=resolved.size,
                    bit_offset=resolved.bit_offset if resolved.bit_offset != NO_BITFIELD else NO_BITFIELD,
                    bit_size=resolved.bit_size if resolved.bit_size != NO_BITFIELD else NO_BITFIELD
                )

                results.append((var_id, resolved, var_info))

            except Exception as e:
                self.error_occurred.emit(f"Error resolving {var_path}: {e}")

        return results
