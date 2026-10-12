"""Nieoficjalny klient API mobilnego eduVULCAN (Hebe CE)."""

from .api import VulcanApi
from .credential import Credential
from .errors import ApiError, AuthError, TransportError, VulcanError

__all__ = ["VulcanApi", "Credential", "VulcanError", "ApiError", "AuthError", "TransportError"]
__version__ = "0.1.0"
