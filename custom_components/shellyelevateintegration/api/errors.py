"""Exceptions raised by the ShellyElevate API clients."""

from __future__ import annotations


class ShellyElevateIntegrationError(Exception):
    """Base error."""


class ShellyElevateIntegrationConnectionError(ShellyElevateIntegrationError):
    """The display could not be reached."""


class ShellyElevateIntegrationAuthError(ShellyElevateIntegrationError):
    """The token was rejected or is missing."""


class ShellyElevateIntegrationCertificateError(ShellyElevateIntegrationAuthError):
    """The display presented a different certificate than the pinned one."""


class ShellyElevateIntegrationPairingError(ShellyElevateIntegrationError):
    """Pairing failed (wrong code, expired, ...)."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


class ShellyElevateIntegrationCommandError(ShellyElevateIntegrationError):
    """The display rejected a command."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code


class ShellyElevateIntegrationUnsupportedError(ShellyElevateIntegrationCommandError):
    """The command or feature is not supported by this app version / transport."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__("unsupported", message)


class ShellyElevateIntegrationIncompatibleError(ShellyElevateIntegrationError):
    """The display speaks an incompatible protocol major version."""
