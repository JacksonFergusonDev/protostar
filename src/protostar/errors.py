"""Domain-specific exceptions for Protostar."""


class ProtostarError(Exception):
    """Base class for all expected operational errors in Protostar."""

    pass


class ConfigurationError(ProtostarError):
    """Raised when a configuration file is malformed, invalid, or missing requirements."""

    pass
