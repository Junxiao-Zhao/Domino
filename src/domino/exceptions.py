class DominoError(Exception):
    """Base exception for domino."""


class DominoConfigError(DominoError):
    """Raised when workflow configuration is invalid."""


class DominoLoadError(DominoError):
    """Raised when a configured callable cannot be loaded."""


class DominoExecutionError(DominoError):
    """Raised when a workflow step fails during execution."""
