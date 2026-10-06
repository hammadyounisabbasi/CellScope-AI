class CellScopeError(Exception):
    """Base class for errors safe to expose to API clients."""


class UploadValidationError(CellScopeError):
    """Raised when an upload is missing, malformed, or unsupported."""


class AnalysisError(CellScopeError):
    """Raised when valid input cannot be analyzed reliably."""

