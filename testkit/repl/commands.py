"""
Commands - Command parsing and execution for REPL

Handles:
- Slash commands (/quit, /open, /get, etc.)
- Shortcut syntax (var -> /get var, var=value -> /set var=value)
"""

import os
import re
import subprocess
import sys
import time
from datetime import datetime
from typing import Tuple, Optional, List, TYPE_CHECKING

from ..serial_manager import SerialManager
from ..variable_parser import parse_variables, parse_assignments
from ..protocol import VarInfo
from ..config import NO_BITFIELD, DEFAULT_SYMBOLS_FILE
from ..state_manager import StateManager

# Windows keyboard input detection
if sys.platform == 'win32':
    import msvcrt
else:
    import select

if TYPE_CHECKING:
    from .session import ReplSession


HELP_TEXT = """
RAMViewer Interactive Mode

Commands:
  /help              Show this help message
  /quit, /exit       Exit interactive mode (state preserved for next session)
  /quit -f           Force exit (close connection, clear state)

  /ports             List available serial ports
  /status            Show connection status

  /open              Open serial port connection
                     Usage: /open --name COM1 --baud 9600 --endian little

  /close             Close serial port connection

  /create <elf>      Generate symbols.json from ELF file
                     Options: -o/--output <file>  Output file (default: symbols.json)
                     Example: /create firmware.elf
                              /create firmware.elf -o my_symbols.json

  /load <file>       Load symbols file (symbols.json)

  /get <vars>        Read variable values
                     Options: -i/--interval <ms>  Repeat interval in milliseconds
                              -c/--count <n>      Number of repeats (0=infinite)
                     Examples: /get counter
                               /get -i 100 val1,val2
                               /get -i 500 -c 10 struct.member

  /set <assigns>     Write variable values
                     Options: -i/--interval <ms>  Repeat interval in milliseconds
                              -c/--count <n>      Number of repeats (0=infinite)
                     Examples: /set counter=0
                               /set -i 100 val=1

  /chart <vars>      Display realtime chart of variable values
                     Options: -i/--interval <ms>  Sampling interval (required)
                              -c/--count <n>      Number of samples (0=infinite)
                     Examples: /chart counter -i 100
                               /chart val1,val2 -i 50 -c 200

  /image <vars>      Generate static chart image from variable data
                     Options: -i/--interval <ms>  Sampling interval (required)
                              -c/--count <n>      Number of samples (required, >0)
                     Saves PNG to ramgs_tmp_imgs/ and outputs file path.
                     Examples: /image counter -i 100 -c 50
                               /image val1,val2 -i 50 -c 100

  /display <buffer>  Generate display panel image from buffer data
                     Options: -d/--design <file>  Panel design file (required)
                              -i/--interval <ms>  Repeat interval in milliseconds
                              -c/--count <n>      Number of renders
                     Examples: /display display_buff[0..15] -d panel.panel.json
                               /display lcd_buffer[0,16] -d panel.json -i 500 -c 10

  /designer [file]   Launch Panel Designer GUI
                     Examples: /designer
                               /designer my_panel.panel.json

  /snapshot          Capture image from camera
                     Options: -d/--device <n>   Camera device index (default: 0)
                              -l/--list         List available cameras
                              -o/--output <f>   Custom output filename
                              -i/--interval <ms> Capture interval in milliseconds
                              -c/--count <n>    Number of captures (0=infinite)
                     Examples: /snapshot
                               /snapshot -d 1
                               /snapshot --list
                               /snapshot -i 1000 -c 5

  /recognize <image> Recognize display panel elements from image
                     Options: -d/--design <file>  Panel design file (required)
                              --json              Output in JSON format
                              -t/--threshold <n>  Brightness threshold (default: 0.4)
                     Examples: /recognize photo.jpg -d panel.panel.json
                               /recognize photo.jpg -d panel.json --json
                               /recognize photo.jpg -d panel.json -t 0.5

Shortcuts:
  varname            Same as '/get varname'
  varname=value      Same as '/set varname=value'
  struct.member      Same as '/get struct.member'

Variable Syntax:
  simple_var         Simple variable
  struct.member      Structure member access
  array[0]           Array element
  array[0..4]        Array range (reads array[0] to array[4])
  struct.arr[2].f    Combined access
  var@filename       File-specific variable

Note: Press ESC to stop repeated operations or chart data collection.
"""


