"""Abstract progress reporter interface.

Provides a base class for progress feedback during long-running operations
(scanning, metadata fetching, renaming). Implementations exist for CLI (Rich)
and GUI (GTK4).
"""

from abc import ABC, abstractmethod


class ProgressReporter(ABC):
    """Abstract progress reporter for long-running operations."""

    @abstractmethod
    def on_start(self, total: int, message: str = ""):
        """Called when an operation starts.

        Args:
            total: Total number of items to process (0 if unknown).
            message: Optional description of the operation.
        """

    @abstractmethod
    def on_progress(self, current: int, message: str = ""):
        """Called after each item is processed.

        Args:
            current: Current item index (1-based).
            message: Optional status message for the current item.
        """

    @abstractmethod
    def on_complete(self, message: str = ""):
        """Called when the operation finishes successfully.

        Args:
            message: Optional completion summary.
        """

    @abstractmethod
    def on_error(self, message: str):
        """Called when an error occurs during the operation.

        Args:
            message: Error description.
        """


class NullProgressReporter(ProgressReporter):
    """No-op reporter for silent operation (default when none is injected)."""

    def on_start(self, total: int, message: str = ""):
        pass

    def on_progress(self, current: int, message: str = ""):
        pass

    def on_complete(self, message: str = ""):
        pass

    def on_error(self, message: str):
        pass
