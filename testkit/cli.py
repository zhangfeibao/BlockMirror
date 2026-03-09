"""
CLI - Command Line Interface for RAMViewer

Commands:
    ramgs open --name COM1 --baud 9600
    ramgs close
    ramgs create <elf_file>
    ramgs load <symbols_file>
    ramgs get [--interval N] [--count N] <variables>
    ramgs set [--interval N] [--count N] <assignments>
    ramgs chart --interval N [--count N] <variables>
    ramgs gui
"""

import json
import multiprocessing
import os
import sys
import time
import subprocess
from datetime import datetime
from typing import Optional, List

import click

from .config import VERSION, DEFAULT_SYMBOLS_FILE, NO_BITFIELD
from .state_manager import StateManager
from .serial_manager import SerialManager
from .protocol import Protocol, VarInfo
from .symbol_resolver import SymbolResolver
from .variable_parser import parse_variables, parse_assignments, VariablePath
from .type_converter import TypeConverter

# Windows keyboard input detection
if sys.platform == 'win32':
    import msvcrt
else:
    # For non-Windows platforms, use select-based approach
    import select
    import tty
    import termios

# Fix Windows stdout encoding for Chinese characters
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# ESC key code
ESC_KEY = 27


def _check_esc_pressed() -> bool:
    """
    Check if ESC key was pressed (non-blocking).

    Returns:
        True if ESC was pressed, False otherwise
    """
    if sys.platform == 'win32':
        # Windows: use msvcrt
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key == b'\x1b':  # ESC key
                return True
            # Handle extended keys (arrow keys, function keys)
            if key in (b'\x00', b'\xe0'):
                msvcrt.getch()  # Consume the second byte
        return False
    else:
        # Unix/Linux/macOS: use select
        if select.select([sys.stdin], [], [], 0)[0]:
            key = sys.stdin.read(1)
            if ord(key) == ESC_KEY:
                return True
        return False


def _sleep_with_esc_check(seconds: float) -> bool:
    """
    Sleep for specified time while checking for ESC key.

    Args:
        seconds: Time to sleep in seconds

    Returns:
        True if ESC was pressed during sleep, False otherwise
    """
    check_interval = 0.05  # Check every 50ms
    elapsed = 0.0

    while elapsed < seconds:
        if _check_esc_pressed():
            return True

        sleep_time = min(check_interval, seconds - elapsed)
        time.sleep(sleep_time)
        elapsed += sleep_time

    return False


def _format_timestamp() -> str:
    """
    Format current time as timestamp string.

    Returns:
        Timestamp in format 'time:hh:mm:ss.fff'
    """
    now = datetime.now()
    return f"time:{now.strftime('%H:%M:%S')}.{now.microsecond // 1000:03d}"


def _get_symbols_file() -> Optional[str]:
    """Get path to symbols.json file"""
    # Check state first
    state_symbols = StateManager.get_symbols_file()
    if state_symbols and os.path.exists(state_symbols):
        return state_symbols

    # Check current directory
    local_symbols = DEFAULT_SYMBOLS_FILE
    if os.path.exists(local_symbols):
        return local_symbols

    return None


def _resolve_variables(resolver: SymbolResolver,
                       var_paths: List[VariablePath]) -> List[tuple]:
    """
    Resolve variable paths to VarInfo objects

    Returns:
        List of tuples (var_path, resolved_symbol, var_info)
    """
    results = []
    for var_path in var_paths:
        resolved = resolver.resolve(var_path)
        if not resolved:
            raise click.ClickException(f"Variable not found: {var_path}")

        var_info = VarInfo(
            address=resolved.address,
            size=resolved.size,
            bit_offset=resolved.bit_offset if resolved.bit_offset != NO_BITFIELD else NO_BITFIELD,
            bit_size=resolved.bit_size if resolved.bit_size != NO_BITFIELD else NO_BITFIELD,
        )
        results.append((var_path, resolved, var_info))

    return results


@click.group(invoke_without_command=True)
@click.version_option(version=VERSION, prog_name='ramgs')
@click.pass_context
def cli(ctx):
    """RAMViewer - MCU RAM Read/Write Tool"""
    if ctx.invoked_subcommand is None:
        # No subcommand -> enter interactive mode
        from .repl import Repl
        repl = Repl()
        repl.run()


@cli.command()
@click.option('--name', required=True, help='Serial port name (e.g., COM1)')
@click.option('--baud', default=9600, type=int, help='Baud rate (default: 9600)')
@click.option('--endian', type=click.Choice(['little', 'big']), default='little',
              help='Byte order (default: little)')
