"""Base manager with common caching, error handling, and logging."""

from functools import wraps
import time
from .errors import ClearlyHubError


class BaseManager:
    """Common manager interface with built-in caching and error handling.

    Subclasses inherit automatic caching for any method decorated with @cached.
    """

    # Default cache TTL in seconds (300 = 5 minutes)
    CACHE_TTL = 300

    def __init__(self, cache_ttl=None):
        """Initialize manager with optional cache TTL override.

        Args:
            cache_ttl: Optional cache time-to-live in seconds.
        """
        self._cache = {}
        self.cache_ttl = cache_ttl or self.CACHE_TTL

    def _cache_key(self, method_name, *args, **kwargs):
        """Generate a unique cache key from method name and arguments.

        Args:
            method_name: Name of the cached method.
            *args: Positional arguments to include in key.
            **kwargs: Keyword arguments to include in key.

        Returns:
            Hashable cache key string.
        """
        arg_str = "_".join(str(arg) for arg in args)
        kwarg_str = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
        parts = [method_name, arg_str, kwarg_str]
        return "|".join(p for p in parts if p)

    def _get_cached(self, key):
        """Retrieve value from cache if not expired.

        Args:
            key: Cache key.

        Returns:
            Cached value if valid, None otherwise.
        """
        if key not in self._cache:
            return None
        value, timestamp = self._cache[key]
        if time.time() - timestamp > self.cache_ttl:
            del self._cache[key]
            return None
        return value

    def _set_cached(self, key, value):
        """Store value in cache with current timestamp.

        Args:
            key: Cache key.
            value: Value to cache.
        """
        self._cache[key] = (value, time.time())

    def _clear_cache(self):
        """Clear all cached values."""
        self._cache.clear()

    @staticmethod
    def cached(func):
        """Decorator to enable automatic caching for a method.

        Usage:
            @BaseManager.cached
            def fetch_datasets(self, limit=None):
                ...

        Args:
            func: Method to decorate.

        Returns:
            Wrapped method with caching.
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not args:
                return func(*args, **kwargs)

            manager = args[0]
            # Skip manager instance from args for cache key
            cache_key = manager._cache_key(func.__name__, *args[1:], **kwargs)
            cached_value = manager._get_cached(cache_key)
            if cached_value is not None:
                return cached_value
            value = func(*args, **kwargs)
            manager._set_cached(cache_key, value)
            return value
        return wrapper

    def _log(self, message, level="INFO"):
        """Log a message with level prefix.

        Args:
            message: Log message.
            level: Log level ("DEBUG", "INFO", "WARNING", "ERROR").
        """
        print(f"[{self.__class__.__name__}] {level}: {message}")

    def _handle_error(self, error, context=""):
        """Handle and log an error, raising ClearlyHubError.

        Args:
            error: Exception that occurred.
            context: Optional context string.

        Raises:
            ClearlyHubError wrapping the original exception.
        """
        msg = f"{context}: {str(error)}" if context else str(error)
        self._log(msg, "ERROR")
        raise ClearlyHubError(msg) from error
