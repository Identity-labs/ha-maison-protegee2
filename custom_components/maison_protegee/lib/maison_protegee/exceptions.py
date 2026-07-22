"""Maison Protégée API exceptions."""


class MaisonProtegeeError(Exception):
    """Base error for the Orange Maison Protégée client."""


class AuthenticationError(MaisonProtegeeError):
    """Login or token validation failed."""


class ApiError(MaisonProtegeeError):
    """gRPC call succeeded but the backend returned an error status."""

    def __init__(self, status: str, message: str = ""):
        self.status = status
        self.api_message = message
        super().__init__(f"{status}: {message}" if message else status)
