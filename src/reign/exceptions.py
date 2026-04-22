"""Custom exception hierarchy."""


class AppError(Exception):
    """Base exception for the application."""


class ValidationError(AppError):
    """Raised when input validation fails."""


class NotFoundError(AppError):
    """Raised when a requested resource is not found."""


class CSVParseError(AppError):
    """Raised when CSV parsing fails."""
