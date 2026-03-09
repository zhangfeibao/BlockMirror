"""
REPL - Read-Eval-Print Loop for RAMViewer

Main interactive mode implementation.
"""

from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.key_binding import KeyBindings

from .session import ReplSession
from .completer import RamgsCompleter
from .commands import CommandHandler


# REPL styling
STYLE = Style.from_dict({
    'prompt': '#00aa00 bold',
    'prompt.port': '#00aaaa',
})


def create_key_bindings():
    """Create custom key bindings for REPL"""
    bindings = KeyBindings()

    @bindings.add(' ')
    def _(event):
        """Insert space and trigger completion"""
        buf = event.app.current_buffer
        buf.insert_text(' ')
        # Trigger completion after space
        buf.start_completion(select_first=False)

    return bindings


class Repl:
    """
    RAMViewer interactive REPL.

    Provides an interactive command-line interface with:
    - Command history (persisted across sessions)
    - Auto-completion for commands and variables
    - Auto-suggest from history
    - Auto-restore of previous connection state
    """

    # History file location
    HISTORY_FILE = Path.home() / ".ramgs" / "history"

    def __init__(self):
        self.session = ReplSession()
        self.completer = RamgsCompleter(self.session)
        self.handler = CommandHandler(self.session)

        # Ensure history directory exists
        self.HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

        self.prompt_session = PromptSession(
            history=FileHistory(str(self.HISTORY_FILE)),
            auto_suggest=AutoSuggestFromHistory(),
            completer=self.completer,
            style=STYLE,
            complete_while_typing=True,
            complete_in_thread=True,
            complete_style=CompleteStyle.MULTI_COLUMN,
            key_bindings=create_key_bindings(),
        )

    def run(self):
        """Run the REPL main loop"""
        self._print_welcome()
        self._restore_previous_state()

        while True:
            try:
                # Build prompt based on connection state
                prompt = self._build_prompt()

                # Get user input
                line = self.prompt_session.prompt(prompt)

                # Execute command
                should_exit, output = self.handler.parse_and_execute(line)

                if output:
                    print(output)

                if should_exit:
                    break

            except KeyboardInterrupt:
                # Ctrl+C - show hint
                print("\n(Use /quit to exit)")
                continue

            except EOFError:
                # Ctrl+D - exit with state preserved
                print("\nGoodbye! (state preserved for next session)")
                break

            except Exception as e:
                print(f"Error: {e}")

        # Cleanup on exit - preserve state for next session
        self.session.close_port_preserve_state()

    def _print_welcome(self):
        """Print welcome message"""
        print("RAMViewer Interactive Mode")
        print("Type /help for available commands, /quit to exit")
        print()

    def _build_prompt(self) -> str:
        """Build prompt string based on current state"""
        if self.session.is_connected:
            return f"[{self.session.port_name}] > "
        else:
            return "ramgs> "

    def _restore_previous_state(self):
        """Attempt to restore previous session state"""
        success, message = self.session.restore_from_state()
        if success and message:
            print(message)
            print()
