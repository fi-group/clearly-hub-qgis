"""Central error types for managers."""


class ClearlyHubError(Exception):
    """Base exception for ClearlyHub backend errors."""
    pass


class APIError(ClearlyHubError):
    """Raised when API call fails (network, HTTP error, etc.)."""
    pass


class AuthenticationError(ClearlyHubError):
    """Raised when authentication fails or token is invalid."""
    pass


class DataValidationError(ClearlyHubError):
    """Raised when data validation or normalization fails."""
    pass


class LayerLoadingError(ClearlyHubError):
    """Raised when layer loading fails."""
    pass
