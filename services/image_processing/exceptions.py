class InvalidImageError(ValueError):
    """Raised when an input file cannot produce a usable image."""


class PatternValidationError(ValueError):
    """Raised when a generated pattern violates a hard requirement."""
