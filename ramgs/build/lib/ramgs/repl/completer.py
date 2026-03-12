"""
Completer - Intelligent auto-completion for REPL

Provides context-aware completion for:
- Slash commands (/quit, /ports, /status, etc.)
- Command arguments (port names, baud rates, etc.)
- Variable names (from symbols.json)
- Struct member names (nested completion)
"""

from typing import Iterable, List, Optional, TYPE_CHECKING

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document

if TYPE_CHECKING:
    from .session import ReplSession


# Command definitions with descriptions
COMMANDS = {
    '/quit': 'Exit interactive mode',
    '/exit': 'Exit interactive mode (alias)',
    '/help': 'Show help message',
    '/ports': 'List available serial ports',
    '/status': 'Show connection status',
    '/open': 'Open serial port: /open --name COM1 --baud 9600',
    '/close': 'Close serial port',
    '/create': 'Create symbols from ELF: /create firmware.elf',
    '/load': 'Load symbols file: /load symbols.json',
    '/get': 'Get variable value: /get var1,var2',
    '/set': 'Set variable value: /set var=123',
    '/chart': 'Realtime chart: /chart -i 100 var1,var2',
    '/image': 'Static chart image: /image -i 100 -c 50 var1,var2',
    '/display': 'Display panel image: /display buf[0..15] -d panel.json',
    '/designer': 'Launch Panel Designer GUI',
    '/snapshot': 'Capture camera image: /snapshot [-d 0] [-i 1000 -c 5]',
    '/recognize': 'Recognize panel elements: /recognize photo.jpg -d panel.json',
}

# Common baud rates
BAUD_RATES = ['2400','4800','9600', '19200', '38400', '57600', '115200', '230400']