class CommandHandler:
    """Parse and execute REPL commands"""

    def __init__(self, session: 'ReplSession'):
        self.session = session

    def parse_and_execute(self, line: str) -> Tuple[bool, str]:
        """
        Parse and execute a command line.

        Args:
            line: User input line

        Returns:
            (should_exit, output_message)
        """
        line = line.strip()

        if not line:
            return False, ''

        # Slash commands
        if line.startswith('/'):
            return self._execute_command(line)

        # Shortcut syntax
        return self._execute_shortcut(line)

    def _execute_command(self, line: str) -> Tuple[bool, str]:
        """Execute a slash command"""
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ''

        handlers = {
            '/quit': self._cmd_quit,
            '/exit': self._cmd_quit,
            '/help': self._cmd_help,
            '/ports': self._cmd_ports,
            '/status': self._cmd_status,
            '/open': self._cmd_open,
            '/close': self._cmd_close,
            '/create': self._cmd_create,
            '/load': self._cmd_load,
            '/get': self._cmd_get,
            '/set': self._cmd_set,
            '/chart': self._cmd_chart,
            '/image': self._cmd_image,
            '/display': self._cmd_display,
            '/designer': self._cmd_designer,
            '/snapshot': self._cmd_snapshot,
            '/recognize': self._cmd_recognize,
        }

        handler = handlers.get(cmd)
        if handler:
            return handler(args)
        else:
            return False, f"Unknown command: {cmd}. Type /help for available commands."

    def _execute_shortcut(self, line: str) -> Tuple[bool, str]:
        """Execute shortcut syntax (var or var=value)"""
        # Check for assignment
        if '=' in line:
            return self._cmd_set(line)
        else:
            return self._cmd_get(line)

    # Command handlers

    def _cmd_quit(self, args: str) -> Tuple[bool, str]:
        """Handle /quit command"""
        force = '-f' in args.split()
        if force:
            self.session.close_port()
            return True, "Goodbye! (connection closed, state cleared)"
        else:
            self.session.close_port_preserve_state()
            return True, "Goodbye! (state preserved for next session)"

    def _cmd_help(self, args: str) -> Tuple[bool, str]:
        """Handle /help command"""
        return False, HELP_TEXT.strip()

    def _cmd_ports(self, args: str) -> Tuple[bool, str]:
        """Handle /ports command"""
        ports = SerialManager.list_ports()

        if not ports:
            return False, "No serial ports found"

        lines = []
        for port_name, description, hwid in ports:
            lines.append(f"  {port_name}: {description}")

        return False, "Available ports:\n" + '\n'.join(lines)

    def _cmd_status(self, args: str) -> Tuple[bool, str]:
        """Handle /status command"""
        lines = []

        if self.session.is_connected:
            lines.append("Connection: Connected")
            lines.append(f"  Port: {self.session.port_name}")
            lines.append(f"  Baud: {self.session.baud_rate}")
            lines.append(f"  Endian: {'little' if self.session.little_endian else 'big'}")
        else:
            lines.append("Connection: Not connected")

        if self.session.has_symbols:
            count = self.session.get_symbol_count()
            lines.append(f"Symbols: Loaded ({count} symbols)")
            lines.append(f"  File: {self.session.symbols_file}")
        else:
            lines.append("Symbols: Not loaded")

        return False, '\n'.join(lines)

    def _cmd_open(self, args: str) -> Tuple[bool, str]:
        """Handle /open command"""
        # Parse arguments
        name = self._extract_option(args, '--name')
        baud = self._extract_option(args, '--baud', '9600')
        endian = self._extract_option(args, '--endian', 'little')

        if not name:
            return False, "Error: --name is required.\nUsage: /open --name COM1 --baud 9600 --endian little"

        try:
            baud_int = int(baud)
        except ValueError:
            return False, f"Error: Invalid baud rate: {baud}"

        if endian not in ('little', 'big'):
            return False, f"Error: Invalid endian: {endian}. Use 'little' or 'big'."

        success, error = self.session.open_port(name, baud_int, endian)

        if success:
            return False, f"Connected to {name} at {baud_int} baud ({endian}-endian)"
        else:
            return False, f"Error: Failed to open {name}: {error}"

    def _cmd_close(self, args: str) -> Tuple[bool, str]:
        """Handle /close command"""
        if not self.session.is_connected:
            return False, "Not connected"

        port_name = self.session.port_name
        self.session.close_port()
        return False, f"Disconnected from {port_name}"

    def _cmd_create(self, args: str) -> Tuple[bool, str]:
        """Handle /create command - generate symbols.json from ELF file"""
        # Parse -o/--output option
        output = self._extract_option(args, '-o') or self._extract_option(args, '--output')
        if output:
            # Remove the option from args to get the ELF file path
            args = re.sub(r'(?:-o|--output)\s+\S+', '', args).strip()
        else:
            output = DEFAULT_SYMBOLS_FILE

        elf_file = args.strip()
        if not elf_file:
            return False, "Error: Please specify ELF file path.\nUsage: /create firmware.elf [-o output.json]"

        if not os.path.exists(elf_file):
            return False, f"Error: ELF file not found: {elf_file}"

        # Find elfsym.exe
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        elfsym_path = os.path.join(script_dir, 'elfsymbol', 'elfsym.exe')

        if not os.path.exists(elfsym_path):
            # Try relative to current directory
            elfsym_path = os.path.join('elfsymbol', 'elfsym.exe')

        if not os.path.exists(elfsym_path):
            return False, "Error: elfsym.exe not found. Please ensure elfsymbol/elfsym.exe exists."

        # Run elfsym.exe
        cmd = [elfsym_path, elf_file, '-o', output]
        print(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or f"Exit code: {result.returncode}"
                return False, f"Error: elfsym.exe failed: {error_msg}"

            # Update state with new symbols file
            if StateManager.is_connected():
                StateManager.set_symbols_file(os.path.abspath(output))

            # Auto-load the generated symbols
            success, error = self.session.load_symbols(output)
            if success:
                count = self.session.get_symbol_count()
                return False, f"Generated: {output}\nLoaded {count} symbols"
            else:
                return False, f"Generated: {output}\nWarning: Failed to load symbols: {error}"

        except FileNotFoundError:
            return False, "Error: Failed to run elfsym.exe"
        except Exception as e:
            return False, f"Error: {e}"

    def _cmd_load(self, args: str) -> Tuple[bool, str]:
        """Handle /load command"""
        file_path = args.strip()

        if not file_path:
            return False, "Error: Please specify symbols file path.\nUsage: /load symbols.json"

        success, error = self.session.load_symbols(file_path)

        if success:
            count = self.session.get_symbol_count()
            return False, f"Loaded {count} symbols from {file_path}"
        else:
            return False, f"Error: {error}"

    def _cmd_get(self, args: str) -> Tuple[bool, str]:
        """Handle /get command or get shortcut"""
        if not self.session.is_connected:
            return False, "Error: Not connected. Use /open first."

        if not self.session.has_symbols:
            return False, "Error: No symbols loaded. Use /load first."

        # Parse options
        interval, count, variables = self._parse_interval_options(args)

        if not variables:
            return False, "Error: Please specify variables to read.\nUsage: /get [-i ms] [-c n] var1,var2"

        try:
            var_paths = parse_variables(variables)
        except ValueError as e:
            return False, f"Error: {e}"

        if not var_paths:
            return False, "Error: No variables specified"

        # Resolve and read variables
        try:
            if interval is not None:
                # Repeated execution
                return self._do_repeated_get(var_paths, interval, count)
            else:
                # Single execution
                results = self._read_variables(var_paths)
                return False, ','.join(results)
        except Exception as e:
            return False, f"Error: {e}"

    def _cmd_set(self, args: str) -> Tuple[bool, str]:
        """Handle /set command or set shortcut"""
        if not self.session.is_connected:
            return False, "Error: Not connected. Use /open first."

        if not self.session.has_symbols:
            return False, "Error: No symbols loaded. Use /load first."

        # Parse options
        interval, count, assignments_str = self._parse_interval_options(args)

        if not assignments_str:
            return False, "Error: Please specify assignments.\nUsage: /set [-i ms] [-c n] var=value"

        try:
            assignments = parse_assignments(assignments_str)
        except ValueError as e:
            return False, f"Error: {e}"

        if not assignments:
            return False, "Error: No assignments specified"

        # Resolve, encode, and write variables
        try:
            if interval is not None:
                # Repeated execution
                return self._do_repeated_set(assignments, interval, count)
            else:
                # Single execution
                self._write_variables(assignments)
                return False, "OK"
        except Exception as e:
            return False, f"Error: {e}"

    # Maximum number of variables for chart
    MAX_CHART_VARIABLES = 8

    def _cmd_chart(self, args: str) -> Tuple[bool, str]:
        """Handle /chart command - display realtime chart"""
        if not self.session.is_connected:
            return False, "Error: Not connected. Use /open first."

        if not self.session.has_symbols:
            return False, "Error: No symbols loaded. Use /load first."

        # Parse options
        interval, count, variables = self._parse_interval_options(args)

        if interval is None:
            return False, "Error: --interval is required for chart command.\nUsage: /chart -i <ms> [-c <n>] var1,var2"

        if not variables:
            return False, "Error: Please specify variables to chart.\nUsage: /chart -i <ms> [-c <n>] var1,var2"

        try:
            var_paths = parse_variables(variables)
        except ValueError as e:
            return False, f"Error: {e}"

        if not var_paths:
            return False, "Error: No variables specified"

        if len(var_paths) > self.MAX_CHART_VARIABLES:
            return False, f"Error: Maximum {self.MAX_CHART_VARIABLES} variables allowed for chart"

        # Execute chart
        try:
            return self._do_chart_get(var_paths, interval, count)
        except Exception as e:
            return False, f"Error: {e}"

    def _do_chart_get(self, var_paths, interval_ms: int,
                      count: int) -> Tuple[bool, str]:
        """Execute get operation with chart display"""
        from ..chart import ChartDataQueue, ChartConfig, DataPoint

        resolver = self.session.symbol_resolver
        protocol = self.session.protocol
        converter = self.session.type_converter

        # Resolve all variables first
        resolved_vars = []
        var_infos = []

        for var_path in var_paths:
            resolved = resolver.resolve(var_path)
            if not resolved:
                raise ValueError(f"Variable not found: {var_path}")

            var_info = VarInfo(
                address=resolved.address,
                size=resolved.size,
                bit_offset=resolved.bit_offset if resolved.bit_offset != NO_BITFIELD else NO_BITFIELD,
                bit_size=resolved.bit_size if resolved.bit_size != NO_BITFIELD else NO_BITFIELD,
            )
            resolved_vars.append((var_path, resolved))
            var_infos.append(var_info)

        # Get variable names as strings
        var_names = [str(vp) for vp in var_paths]

        # Create chart configuration
        config = ChartConfig(
            var_names=var_names,
            update_interval_ms=min(interval_ms, 100)
        )

        # Start chart window
        data_queue = ChartDataQueue()
        if not data_queue.start_chart(config):
            raise ValueError("Failed to start chart window")

        iteration = 0
        interval_sec = interval_ms / 1000.0
        stopped = False

        print("Chart window opened. Press ESC to stop data collection...")

        try:
            while not stopped:
                if self._check_esc_pressed():
                    stopped = True
                    break

                iteration += 1
                if count > 0 and iteration > count:
                    break

                # Read variables
                success, data_list, error = protocol.read_variables(var_infos)
                if not success:
                    print(f"[{iteration}] Error: {error}")
                else:
                    # Decode values
                    values = []
                    for (var_path, resolved), data in zip(resolved_vars, data_list):
                        if resolved.bit_offset != NO_BITFIELD:
                            value = converter.decode_bitfield(data[0], resolved.bit_size,
                                                               resolved.bit_offset)
                        else:
                            value = converter.decode(data, resolved.base_type)
                        values.append(float(value))

                    # Send to chart
                    data_point = DataPoint.create(var_names, values)
                    data_queue.put_data(data_point)

                # Wait for next interval
                if count == 0 or iteration < count:
                    if self._sleep_with_esc_check(interval_sec):
                        stopped = True
                        break

            # Signal collection stopped
            data_queue.stop_collection()

            if stopped:
                print("\nData collection stopped. Chart window remains open for analysis.")
                print("Close the chart window to continue...")
            else:
                print(f"\nCollected {iteration} samples. Chart window remains open.")
                print("Close the chart window to continue...")

            # Wait for chart window to be closed
            data_queue.wait_for_close()
            return False, ""

        except KeyboardInterrupt:
            return False, "\nInterrupted."
        finally:
            data_queue.close()

    # Maximum number of variables for image
    MAX_IMAGE_VARIABLES = 8

    def _cmd_image(self, args: str) -> Tuple[bool, str]:
        """Handle /image command - generate static chart image"""
        if not self.session.is_connected:
            return False, "Error: Not connected. Use /open first."

        if not self.session.has_symbols:
            return False, "Error: No symbols loaded. Use /load first."

        # Parse options
        interval, count, variables = self._parse_interval_options(args)

        if interval is None:
            return False, "Error: --interval is required for image command.\nUsage: /image -i <ms> -c <n> var1,var2"

        if count is None or count <= 0:
            return False, "Error: --count is required for image command (must be > 0).\nUsage: /image -i <ms> -c <n> var1,var2"

        if not variables:
            return False, "Error: Please specify variables to image.\nUsage: /image -i <ms> -c <n> var1,var2"

        try:
            var_paths = parse_variables(variables)
        except ValueError as e:
            return False, f"Error: {e}"

        if not var_paths:
            return False, "Error: No variables specified"

        if len(var_paths) > self.MAX_IMAGE_VARIABLES:
            return False, f"Error: Maximum {self.MAX_IMAGE_VARIABLES} variables allowed for image"

        # Execute image generation
        try:
            return self._do_image_get(var_paths, interval, count)
        except Exception as e:
            return False, f"Error: {e}"

    def _do_image_get(self, var_paths, interval_ms: int,
                      count: int) -> Tuple[bool, str]:
        """Collect data and generate static chart image"""
        import time as time_module
        from ..image_generator import generate_image
        from ..progress import ProgressBar

        resolver = self.session.symbol_resolver
        protocol = self.session.protocol
        converter = self.session.type_converter

        # Resolve all variables first
        resolved_vars = []
        var_infos = []

        for var_path in var_paths:
            resolved = resolver.resolve(var_path)
            if not resolved:
                raise ValueError(f"Variable not found: {var_path}")

            var_info = VarInfo(
                address=resolved.address,
                size=resolved.size,
                bit_offset=resolved.bit_offset if resolved.bit_offset != NO_BITFIELD else NO_BITFIELD,
                bit_size=resolved.bit_size if resolved.bit_size != NO_BITFIELD else NO_BITFIELD,
            )
            resolved_vars.append((var_path, resolved))
            var_infos.append(var_info)

        # Get variable names as strings
        var_names = [str(vp) for vp in var_paths]

        # Data storage
        timestamps = []
        data = {name: [] for name in var_names}
        start_time = None

        iteration = 0
        interval_sec = interval_ms / 1000.0
        stopped = False
        error_count = 0

        # Initialize progress bar
        progress = ProgressBar(total=count, prefix="Collecting...")
        progress.update(0)

        while not stopped and iteration < count:
            if self._check_esc_pressed():
                stopped = True
                break

            iteration += 1

            # Read variables
            success, data_list, error = protocol.read_variables(var_infos)
            if not success:
                progress.clear()
                print(f"[{iteration}] Error: {error}")
                error_count += 1
                progress.update(iteration)
            else:
                # Record timestamp
                current_time = time_module.time()
                if start_time is None:
                    start_time = current_time
                timestamps.append(current_time - start_time)

                # Decode and store values
                for (var_path, resolved), raw_data in zip(resolved_vars, data_list):
                    if resolved.bit_offset != NO_BITFIELD:
                        value = converter.decode_bitfield(raw_data[0], resolved.bit_size,
                                                           resolved.bit_offset)
                    else:
                        value = converter.decode(raw_data, resolved.base_type)
                    data[str(var_path)].append(float(value))

                # Update progress bar
                progress.update(iteration)

            # Wait for next interval
            if iteration < count:
                if self._sleep_with_esc_check(interval_sec):
                    stopped = True
                    break

        # Clear progress bar before final output
        progress.finish()

        # Generate image if we have data
        if not timestamps:
            if stopped:
                return False, "Interrupted. No data collected, files not generated."
            return False, "No data collected."

        image_path, csv_path = generate_image(timestamps, data, var_names)

        if stopped:
            return False, f"Interrupted. Generated with {len(timestamps)} samples:\n  Image: {image_path}\n  CSV: {csv_path}"
        else:
            if error_count > 0:
                return False, f"Collected {len(timestamps)} samples ({error_count} errors):\n  Image: {image_path}\n  CSV: {csv_path}"
            else:
                return False, f"Collected {len(timestamps)} samples:\n  Image: {image_path}\n  CSV: {csv_path}"

    # Helper methods

    def _parse_interval_options(self, args: str) -> Tuple[Optional[int], int, str]:
        """
        Parse -i/--interval and -c/--count options from args.

        Returns:
            (interval_ms, count, remaining_args)
        """
        interval = None
        count = 0  # 0 means infinite

        # Extract -i or --interval
        interval_match = re.search(r'(?:-i|--interval)\s+(\d+)', args)
        if interval_match:
            interval = int(interval_match.group(1))
            args = args[:interval_match.start()] + args[interval_match.end():]

        # Extract -c or --count
        count_match = re.search(r'(?:-c|--count)\s+(\d+)', args)
        if count_match:
            count = int(count_match.group(1))
            args = args[:count_match.start()] + args[count_match.end():]

        return interval, count, args.strip()

    def _check_esc_pressed(self) -> bool:
        """Check if ESC key was pressed (non-blocking)"""
        if sys.platform == 'win32':
            if msvcrt.kbhit():
                key = msvcrt.getch()
                if key == b'\x1b':  # ESC key
                    return True
                # Handle extended keys
                if key in (b'\x00', b'\xe0'):
                    msvcrt.getch()
            return False
        else:
            if select.select([sys.stdin], [], [], 0)[0]:
                key = sys.stdin.read(1)
                if ord(key) == 27:  # ESC
                    return True
            return False

    def _sleep_with_esc_check(self, seconds: float) -> bool:
        """Sleep while checking for ESC key. Returns True if ESC pressed."""
        check_interval = 0.05
        elapsed = 0.0

        while elapsed < seconds:
            if self._check_esc_pressed():
                return True
            sleep_time = min(check_interval, seconds - elapsed)
            time.sleep(sleep_time)
            elapsed += sleep_time

        return False

    def _format_timestamp(self) -> str:
        """
        Format current time as timestamp string.

        Returns:
            Timestamp in format 'time:hh:mm:ss.fff'
        """
        now = datetime.now()
        return f"time:{now.strftime('%H:%M:%S')}.{now.microsecond // 1000:03d}"

    def _do_repeated_get(self, var_paths, interval_ms: int,
                         count: int) -> Tuple[bool, str]:
        """Execute repeated get operation"""
        iteration = 0
        interval_sec = interval_ms / 1000.0
        stopped = False

        print("Press ESC to stop...")

        while not stopped:
            if self._check_esc_pressed():
                stopped = True
                break

            iteration += 1
            if count > 0 and iteration > count:
                break

            try:
                results = self._read_variables(var_paths)
                timestamp = self._format_timestamp()
                print(f"{timestamp} {','.join(results)}")
            except Exception as e:
                print(f"[{iteration}] Error: {e}")

            if count == 0 or iteration < count:
                if self._sleep_with_esc_check(interval_sec):
                    stopped = True
                    break

        if stopped:
            return False, "\nStopped by user (ESC)"
        return False, ""

    def _do_repeated_set(self, assignments, interval_ms: int,
                         count: int) -> Tuple[bool, str]:
        """Execute repeated set operation"""
        iteration = 0
        interval_sec = interval_ms / 1000.0
        stopped = False

        print("Press ESC to stop...")

        while not stopped:
            if self._check_esc_pressed():
                stopped = True
                break

            iteration += 1
            if count > 0 and iteration > count:
                break

            try:
                self._write_variables(assignments)
                print(f"[{iteration}] OK")
            except Exception as e:
                print(f"[{iteration}] Error: {e}")

            if count == 0 or iteration < count:
                if self._sleep_with_esc_check(interval_sec):
                    stopped = True
                    break

        if stopped:
            return False, "\nStopped by user (ESC)"
        return False, ""

    def _extract_option(self, args: str, option: str,
                        default: Optional[str] = None) -> Optional[str]:
        """Extract option value from argument string"""
        pattern = rf'{option}\s+(\S+)'
        match = re.search(pattern, args, re.IGNORECASE)
        return match.group(1) if match else default

    def _read_variables(self, var_paths) -> List[str]:
        """Read variables and return formatted results"""
        resolver = self.session.symbol_resolver
        protocol = self.session.protocol
        converter = self.session.type_converter

        # Resolve all variables
        resolved_vars = []
        var_infos = []

        for var_path in var_paths:
            resolved = resolver.resolve(var_path)
            if not resolved:
                raise ValueError(f"Variable not found: {var_path}")

            var_info = VarInfo(
                address=resolved.address,
                size=resolved.size,
                bit_offset=resolved.bit_offset if resolved.bit_offset != NO_BITFIELD else NO_BITFIELD,
                bit_size=resolved.bit_size if resolved.bit_size != NO_BITFIELD else NO_BITFIELD,
            )
            resolved_vars.append((var_path, resolved))
            var_infos.append(var_info)

        # Read from MCU
        success, data_list, error = protocol.read_variables(var_infos)
        if not success:
            raise ValueError(f"Read failed: {error}")

        # Format results
        results = []
        for (var_path, resolved), data in zip(resolved_vars, data_list):
            if resolved.bit_offset != NO_BITFIELD:
                value = converter.decode_bitfield(data[0], resolved.bit_size, resolved.bit_offset)
            else:
                value = converter.decode(data, resolved.base_type)

            formatted = converter.format_value(value, resolved.base_type)
            results.append(f"{var_path}={formatted}")

        return results

    def _write_variables(self, assignments) -> None:
        """Write variables to MCU"""
        resolver = self.session.symbol_resolver
        protocol = self.session.protocol
        converter = self.session.type_converter

        # Resolve and encode all variables
        var_infos = []
        data_list = []

        for assignment in assignments:
            resolved = resolver.resolve(assignment.variable)
            if not resolved:
                raise ValueError(f"Variable not found: {assignment.variable}")

            # Parse and encode value
            value = converter.parse_value(assignment.value, resolved.base_type)

            if resolved.bit_offset != NO_BITFIELD:
                data = bytes([int(value) & ((1 << resolved.bit_size) - 1)])
            else:
                data = converter.encode(value, resolved.base_type, resolved.size)

            var_info = VarInfo(
                address=resolved.address,
                size=resolved.size,
                bit_offset=resolved.bit_offset if resolved.bit_offset != NO_BITFIELD else NO_BITFIELD,
                bit_size=resolved.bit_size if resolved.bit_size != NO_BITFIELD else NO_BITFIELD,
            )
            var_infos.append(var_info)
            data_list.append(data)

        # Write to MCU
        success, error = protocol.write_variables(var_infos, data_list)
        if not success:
            raise ValueError(f"Write failed: {error}")

    def _cmd_designer(self, args: str) -> Tuple[bool, str]:
        """Handle /designer command - launch Panel Designer GUI"""
        from ..designer import run_designer

        file_path = args.strip() if args.strip() else None

        # Validate file exists if specified
        if file_path and not os.path.exists(file_path):
            return False, f"Error: File not found: {file_path}"

        # Launch designer in background
        print("Launching Panel Designer...")
        run_designer(file_path)

        return False, ""

    def _cmd_display(self, args: str) -> Tuple[bool, str]:
        """Handle /display command - generate display panel image"""
        if not self.session.is_connected:
            return False, "Error: Not connected. Use /open first."

        if not self.session.has_symbols:
            return False, "Error: No symbols loaded. Use /load first."

        # Parse options
        design_file = self._extract_option(args, '-d') or self._extract_option(args, '--design')
        interval, count, buffer_var = self._parse_interval_options(args)

        # Remove design option from buffer_var
        if design_file:
            buffer_var = re.sub(r'(?:-d|--design)\s+\S+', '', buffer_var).strip()

        if not design_file:
            return False, "Error: --design is required.\nUsage: /display buffer[0..n] -d panel.panel.json"

        if not buffer_var:
            return False, "Error: Please specify buffer variable.\nUsage: /display buffer[0..n] -d panel.panel.json"

        if not os.path.exists(design_file):
            return False, f"Error: Design file not found: {design_file}"

        # Load design file
        from ..designer.display_renderer import DisplayRenderer

        renderer, error = DisplayRenderer.from_file(design_file)
        if error:
            return False, f"Error: Failed to load design file: {error}"

        # Parse buffer variable
        try:
            var_infos, resolved_vars = self._parse_buffer_variable(buffer_var)
        except ValueError as e:
            return False, f"Error: {e}"

        # Execute
        try:
            if interval is not None:
                return self._do_repeated_display(renderer, var_infos, resolved_vars, interval, count)
            else:
                buffer_data = self._read_buffer_data(var_infos)
                image_path, error = renderer.render(buffer_data)
                if error:
                    return False, f"Error: Render failed: {error}"
                return False, image_path
        except Exception as e:
            return False, f"Error: {e}"

    def _parse_buffer_variable(self, buffer_variable: str):
        """Parse buffer variable with range syntax"""
        # Parse range syntax: var[start..end] or var[start,count]
        range_match = re.match(r'(.+?)\[(\d+)\.\.(\d+)\]$', buffer_variable)
        comma_match = re.match(r'(.+?)\[(\d+),(\d+)\]$', buffer_variable)

        if range_match:
            var_name = range_match.group(1)
            start_idx = int(range_match.group(2))
            end_idx = int(range_match.group(3))
            byte_count = end_idx - start_idx + 1
        elif comma_match:
            var_name = comma_match.group(1)
            start_idx = int(comma_match.group(2))
            byte_count = int(comma_match.group(3))
        else:
            raise ValueError(
                f"Invalid buffer variable syntax: {buffer_variable}\n"
                "Use var[start..end] or var[start,count] format."
            )

        # Resolve base variable
        resolver = self.session.symbol_resolver
        var_paths = parse_variables(var_name)
        if not var_paths:
            raise ValueError(f"Invalid variable: {var_name}")

        resolved = resolver.resolve(var_paths[0])
        if not resolved:
            raise ValueError(f"Variable not found: {var_name}")

        # Create VarInfo for each byte in range
        var_infos = []
        resolved_vars = []
        base_address = resolved.address

        for i in range(byte_count):
            var_info = VarInfo(
                address=base_address + start_idx + i,
                size=1,
                bit_offset=NO_BITFIELD,
                bit_size=NO_BITFIELD,
            )
            var_infos.append(var_info)
            resolved_vars.append((f"{var_name}[{start_idx + i}]", resolved))

        return var_infos, resolved_vars

    def _read_buffer_data(self, var_infos) -> bytes:
        """Read buffer data from MCU"""
        protocol = self.session.protocol

        success, data_list, error = protocol.read_variables(var_infos)
        if not success:
            raise ValueError(f"Read failed: {error}")

        return bytes(d[0] for d in data_list)

    def _do_repeated_display(self, renderer, var_infos, resolved_vars,
                             interval_ms: int, count: int) -> Tuple[bool, str]:
        """Execute repeated display rendering"""
        iteration = 0
        interval_sec = interval_ms / 1000.0
        stopped = False

        print("Press ESC to stop...")

        while not stopped:
            if self._check_esc_pressed():
                stopped = True
                break

            iteration += 1
            if count > 0 and iteration > count:
                break

            try:
                buffer_data = self._read_buffer_data(var_infos)
                image_path, error = renderer.render(buffer_data)
                if error:
                    print(f"[{iteration}] Error: {error}")
                else:
                    print(f"[{iteration}] {image_path}")
            except Exception as e:
                print(f"[{iteration}] Error: {e}")

            if count == 0 or iteration < count:
                if self._sleep_with_esc_check(interval_sec):
                    stopped = True
                    break

        if stopped:
            return False, f"\nStopped by user (ESC). Generated {iteration - 1} images."
        return False, ""

    def _cmd_snapshot(self, args: str) -> Tuple[bool, str]:
        """Handle /snapshot command - capture image from camera"""
        from ..camera import check_opencv, list_cameras, capture_snapshot, CameraCapture

        # Check OpenCV availability
        if not check_opencv():
            return False, "Error: OpenCV not available. Install with: pip install opencv-python"

        # Parse options
        list_mode = '-l' in args.split() or '--list' in args.split()
        device = int(self._extract_option(args, '-d') or self._extract_option(args, '--device') or '0')
        output = self._extract_option(args, '-o') or self._extract_option(args, '--output')
        interval, count, _ = self._parse_interval_options(args)

        # List devices mode
        if list_mode:
            cameras = list_cameras()
            if not cameras:
                return False, "No camera devices found"

            lines = ["Available cameras:"]
            for idx, name in cameras:
                lines.append(f"  [{idx}] {name}")
            return False, '\n'.join(lines)

        # Determine execution mode
        if interval is None:
            # Single capture
            success, image_path, error = capture_snapshot(device, output)
            if not success:
                return False, f"Error: {error}"
            return False, image_path
        else:
            # Repeated capture
            if count is None:
                count = 0  # Infinite

            try:
                with CameraCapture(device) as cam:
                    return self._do_repeated_snapshot(cam, interval, count)
            except RuntimeError as e:
                return False, f"Error: {e}"

    def _do_repeated_snapshot(self, cam, interval_ms: int, count: int) -> Tuple[bool, str]:
        """Execute repeated snapshot capture (press ESC to stop)"""
        iteration = 0
        interval_sec = interval_ms / 1000.0
        stopped = False

        print("Press ESC to stop...")

        while not stopped:
            if self._check_esc_pressed():
                stopped = True
                break

            iteration += 1
            if count > 0 and iteration > count:
                break

            success, image_path, error = cam.capture()
            if not success:
                print(f"[{iteration}] Error: {error}")
            else:
                print(f"[{iteration}] {image_path}")

            if count == 0 or iteration < count:
                if self._sleep_with_esc_check(interval_sec):
                    stopped = True
                    break

        if stopped:
            return False, "\nStopped by user (ESC)"
        return False, ""

    def _cmd_recognize(self, args: str) -> Tuple[bool, str]:
        """Handle /recognize command - recognize display panel elements from image"""
        from ..recognizer import PanelRecognizer, check_opencv

        # Check OpenCV availability
        if not check_opencv():
            return False, "Error: OpenCV not available. Install with: pip install opencv-python"

        # Parse options
        design_file = self._extract_option(args, '-d') or self._extract_option(args, '--design')
        output_json = '--json' in args.split()
        threshold_str = self._extract_option(args, '-t') or self._extract_option(args, '--threshold')
        threshold = float(threshold_str) if threshold_str else 0.4

        # Remove options from args to get image path
        image_path = args
        # Remove -d/--design option
        if design_file:
            image_path = re.sub(r'(?:-d|--design)\s+\S+', '', image_path)
        # Remove --json flag
        image_path = re.sub(r'--json\b', '', image_path)
        # Remove -t/--threshold option
        image_path = re.sub(r'(?:-t|--threshold)\s+\S+', '', image_path)
        image_path = image_path.strip()

        # Validate arguments
        if not image_path:
            return False, "Error: Please specify image path.\nUsage: /recognize photo.jpg -d panel.json"

        if not design_file:
            return False, "Error: --design is required.\nUsage: /recognize photo.jpg -d panel.json"

        if not os.path.exists(image_path):
            return False, f"Error: Image file not found: {image_path}"

        if not os.path.exists(design_file):
            return False, f"Error: Design file not found: {design_file}"

        # Load design file and create recognizer
        recognizer, error = PanelRecognizer.from_file(design_file, threshold)
        if error:
            return False, f"Error: Failed to load design file: {error}"

        # Perform recognition
        result = recognizer.recognize(image_path)

        # Output result
        if output_json:
            return False, result.to_json()
        else:
            return False, result.format_cli_output()

