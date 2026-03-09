"""
Progress Bar - Simple text-based progress bar for terminal display

Compatible with Windows terminal, updates in-place using carriage return.
"""

import sys


class ProgressBar:
    """Simple text-based progress bar that updates in-place."""

    def __init__(self, total: int, width: int = 20, prefix: str = "Collecting..."):
        """
        Initialize progress bar.

        Args:
            total: Total number of items
            width: Width of the progress bar in characters
            prefix: Text to display before the progress bar
        """
        self.total = total
        self.width = width
        self.prefix = prefix
        self.current = 0

    def update(self, current: int) -> None:
        """
        Update progress bar display.

        Args:
            current: Current progress (1 to total)
        """
        self.current = current
        percentage = int(100 * current / self.total) if self.total > 0 else 0
        filled = int(self.width * current / self.total) if self.total > 0 else 0

        bar = '=' * filled
        if filled < self.width:
            bar += '>'
            bar += ' ' * (self.width - filled - 1)
        else:
            bar = '=' * self.width

        line = f"\r{self.prefix} [{current}/{self.total}] [{bar}] {percentage}%"
        sys.stdout.write(line)
        sys.stdout.flush()

    def clear(self) -> None:
        """Clear the progress bar line."""
        sys.stdout.write('\r' + ' ' * 80 + '\r')
        sys.stdout.flush()

    def finish(self) -> None:
        """Clear progress bar and move to new line."""
        self.clear()