def open(name: str, baud: int, endian: str):
    """Open serial port connection"""
    # Test connection
    serial_mgr = SerialManager()
    success, error = serial_mgr.open(name, baud)

    if not success:
        raise click.ClickException(f"Failed to open {name}: {error}")

    # Test with ping (optional, may fail if MCU not ready)
    serial_mgr.close()

    # Save state
    little_endian = (endian == 'little')
    symbols_file = _get_symbols_file()
    StateManager.save_state(name, baud, symbols_file, little_endian)

    click.echo(f"Connected to {name} at {baud} baud ({endian}-endian)")
    if symbols_file:
        click.echo(f"Using symbols file: {symbols_file}")


@cli.command()
def close():
    """Close serial port connection"""
    if not StateManager.is_connected():
        click.echo("No active connection")
        return

    port_name = StateManager.get_port_name()
    StateManager.clear_state()
    click.echo(f"Disconnected from {port_name}")


@cli.command()
@click.argument('elf_file', type=click.Path(exists=True))
@click.option('-o', '--output', default=DEFAULT_SYMBOLS_FILE,
              help=f'Output file (default: {DEFAULT_SYMBOLS_FILE})')
def create(elf_file: str, output: str):
    """Generate symbols.json from ELF file"""
    # Find elfsym.exe
    script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    elfsym_path = os.path.join(script_dir, 'elfsymbol', 'elfsym.exe')

    if not os.path.exists(elfsym_path):
        # Try relative to current directory
        elfsym_path = os.path.join('elfsymbol', 'elfsym.exe')

    if not os.path.exists(elfsym_path):
        raise click.ClickException(
            "elfsym.exe not found. Please ensure elfsymbol/elfsym.exe exists."
        )

    # Run elfsym.exe
    cmd = [elfsym_path, elf_file, '-o', output]
    click.echo(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or f"Exit code: {result.returncode}"
            raise click.ClickException(f"elfsym.exe failed: {error_msg}")

        click.echo(f"Generated: {output}")

        # Update state with new symbols file
        if StateManager.is_connected():
            StateManager.set_symbols_file(os.path.abspath(output))

    except FileNotFoundError:
        raise click.ClickException("Failed to run elfsym.exe")


@cli.command()
@click.argument('symbols_file', type=click.Path())
def load(symbols_file: str):
    """Load symbols file for subsequent commands

    SYMBOLS_FILE: Path to symbols.json file

    Example: ramgs load my_symbols.json
    """
    # Check file exists
    if not os.path.exists(symbols_file):
        raise click.ClickException(f"File not found: {symbols_file}")

    # Validate symbols file by attempting to load it
    try:
        resolver = SymbolResolver(symbols_file)
        symbol_count = len(resolver.symbols)
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Invalid JSON format: {e}")
    except KeyError as e:
        raise click.ClickException(f"Invalid symbols file format: missing {e}")
    except Exception as e:
        raise click.ClickException(f"Failed to load symbols: {e}")

    # Persist symbols file path to state
    abs_path = os.path.abspath(symbols_file)
    state = StateManager.load_state()
    if state:
        # Update existing state
        StateManager.set_symbols_file(abs_path)
    else:
        # Create minimal state with just symbols file
        StateManager._ensure_dir()
        StateManager.STATE_FILE.write_text(
            json.dumps({"symbols_file": abs_path}, indent=2)
        )

    click.echo(f"Loaded {symbol_count} symbols from {symbols_file}")


@cli.command('get')
@click.argument('variables')
@click.option('--interval', '-i', type=int, default=None,
              help='Interval between reads in milliseconds')
@click.option('--count', '-c', type=int, default=None,
              help='Number of reads (0 for infinite, default: 1)')
def get_cmd(variables: str, interval: Optional[int], count: Optional[int]):
    """
    Get variable values

    VARIABLES: Comma-separated variable names (e.g., val1,val2,struct.member)
    """
    # Check connection state
    state = StateManager.load_state()
    if not state:
        raise click.ClickException("Not connected. Use 'ramgs open' first.")

    # Load symbols
    symbols_file = state.get('symbols_file') or _get_symbols_file()
    if not symbols_file or not os.path.exists(symbols_file):
        raise click.ClickException(
            f"Symbols file not found. Use 'ramgs create <elf_file>' first."
        )

    # Parse variables
    try:
        var_paths = parse_variables(variables)
    except ValueError as e:
        raise click.ClickException(str(e))

    if not var_paths:
        raise click.ClickException("No variables specified")

    # Resolve variables
    resolver = SymbolResolver(symbols_file)
    try:
        resolved_vars = _resolve_variables(resolver, var_paths)
    except click.ClickException:
        raise

    # Open serial port
    serial_mgr = SerialManager()
    success, error = serial_mgr.open(state['port_name'], state['baud_rate'])
    if not success:
        raise click.ClickException(f"Failed to open serial port: {error}")

    try:
        protocol = Protocol(serial_mgr.get_port(), state.get('little_endian', True))
        converter = TypeConverter(state.get('little_endian', True))

        var_infos = [vi for _, _, vi in resolved_vars]

        # Determine execution mode
        if interval is None:
            # Single execution
            _do_single_get(protocol, converter, resolved_vars, var_infos)
        else:
            # Repeated execution
            if count is None:
                count = 0  # Infinite
            _do_repeated_get(protocol, converter, resolved_vars, var_infos,
                             interval, count)

    finally:
        serial_mgr.close()


def _do_single_get(protocol: Protocol, converter: TypeConverter,
                   resolved_vars: List[tuple], var_infos: List[VarInfo]):
    """Execute single get operation"""
    success, data_list, error = protocol.read_variables(var_infos)
    if not success:
        raise click.ClickException(f"Read failed: {error}")

    # Format output
    output_parts = []
    for (var_path, resolved, _), data in zip(resolved_vars, data_list):
        if resolved.bit_offset != NO_BITFIELD:
            value = converter.decode_bitfield(data[0], resolved.bit_size, resolved.bit_offset)
        else:
            value = converter.decode(data, resolved.base_type)

        formatted = converter.format_value(value, resolved.base_type)
        output_parts.append(f"{var_path}={formatted}")

    click.echo(','.join(output_parts))


def _do_repeated_get(protocol: Protocol, converter: TypeConverter,
                     resolved_vars: List[tuple], var_infos: List[VarInfo],
                     interval_ms: int, count: int):
    """Execute repeated get operation (press ESC to stop)"""
    iteration = 0
    interval_sec = interval_ms / 1000.0
    stopped = False

    click.echo("Press ESC to stop...")

    while not stopped:
        # Check for ESC key before operation
        if _check_esc_pressed():
            stopped = True
            break

        iteration += 1
        if count > 0 and iteration > count:
            break

        success, data_list, error = protocol.read_variables(var_infos)
        if not success:
            click.echo(f"[{iteration}] Error: {error}", err=True)
        else:
            output_parts = []
            for (var_path, resolved, _), data in zip(resolved_vars, data_list):
                if resolved.bit_offset != NO_BITFIELD:
                    value = converter.decode_bitfield(data[0], resolved.bit_size,
                                                       resolved.bit_offset)
                else:
                    value = converter.decode(data, resolved.base_type)

                formatted = converter.format_value(value, resolved.base_type)
                output_parts.append(f"{var_path}={formatted}")

            timestamp = _format_timestamp()
            click.echo(f"{timestamp} {','.join(output_parts)}")

        # Wait for next interval (with ESC check)
        if count == 0 or iteration < count:
            if _sleep_with_esc_check(interval_sec):
                stopped = True
                break

    if stopped:
        click.echo("\nStopped by user (ESC)")


@cli.command('set')
@click.argument('assignments')
@click.option('--interval', '-i', type=int, default=None,
              help='Interval between writes in milliseconds')
@click.option('--count', '-c', type=int, default=None,
              help='Number of writes (0 for infinite, default: 1)')
def set_cmd(assignments: str, interval: Optional[int], count: Optional[int]):
    """
    Set variable values

    ASSIGNMENTS: Comma-separated assignments (e.g., val1=1,val2=12,val3=4)
    """
    # Check connection state
    state = StateManager.load_state()
    if not state:
        raise click.ClickException("Not connected. Use 'ramgs open' first.")

    # Load symbols
    symbols_file = state.get('symbols_file') or _get_symbols_file()
    if not symbols_file or not os.path.exists(symbols_file):
        raise click.ClickException(
            f"Symbols file not found. Use 'ramgs create <elf_file>' first."
        )

    # Parse assignments
    try:
        assignment_list = parse_assignments(assignments)
    except ValueError as e:
        raise click.ClickException(str(e))

    if not assignment_list:
        raise click.ClickException("No assignments specified")

    # Resolve variables and prepare data
    resolver = SymbolResolver(symbols_file)
    converter = TypeConverter(state.get('little_endian', True))

    resolved_list = []
    for assignment in assignment_list:
        resolved = resolver.resolve(assignment.variable)
        if not resolved:
            raise click.ClickException(f"Variable not found: {assignment.variable}")

        # Parse and encode value
        try:
            value = converter.parse_value(assignment.value, resolved.base_type)

            if resolved.bit_offset != NO_BITFIELD:
                # Bitfield: encode as single byte (will be merged on MCU side)
                data = bytes([int(value) & ((1 << resolved.bit_size) - 1)])
            else:
                data = converter.encode(value, resolved.base_type, resolved.size)

        except (ValueError, OverflowError) as e:
            raise click.ClickException(
                f"Invalid value for {assignment.variable}: {e}"
            )

        var_info = VarInfo(
            address=resolved.address,
            size=resolved.size,
            bit_offset=resolved.bit_offset if resolved.bit_offset != NO_BITFIELD else NO_BITFIELD,
            bit_size=resolved.bit_size if resolved.bit_size != NO_BITFIELD else NO_BITFIELD,
        )
        resolved_list.append((assignment.variable, resolved, var_info, data))

    # Open serial port
    serial_mgr = SerialManager()
    success, error = serial_mgr.open(state['port_name'], state['baud_rate'])
    if not success:
        raise click.ClickException(f"Failed to open serial port: {error}")

    try:
        protocol = Protocol(serial_mgr.get_port(), state.get('little_endian', True))

        var_infos = [vi for _, _, vi, _ in resolved_list]
        data_list = [d for _, _, _, d in resolved_list]

        # Determine execution mode
        if interval is None:
            # Single execution
            success, error = protocol.write_variables(var_infos, data_list)
            if not success:
                raise click.ClickException(f"Write failed: {error}")
            click.echo("OK")
        else:
            # Repeated execution
            if count is None:
                count = 0  # Infinite
            _do_repeated_set(protocol, var_infos, data_list, interval, count)

    finally:
        serial_mgr.close()


def _do_repeated_set(protocol: Protocol, var_infos: List[VarInfo],
                     data_list: List[bytes], interval_ms: int, count: int):
    """Execute repeated set operation (press ESC to stop)"""
    iteration = 0
    interval_sec = interval_ms / 1000.0
    stopped = False

    click.echo("Press ESC to stop...")

    while not stopped:
        # Check for ESC key before operation
        if _check_esc_pressed():
            stopped = True
            break

        iteration += 1
        if count > 0 and iteration > count:
            break

        success, error = protocol.write_variables(var_infos, data_list)
        if not success:
            click.echo(f"[{iteration}] Error: {error}", err=True)
        else:
            click.echo(f"[{iteration}] OK")

        # Wait for next interval (with ESC check)
        if count == 0 or iteration < count:
            if _sleep_with_esc_check(interval_sec):
                stopped = True
                break

    if stopped:
        click.echo("\nStopped by user (ESC)")


@cli.command()
def ports():
    """List available serial ports"""
    ports = SerialManager.list_ports()
    if not ports:
        click.echo("No serial ports found")
        return

    for port_name, description, hwid in ports:
        click.echo(f"{port_name}: {description}")


@cli.command()
def status():
    """Show current connection status"""
    state = StateManager.load_state()
    if not state:
        click.echo("Status: Not connected")
        return

    click.echo(f"Status: Connected")
    click.echo(f"  Port: {state.get('port_name')}")
    click.echo(f"  Baud: {state.get('baud_rate')}")
    click.echo(f"  Endian: {'little' if state.get('little_endian', True) else 'big'}")

    symbols = state.get('symbols_file')
    if symbols:
        click.echo(f"  Symbols: {symbols}")


# Maximum number of variables for chart
MAX_CHART_VARIABLES = 8


@cli.command()
@click.argument('variables')
@click.option('--interval', '-i', type=int, required=True,
              help='Sampling interval in milliseconds (required)')
@click.option('--count', '-c', type=int, default=0,
              help='Number of samples (0 for infinite, default: 0)')
def chart(variables: str, interval: int, count: int):
    """
    Display realtime chart of variable values

    VARIABLES: Comma-separated variable names (e.g., val1,val2,struct.member)

    Example: ramgs chart counter,speed -i 100
    """
    # Check connection state
    state = StateManager.load_state()
    if not state:
        raise click.ClickException("Not connected. Use 'ramgs open' first.")

    # Load symbols
    symbols_file = state.get('symbols_file') or _get_symbols_file()
    if not symbols_file or not os.path.exists(symbols_file):
        raise click.ClickException(
            f"Symbols file not found. Use 'ramgs create <elf_file>' first."
        )

    # Parse variables
    try:
        var_paths = parse_variables(variables)
    except ValueError as e:
        raise click.ClickException(str(e))

    if not var_paths:
        raise click.ClickException("No variables specified")

    if len(var_paths) > MAX_CHART_VARIABLES:
        raise click.ClickException(f"Error: Maximum {MAX_CHART_VARIABLES} variables allowed for chart")

    # Resolve variables
    resolver = SymbolResolver(symbols_file)
    try:
        resolved_vars = _resolve_variables(resolver, var_paths)
    except click.ClickException:
        raise

    # Get variable names as strings
    var_names = [str(vp) for vp in var_paths]

    # Open serial port
    serial_mgr = SerialManager()
    success, error = serial_mgr.open(state['port_name'], state['baud_rate'])
    if not success:
        raise click.ClickException(f"Failed to open serial port: {error}")

    try:
        protocol = Protocol(serial_mgr.get_port(), state.get('little_endian', True))
        converter = TypeConverter(state.get('little_endian', True))

        var_infos = [vi for _, _, vi in resolved_vars]

        # Run chart with data collection
        _do_chart_get(protocol, converter, resolved_vars, var_infos,
                      var_names, interval, count)

    finally:
        serial_mgr.close()


def _do_chart_get(protocol: Protocol, converter: TypeConverter,
                  resolved_vars: List[tuple], var_infos: List[VarInfo],
                  var_names: List[str], interval_ms: int, count: int):
    """Execute get operation with chart display"""
    # Import chart module
    from .chart import ChartDataQueue, ChartConfig, DataPoint

    # Create chart configuration
    config = ChartConfig(
        var_names=var_names,
        update_interval_ms=min(interval_ms, 100)  # Chart updates at least every 100ms
    )

    # Start chart window
    data_queue = ChartDataQueue()
    if not data_queue.start_chart(config):
        raise click.ClickException("Failed to start chart window")

    iteration = 0
    interval_sec = interval_ms / 1000.0
    stopped = False

    click.echo("Chart window opened. Press ESC to stop data collection...")

    try:
        while not stopped:
            # Check for ESC key before operation
            if _check_esc_pressed():
                stopped = True
                break

            iteration += 1
            if count > 0 and iteration > count:
                break

            success, data_list, error = protocol.read_variables(var_infos)
            if not success:
                click.echo(f"[{iteration}] Error: {error}", err=True)
            else:
                # Decode values
                values = []
                for (var_path, resolved, _), data in zip(resolved_vars, data_list):
                    if resolved.bit_offset != NO_BITFIELD:
                        value = converter.decode_bitfield(data[0], resolved.bit_size,
                                                           resolved.bit_offset)
                    else:
                        value = converter.decode(data, resolved.base_type)
                    values.append(float(value))

                # Send to chart
                data_point = DataPoint.create(var_names, values)
                data_queue.put_data(data_point)

            # Wait for next interval (with ESC check)
            if count == 0 or iteration < count:
                if _sleep_with_esc_check(interval_sec):
                    stopped = True
                    break

        # Signal collection stopped
        data_queue.stop_collection()

        if stopped:
            click.echo("\nData collection stopped. Chart window remains open for analysis.")
            click.echo("Close the chart window to continue...")
        else:
            click.echo(f"\nCollected {iteration} samples. Chart window remains open.")
            click.echo("Close the chart window to continue...")

        # Wait for chart window to be closed
        data_queue.wait_for_close()

    except KeyboardInterrupt:
        click.echo("\nInterrupted.")
    finally:
        data_queue.close()


# Maximum number of variables for image
MAX_IMAGE_VARIABLES = 8


@cli.command()
@click.argument('variables')
@click.option('--interval', '-i', type=int, required=True,
              help='Sampling interval in milliseconds (required)')
@click.option('--count', '-c', type=int, required=True,
              help='Number of samples (required, must be > 0)')
def image(variables: str, interval: int, count: int):
    """
    Generate static chart image from variable data

    VARIABLES: Comma-separated variable names (e.g., val1,val2,struct.member)

    Example: ramgs image -i 100 -c 50 counter,speed
    """
    # Validate count
    if count <= 0:
        raise click.ClickException(
            "Error: --count must be a positive integer (infinite not allowed for image)"
        )

    # Check connection state
    state = StateManager.load_state()
    if not state:
        raise click.ClickException("Not connected. Use 'ramgs open' first.")

    # Load symbols
    symbols_file = state.get('symbols_file') or _get_symbols_file()
    if not symbols_file or not os.path.exists(symbols_file):
        raise click.ClickException(
            f"Symbols file not found. Use 'ramgs create <elf_file>' first."
        )

    # Parse variables
    try:
        var_paths = parse_variables(variables)
    except ValueError as e:
        raise click.ClickException(str(e))

    if not var_paths:
        raise click.ClickException("No variables specified")

    if len(var_paths) > MAX_IMAGE_VARIABLES:
        raise click.ClickException(f"Error: Maximum {MAX_IMAGE_VARIABLES} variables allowed for image")

    # Resolve variables
    resolver = SymbolResolver(symbols_file)
    try:
        resolved_vars = _resolve_variables(resolver, var_paths)
    except click.ClickException:
        raise

    # Get variable names as strings
    var_names = [str(vp) for vp in var_paths]

    # Open serial port
    serial_mgr = SerialManager()
    success, error = serial_mgr.open(state['port_name'], state['baud_rate'])
    if not success:
        raise click.ClickException(f"Failed to open serial port: {error}")

    try:
        protocol = Protocol(serial_mgr.get_port(), state.get('little_endian', True))
        converter = TypeConverter(state.get('little_endian', True))

        var_infos = [vi for _, _, vi in resolved_vars]

        # Collect data and generate image
        filepath = _do_image_get(protocol, converter, resolved_vars, var_infos,
                                 var_names, interval, count)
        if filepath:
            click.echo(filepath)

    finally:
        serial_mgr.close()


def _do_image_get(protocol: Protocol, converter: TypeConverter,
                  resolved_vars: List[tuple], var_infos: List[VarInfo],
                  var_names: List[str], interval_ms: int, count: int) -> Optional[str]:
    """Collect data and generate static chart image"""
    import time as time_module
    from .image_generator import generate_image
    from .progress import ProgressBar

    # Data storage
    timestamps: List[float] = []
    data: dict = {name: [] for name in var_names}
    start_time: Optional[float] = None

    iteration = 0
    interval_sec = interval_ms / 1000.0
    stopped = False
    error_count = 0

    # Initialize progress bar
    progress = ProgressBar(total=count, prefix="Collecting...")
    progress.update(0)

    while not stopped and iteration < count:
        # Check for ESC key before operation
        if _check_esc_pressed():
            stopped = True
            break

        iteration += 1

        success, data_list, error = protocol.read_variables(var_infos)
        if not success:
            progress.clear()
            click.echo(f"[{iteration}] Error: {error}", err=True)
            error_count += 1
            progress.update(iteration)
        else:
            # Record timestamp
            current_time = time_module.time()
            if start_time is None:
                start_time = current_time
            timestamps.append(current_time - start_time)

            # Decode and store values
            for (var_path, resolved, _), raw_data in zip(resolved_vars, data_list):
                if resolved.bit_offset != NO_BITFIELD:
                    value = converter.decode_bitfield(raw_data[0], resolved.bit_size,
                                                       resolved.bit_offset)
                else:
                    value = converter.decode(raw_data, resolved.base_type)
                data[str(var_path)].append(float(value))

            # Update progress bar
            progress.update(iteration)

        # Wait for next interval (with ESC check)
        if iteration < count:
            if _sleep_with_esc_check(interval_sec):
                stopped = True
                break

    # Clear progress bar before final output
    progress.finish()

    # Generate image if we have data
    if not timestamps:
        if stopped:
            click.echo("Interrupted. No data collected, files not generated.")
        return None

    image_path, csv_path = generate_image(timestamps, data, var_names)

    if stopped:
        click.echo(f"Interrupted. Generated with {len(timestamps)} samples:")
        click.echo(f"  Image: {image_path}")
        click.echo(f"  CSV: {csv_path}")
    else:
        if error_count > 0:
            click.echo(f"Collected {len(timestamps)} samples ({error_count} errors):")
        else:
            click.echo(f"Collected {len(timestamps)} samples:")
        click.echo(f"  Image: {image_path}")
        click.echo(f"  CSV: {csv_path}")

    return image_path


def main():
    """Main entry point with multiprocessing freeze support"""
    # Required for Windows + PyInstaller multiprocessing support
    multiprocessing.freeze_support()
    cli()


@cli.command()
def gui():
    """Launch GUI application for visual MCU variable monitoring"""
    from .gui import run_gui
    run_gui()


@cli.command()
@click.argument('file', required=False)
def designer(file: Optional[str]):
    """Launch Panel Designer for creating display panel layouts

    FILE: Optional path to a .panel.json file to open

    Example: ramgs designer
             ramgs designer my_panel.panel.json
    """
    from .designer import run_designer
    run_designer(file)


@cli.command()
@click.argument('buffer_variable')
@click.option('--design', '-d', required=True, type=click.Path(exists=True),
              help='Path to panel design file (.panel.json)')
@click.option('--interval', '-i', type=int, default=None,
              help='Interval between renders in milliseconds')
@click.option('--count', '-c', type=int, default=None,
              help='Number of renders (default: 1)')
def display(buffer_variable: str, design: str, interval: Optional[int], count: Optional[int]):
    """
    Generate display panel image from buffer data

    BUFFER_VARIABLE: Buffer variable with range syntax (e.g., display_buff[0..10] or display_buff[0,16])

    Example: ramgs display display_buff[0..15] --design panel.panel.json
             ramgs display lcd_buffer[0,16] -d panel.json -i 500 -c 10
    """
    from .designer.display_renderer import DisplayRenderer
    from .designer.file_manager import FileManager

    # Check connection state
    state = StateManager.load_state()
    if not state:
        raise click.ClickException("Not connected. Use 'ramgs open' first.")

    # Load symbols
    symbols_file = state.get('symbols_file') or _get_symbols_file()
    if not symbols_file or not os.path.exists(symbols_file):
        raise click.ClickException(
            "Symbols file not found. Use 'ramgs create <elf_file>' first."
        )

    # Load design file
    renderer, error = DisplayRenderer.from_file(design)
    if error:
        raise click.ClickException(f"Failed to load design file: {error}")

    # Parse buffer variable and range
    buffer_data, var_infos, resolved_vars = _parse_buffer_variable(
        buffer_variable, symbols_file, state
    )

    # Open serial port
    serial_mgr = SerialManager()
    success, error = serial_mgr.open(state['port_name'], state['baud_rate'])
    if not success:
        raise click.ClickException(f"Failed to open serial port: {error}")

    try:
        protocol = Protocol(serial_mgr.get_port(), state.get('little_endian', True))

        # Determine execution mode
        if interval is None:
            # Single execution
            buffer_data = _read_buffer_data(protocol, var_infos, resolved_vars, state)
            image_path, error = renderer.render(buffer_data)
            if error:
                raise click.ClickException(f"Render failed: {error}")
            click.echo(image_path)
        else:
            # Repeated execution
            if count is None:
                count = 0  # Infinite
            _do_repeated_display(protocol, renderer, var_infos, resolved_vars,
                                 state, interval, count)

    finally:
        serial_mgr.close()


def _parse_buffer_variable(buffer_variable: str, symbols_file: str, state: dict):
    """Parse buffer variable with range syntax and resolve to VarInfo list"""
    import re

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
        raise click.ClickException(
            f"Invalid buffer variable syntax: {buffer_variable}\n"
            "Use var[start..end] or var[start,count] format."
        )

    # Resolve base variable
    resolver = SymbolResolver(symbols_file)
    var_paths = parse_variables(var_name)
    if not var_paths:
        raise click.ClickException(f"Invalid variable: {var_name}")

    resolved = resolver.resolve(var_paths[0])
    if not resolved:
        raise click.ClickException(f"Variable not found: {var_name}")

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

    return bytes(byte_count), var_infos, resolved_vars


def _read_buffer_data(protocol: Protocol, var_infos: list, resolved_vars: list, state: dict) -> bytes:
    """Read buffer data from MCU"""
    success, data_list, error = protocol.read_variables(var_infos)
    if not success:
        raise click.ClickException(f"Read failed: {error}")

    # Combine bytes
    return bytes(d[0] for d in data_list)


def _do_repeated_display(protocol: Protocol, renderer, var_infos: list,
                         resolved_vars: list, state: dict,
                         interval_ms: int, count: int):
    """Execute repeated display rendering"""
    iteration = 0
    interval_sec = interval_ms / 1000.0
    stopped = False

    click.echo("Press ESC to stop...")

    while not stopped:
        if _check_esc_pressed():
            stopped = True
            break

        iteration += 1
        if count > 0 and iteration > count:
            break

        try:
            buffer_data = _read_buffer_data(protocol, var_infos, resolved_vars, state)
            image_path, error = renderer.render(buffer_data)
            if error:
                click.echo(f"[{iteration}] Error: {error}", err=True)
            else:
                click.echo(f"[{iteration}] {image_path}")
        except Exception as e:
            click.echo(f"[{iteration}] Error: {e}", err=True)

        if count == 0 or iteration < count:
            if _sleep_with_esc_check(interval_sec):
                stopped = True
                break

    if stopped:
        click.echo(f"\nStopped by user (ESC). Generated {iteration - 1} images.")


@cli.command()
@click.option('--device', '-d', type=int, default=0,
              help='Camera device index (default: 0)')
@click.option('--list', '-l', 'list_devices', is_flag=True, default=False,
              help='List available camera devices')
@click.option('--output', '-o', type=str, default=None,
              help='Custom output filename (single capture only)')
@click.option('--interval', '-i', type=int, default=None,
              help='Interval between captures in milliseconds')
@click.option('--count', '-c', type=int, default=None,
              help='Number of captures (0 for infinite, default: 1)')
def snapshot(device: int, list_devices: bool, output: Optional[str],
             interval: Optional[int], count: Optional[int]):
    """
    Capture image from camera

    Examples:
        ramgs snapshot
        ramgs snapshot -d 1
        ramgs snapshot --list
        ramgs snapshot -i 1000 -c 5
        ramgs snapshot -o my_photo.png
    """
    from .camera import check_opencv, list_cameras, capture_snapshot, CameraCapture

    # Check OpenCV availability
    if not check_opencv():
        raise click.ClickException(
            "OpenCV not available. Install with: pip install opencv-python"
        )

    # List devices mode
    if list_devices:
        cameras = list_cameras()
        if not cameras:
            click.echo("No camera devices found")
            return

        click.echo("Available cameras:")
        for idx, name in cameras:
            click.echo(f"  [{idx}] {name}")
        return

    # Determine execution mode
    if interval is None:
        # Single capture
        success, image_path, error = capture_snapshot(device, output)
        if not success:
            raise click.ClickException(error)
        click.echo(image_path)
    else:
        # Repeated capture
        if count is None:
            count = 0  # Infinite

        try:
            with CameraCapture(device) as cam:
                _do_repeated_snapshot(cam, interval, count)
        except RuntimeError as e:
            raise click.ClickException(str(e))


def _do_repeated_snapshot(cam, interval_ms: int, count: int):
    """Execute repeated snapshot capture (press ESC to stop)"""
    iteration = 0
    interval_sec = interval_ms / 1000.0
    stopped = False

    click.echo("Press ESC to stop...")

    while not stopped:
        # Check for ESC key before operation
        if _check_esc_pressed():
            stopped = True
            break

        iteration += 1
        if count > 0 and iteration > count:
            break

        success, image_path, error = cam.capture()
        if not success:
            click.echo(f"[{iteration}] Error: {error}", err=True)
        else:
            click.echo(f"[{iteration}] {image_path}")

        # Wait for next interval (with ESC check)
        if count == 0 or iteration < count:
            if _sleep_with_esc_check(interval_sec):
                stopped = True
                break

    if stopped:
        click.echo("\nStopped by user (ESC)")


@cli.command()
@click.argument('image', type=click.Path(exists=True))
@click.option('--design', '-d', required=True, type=click.Path(exists=True),
              help='Path to panel design file (.panel.json)')
@click.option('--json', 'output_json', is_flag=True, default=False,
              help='Output in JSON format (default: text)')
@click.option('--threshold', '-t', type=float, default=0.4,
              help='Brightness threshold for on/off detection (default: 0.4)')
def recognize(image: str, design: str, output_json: bool, threshold: float):
    """
    Recognize display panel elements from an image

    IMAGE: Path to panel photograph

    Example: ramgs recognize photo.jpg --design panel.panel.json
             ramgs recognize photo.jpg -d panel.json --json
    """
    from .recognizer import PanelRecognizer, check_opencv

    # Check OpenCV availability
    if not check_opencv():
        raise click.ClickException(
            "OpenCV not available. Install with: pip install opencv-python"
        )

    # Load design file and create recognizer
    recognizer, error = PanelRecognizer.from_file(design, threshold)
    if error:
        raise click.ClickException(f"Failed to load design file: {error}")

    # Perform recognition
    result = recognizer.recognize(image)

    # Output result
    if output_json:
        click.echo(result.to_json())
    else:
        click.echo(result.format_cli_output())


if __name__ == '__main__':
    main()