class RamgsCompleter(Completer):
    """
    Context-aware completer for RAMViewer REPL.

    Completion contexts:
    1. Empty input or '/' -> Show slash commands
    2. '/open' args -> --name (port list), --baud (rates), --endian
    3. '/get', '/set' or shortcut -> Variable name completion
    4. After '.' -> Struct member completion
    5. After '[' -> Array index hint
    """

    def __init__(self, session: 'ReplSession'):
        self.session = session

    def get_completions(self, document: Document,
                        complete_event) -> Iterable[Completion]:
        text = document.text_before_cursor.lstrip()

        # Empty input -> show all commands
        if not text:
            yield from self._complete_commands(text)
            return

        # Parse command context
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ''

        # Check if we're still typing a command (no space after command yet)
        if text.startswith('/') and ' ' not in text:
            yield from self._complete_commands(text)
            return

        # Command-specific completions
        if cmd == '/open':
            yield from self._complete_open_args(text, args)
        elif cmd == '/load':
            yield from self._complete_file_path(args)
        elif cmd == '/create':
            yield from self._complete_file_path(args)
        elif cmd in ('/get', '/set'):
            # Get variable part after command
            yield from self._complete_variable(args)
        elif cmd == '/chart':
            # Chart command: needs -i option and variables
            yield from self._complete_chart_args(args)
        elif cmd == '/image':
            # Image command: needs -i and -c options and variables
            yield from self._complete_image_args(args)
        elif cmd == '/display':
            # Display command: needs -d option and buffer variable
            yield from self._complete_display_args(args)
        elif cmd == '/designer':
            # Designer command: optional file path
            yield from self._complete_file_path(args)
        elif cmd == '/snapshot':
            # Snapshot command: -d, -l, -o, -i, -c options
            yield from self._complete_snapshot_args(args)
        elif cmd == '/recognize':
            # Recognize command: image path, -d, --json, -t options
            yield from self._complete_recognize_args(args)
        elif not text.startswith('/'):
            # Shortcut syntax: assume it's a variable reference
            # Could be 'var', 'var.member', or 'var=value'
            yield from self._complete_shortcut(text)

    def _complete_commands(self, text: str) -> Iterable[Completion]:
        """Complete slash commands"""
        # Remove leading slash for matching
        prefix = text[1:] if text.startswith('/') else text

        for cmd, desc in COMMANDS.items():
            cmd_name = cmd[1:]  # Remove leading /
            if cmd_name.startswith(prefix.lower()):
                yield Completion(
                    cmd,
                    start_position=-len(text),
                    display=cmd,
                    display_meta=desc
                )

    def _complete_open_args(self, full_text: str, args: str) -> Iterable[Completion]:
        """Complete /open command arguments"""
        # Determine what we're completing
        args_lower = args.lower()

        # Check if we're after --name
        if '--name' in args_lower:
            # Check if we need port name or next option
            name_idx = args_lower.rfind('--name')
            after_name = args[name_idx + 6:].strip()

            if not after_name or not after_name.startswith('-'):
                # Need port name
                yield from self._complete_port_names(after_name)
                return

        # Check if we're after --baud
        if '--baud' in args_lower:
            baud_idx = args_lower.rfind('--baud')
            after_baud = args[baud_idx + 6:].strip()

            if not after_baud or not after_baud.startswith('-'):
                # Need baud rate
                for rate in BAUD_RATES:
                    if rate.startswith(after_baud):
                        yield Completion(
                            rate,
                            start_position=-len(after_baud) if after_baud else 0
                        )
                return

        # Check if we're after --endian
        if '--endian' in args_lower:
            endian_idx = args_lower.rfind('--endian')
            after_endian = args[endian_idx + 8:].strip()

            if not after_endian or not after_endian.startswith('-'):
                for endian in ['little', 'big']:
                    if endian.startswith(after_endian.lower()):
                        yield Completion(
                            endian,
                            start_position=-len(after_endian) if after_endian else 0,
                            display_meta='default' if endian == 'little' else ''
                        )
                return

        # Suggest options
        options = []
        if '--name' not in args_lower:
            options.append(('--name', 'Serial port name (required)'))
        if '--baud' not in args_lower:
            options.append(('--baud', 'Baud rate (default: 9600)'))
        if '--endian' not in args_lower:
            options.append(('--endian', 'Byte order (default: little)'))

        # Get the last partial word
        words = args.split()
        last_word = words[-1] if words and not args.endswith(' ') else ''

        for opt, desc in options:
            if opt.startswith(last_word) or not last_word:
                yield Completion(
                    opt,
                    start_position=-len(last_word),
                    display_meta=desc
                )

    def _complete_port_names(self, prefix: str) -> Iterable[Completion]:
        """Complete serial port names"""
        from ..serial_manager import SerialManager

        ports = SerialManager.list_ports()
        for port_name, description, _ in ports:
            if port_name.lower().startswith(prefix.lower()):
                yield Completion(
                    port_name,
                    start_position=-len(prefix) if prefix else 0,
                    display=port_name,
                    display_meta=description
                )

    def _complete_file_path(self, prefix: str) -> Iterable[Completion]:
        """Complete file paths (basic implementation)"""
        import os
        import glob

        if not prefix:
            prefix = '.'

        # Handle directory vs file
        if os.path.isdir(prefix):
            search_dir = prefix
            file_prefix = ''
        else:
            search_dir = os.path.dirname(prefix) or '.'
            file_prefix = os.path.basename(prefix)

        try:
            pattern = os.path.join(search_dir, file_prefix + '*')
            for path in glob.glob(pattern):
                name = os.path.basename(path)
                if name.startswith(file_prefix):
                    display_meta = 'dir' if os.path.isdir(path) else ''
                    yield Completion(
                        path,
                        start_position=-len(prefix),
                        display=name,
                        display_meta=display_meta
                    )
        except Exception:
            pass

    def _complete_variable(self, var_text: str) -> Iterable[Completion]:
        """Complete variable names and struct members"""
        if not self.session.has_symbols:
            return

        # Strip -i/--interval and -c/--count options first
        var_text = self._strip_interval_options(var_text)

        # Handle comma-separated variables (complete the last one)
        if ',' in var_text:
            last_comma = var_text.rfind(',')
            prefix_before_comma = var_text[:last_comma + 1]
            current_var = var_text[last_comma + 1:].lstrip()
        else:
            prefix_before_comma = ''
            current_var = var_text

        # Handle assignment syntax (var=value)
        if '=' in current_var:
            # After '=' we're entering value, no completion
            return

        # Check for member access
        if '.' in current_var:
            yield from self._complete_member(current_var, prefix_before_comma)
        elif '[' in current_var and not current_var.endswith(']'):
            # Inside array index
            yield from self._complete_array_index(current_var, prefix_before_comma)
        else:
            # Base variable name
            yield from self._complete_variable_name(current_var, prefix_before_comma)

    def _strip_interval_options(self, text: str) -> str:
        """Strip -i/--interval and -c/--count options from text"""
        import re
        # Remove -i <num> or --interval <num>
        text = re.sub(r'(?:-i|--interval)\s+\d+\s*', '', text)
        # Remove -c <num> or --count <num>
        text = re.sub(r'(?:-c|--count)\s+\d+\s*', '', text)
        return text.strip()

    def _complete_variable_name(self, prefix: str, prepend: str) -> Iterable[Completion]:
        """Complete base variable names"""
        names = self.session.get_all_variable_names()

        for name in names:
            if name.lower().startswith(prefix.lower()):
                full_completion = prepend + name
                yield Completion(
                    name,
                    start_position=-len(prefix),
                )

    def _complete_member(self, var_text: str, prepend: str) -> Iterable[Completion]:
        """Complete struct members"""
        # Split at the last dot
        last_dot = var_text.rfind('.')
        base_path = var_text[:last_dot]
        member_prefix = var_text[last_dot + 1:]

        # Get members at the base path
        members = self.session.get_members_at_path(base_path)

        for member in members:
            if member.lower().startswith(member_prefix.lower()):
                yield Completion(
                    member,
                    start_position=-len(member_prefix),
                    display_meta='member'
                )

    def _complete_array_index(self, var_text: str, prepend: str) -> Iterable[Completion]:
        """Provide hints for array index"""
        # Extract the path before '['
        bracket_idx = var_text.rfind('[')
        base_path = var_text[:bracket_idx]
        index_prefix = var_text[bracket_idx + 1:]

        # Get array dimensions
        if self.session.symbol_resolver:
            dims = self.session.symbol_resolver.get_array_dimensions(base_path)
            if dims and len(dims) > 0:
                max_idx = dims[0] - 1
                # Suggest completing the bracket
                yield Completion(
                    f'{index_prefix}]',
                    start_position=-len(index_prefix),
                    display=f'0..{max_idx}',
                    display_meta=f'array[{dims[0]}]'
                )

    def _complete_shortcut(self, text: str) -> Iterable[Completion]:
        """Complete shortcut syntax (variable without command)"""
        # Handle assignment: var=value
        if '=' in text:
            var_part = text.split('=')[0]
            # No completion for value part
            return

        # Handle variable path
        yield from self._complete_variable(text)

    def _complete_chart_args(self, args: str) -> Iterable[Completion]:
        """Complete /chart command arguments (-i, -c, and variables)"""
        args_lower = args.lower()

        # Get the last word being typed
        words = args.split()
        last_word = words[-1] if words and not args.endswith(' ') else ''

        # Check if we just typed -i or -c and need a number
        if len(words) >= 1:
            prev_word = words[-1] if args.endswith(' ') else (words[-2] if len(words) >= 2 else '')
            if prev_word in ('-i', '--interval'):
                # Suggest common intervals
                for interval in ['50', '100', '200', '500', '1000']:
                    if interval.startswith(last_word) or args.endswith(' '):
                        yield Completion(
                            interval,
                            start_position=-len(last_word) if last_word else 0,
                            display_meta='ms'
                        )
                return
            elif prev_word in ('-c', '--count'):
                # Suggest common counts
                for count in ['0', '100', '200', '500', '1000']:
                    if count.startswith(last_word) or args.endswith(' '):
                        yield Completion(
                            count,
                            start_position=-len(last_word) if last_word else 0,
                            display_meta='0=infinite'
                        )
                return

        # Suggest options if not present
        options = []
        if '-i' not in args_lower and '--interval' not in args_lower:
            options.append(('-i', 'Sampling interval in ms (required)'))
        if '-c' not in args_lower and '--count' not in args_lower:
            options.append(('-c', 'Sample count (0=infinite)'))

        # If last word starts with '-', complete options
        if last_word.startswith('-'):
            for opt, desc in options:
                if opt.startswith(last_word):
                    yield Completion(
                        opt,
                        start_position=-len(last_word),
                        display_meta=desc
                    )
            return

        # Check if -i is already provided, then we can suggest variables
        if '-i' in args_lower or '--interval' in args_lower:
            # Strip options and complete variables
            yield from self._complete_variable(args)
        else:
            # Suggest -i option first (required)
            for opt, desc in options:
                yield Completion(
                    opt,
                    start_position=0,
                    display_meta=desc
                )

    def _complete_image_args(self, args: str) -> Iterable[Completion]:
        """Complete /image command arguments (-i, -c required, and variables)"""
        args_lower = args.lower()

        # Get the last word being typed
        words = args.split()
        last_word = words[-1] if words and not args.endswith(' ') else ''

        # Check if we just typed -i or -c and need a number
        if len(words) >= 1:
            prev_word = words[-1] if args.endswith(' ') else (words[-2] if len(words) >= 2 else '')
            if prev_word in ('-i', '--interval'):
                # Suggest common intervals
                for interval in ['50', '100', '200', '500', '1000']:
                    if interval.startswith(last_word) or args.endswith(' '):
                        yield Completion(
                            interval,
                            start_position=-len(last_word) if last_word else 0,
                            display_meta='ms'
                        )
                return
            elif prev_word in ('-c', '--count'):
                # Suggest common counts (no 0 for image, must be > 0)
                for count in ['10', '50', '100', '200', '500']:
                    if count.startswith(last_word) or args.endswith(' '):
                        yield Completion(
                            count,
                            start_position=-len(last_word) if last_word else 0,
                            display_meta='samples'
                        )
                return

        # Suggest options if not present
        options = []
        if '-i' not in args_lower and '--interval' not in args_lower:
            options.append(('-i', 'Sampling interval in ms (required)'))
        if '-c' not in args_lower and '--count' not in args_lower:
            options.append(('-c', 'Sample count (required, >0)'))

        # If last word starts with '-', complete options
        if last_word.startswith('-'):
            for opt, desc in options:
                if opt.startswith(last_word):
                    yield Completion(
                        opt,
                        start_position=-len(last_word),
                        display_meta=desc
                    )
            return

        # Check if both -i and -c are provided, then suggest variables
        has_interval = '-i' in args_lower or '--interval' in args_lower
        has_count = '-c' in args_lower or '--count' in args_lower

        if has_interval and has_count:
            # Both required options present, complete variables
            yield from self._complete_variable(args)
        else:
            # Suggest missing required options
            for opt, desc in options:
                yield Completion(
                    opt,
                    start_position=0,
                    display_meta=desc
                )

    def _complete_display_args(self, args: str) -> Iterable[Completion]:
        """Complete /display command arguments (-d required, optional -i -c, and buffer variable)"""
        args_lower = args.lower()

        # Get the last word being typed
        words = args.split()
        last_word = words[-1] if words and not args.endswith(' ') else ''

        # Check if we just typed -d and need a file path
        if len(words) >= 1:
            prev_word = words[-1] if args.endswith(' ') else (words[-2] if len(words) >= 2 else '')
            if prev_word in ('-d', '--design'):
                # Need design file path
                yield from self._complete_file_path(last_word)
                return
            elif prev_word in ('-i', '--interval'):
                # Suggest common intervals
                for interval in ['100', '200', '500', '1000']:
                    if interval.startswith(last_word) or args.endswith(' '):
                        yield Completion(
                            interval,
                            start_position=-len(last_word) if last_word else 0,
                            display_meta='ms'
                        )
                return
            elif prev_word in ('-c', '--count'):
                # Suggest common counts
                for count in ['0', '5', '10', '20', '50']:
                    if count.startswith(last_word) or args.endswith(' '):
                        yield Completion(
                            count,
                            start_position=-len(last_word) if last_word else 0,
                            display_meta='0=infinite'
                        )
                return

        # Suggest options if not present
        options = []
        if '-d' not in args_lower and '--design' not in args_lower:
            options.append(('-d', 'Panel design file (required)'))
        if '-i' not in args_lower and '--interval' not in args_lower:
            options.append(('-i', 'Repeat interval in ms (optional)'))
        if '-c' not in args_lower and '--count' not in args_lower:
            options.append(('-c', 'Repeat count (optional)'))

        # If last word starts with '-', complete options
        if last_word.startswith('-'):
            for opt, desc in options:
                if opt.startswith(last_word):
                    yield Completion(
                        opt,
                        start_position=-len(last_word),
                        display_meta=desc
                    )
            return

        # Check if -d is provided, suggest variables
        has_design = '-d' in args_lower or '--design' in args_lower

        if has_design:
            # Design file provided, complete buffer variable
            yield from self._complete_variable(args)
        else:
            # Suggest -d option first (required)
            for opt, desc in options:
                if opt == '-d':
                    yield Completion(
                        opt,
                        start_position=0,
                        display_meta=desc
                    )

    def _complete_snapshot_args(self, args: str) -> Iterable[Completion]:
        """Complete /snapshot command arguments (-d, -l, -o, -i, -c options)"""
        args_lower = args.lower()

        # Get the last word being typed
        words = args.split()
        last_word = words[-1] if words and not args.endswith(' ') else ''

        # Check if we just typed an option and need a value
        if len(words) >= 1:
            prev_word = words[-1] if args.endswith(' ') else (words[-2] if len(words) >= 2 else '')
            if prev_word in ('-d', '--device'):
                # Suggest device indices
                for idx in ['0', '1', '2']:
                    if idx.startswith(last_word) or args.endswith(' '):
                        yield Completion(
                            idx,
                            start_position=-len(last_word) if last_word else 0,
                            display_meta='default' if idx == '0' else ''
                        )
                return
            elif prev_word in ('-i', '--interval'):
                # Suggest common intervals
                for interval in ['500', '1000', '2000', '5000']:
                    if interval.startswith(last_word) or args.endswith(' '):
                        yield Completion(
                            interval,
                            start_position=-len(last_word) if last_word else 0,
                            display_meta='ms'
                        )
                return
            elif prev_word in ('-c', '--count'):
                # Suggest common counts
                for count in ['0', '5', '10', '20', '50']:
                    if count.startswith(last_word) or args.endswith(' '):
                        yield Completion(
                            count,
                            start_position=-len(last_word) if last_word else 0,
                            display_meta='0=infinite'
                        )
                return
            elif prev_word in ('-o', '--output'):
                # Suggest file path
                yield from self._complete_file_path(last_word)
                return

        # Suggest options if not present
        options = []
        if '-d' not in args_lower and '--device' not in args_lower:
            options.append(('-d', 'Camera device index (default: 0)'))
        if '-l' not in args_lower and '--list' not in args_lower:
            options.append(('-l', 'List available cameras'))
        if '-o' not in args_lower and '--output' not in args_lower:
            options.append(('-o', 'Custom output filename'))
        if '-i' not in args_lower and '--interval' not in args_lower:
            options.append(('-i', 'Capture interval in ms'))
        if '-c' not in args_lower and '--count' not in args_lower:
            options.append(('-c', 'Number of captures (0=infinite)'))

        # If last word starts with '-', complete options
        if last_word.startswith('-'):
            for opt, desc in options:
                if opt.startswith(last_word):
                    yield Completion(
                        opt,
                        start_position=-len(last_word),
                        display_meta=desc
                    )
            return

        # Suggest all available options
        for opt, desc in options:
            yield Completion(
                opt,
                start_position=0,
                display_meta=desc
            )

    def _complete_recognize_args(self, args: str) -> Iterable[Completion]:
        """Complete /recognize command arguments (image path, -d, --json, -t options)"""
        args_lower = args.lower()

        # Get the last word being typed
        words = args.split()
        last_word = words[-1] if words and not args.endswith(' ') else ''

        # Check if we just typed an option and need a value
        if len(words) >= 1:
            prev_word = words[-1] if args.endswith(' ') else (words[-2] if len(words) >= 2 else '')
            if prev_word in ('-d', '--design'):
                # Need design file path
                yield from self._complete_file_path(last_word)
                return
            elif prev_word in ('-t', '--threshold'):
                # Suggest common threshold values
                for threshold in ['0.3', '0.4', '0.5', '0.6']:
                    if threshold.startswith(last_word) or args.endswith(' '):
                        yield Completion(
                            threshold,
                            start_position=-len(last_word) if last_word else 0,
                            display_meta='default' if threshold == '0.4' else ''
                        )
                return

        # Suggest options if not present
        options = []
        if '-d' not in args_lower and '--design' not in args_lower:
            options.append(('-d', 'Panel design file (required)'))
        if '--json' not in args_lower:
            options.append(('--json', 'Output in JSON format'))
        if '-t' not in args_lower and '--threshold' not in args_lower:
            options.append(('-t', 'Brightness threshold (default: 0.4)'))

        # If last word starts with '-', complete options
        if last_word.startswith('-'):
            for opt, desc in options:
                if opt.startswith(last_word):
                    yield Completion(
                        opt,
                        start_position=-len(last_word),
                        display_meta=desc
                    )
            return

        # Check if -d is provided
        has_design = '-d' in args_lower or '--design' in args_lower

        # If no image path yet (first argument), suggest file paths
        # Count non-option arguments
        non_option_args = []
        skip_next = False
        for w in words:
            if skip_next:
                skip_next = False
                continue
            if w in ('-d', '--design', '-t', '--threshold'):
                skip_next = True
                continue
            if w.startswith('-'):
                continue
            non_option_args.append(w)

        if len(non_option_args) == 0 or (len(non_option_args) == 1 and not args.endswith(' ')):
            # Need image file path
            yield from self._complete_file_path(last_word if not last_word.startswith('-') else '')

        # Suggest options
        for opt, desc in options:
            yield Completion(
                opt,
                start_position=0,
                display_meta=desc
            )
