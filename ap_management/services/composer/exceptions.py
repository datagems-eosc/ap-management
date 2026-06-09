class CompositionInputError(ValueError):
    """Raised when the caller-provided APs are invalid or incompatible."""


class CompositionInternalError(RuntimeError):
    """Raised when the composition logic itself produces an invalid result."""


class CompositionImpossibleError(RuntimeError):
    """Raised when the APs are deemed incompatible."""
