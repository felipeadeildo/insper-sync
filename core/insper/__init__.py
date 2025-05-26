"""
Módulo para integração com sistemas do Insper
"""

from .auth import InsperAuth, validate_insper_credentials
from .calendar import InsperCalendar, InsperEvent
from .crypto import InsperCrypto, encrypt_insper_password
from .exceptions import InsperAuthError, InsperConnectionError, InsperCryptoError
from .models import InsperAcademicData, InsperUserData
from .utils import clear_insper_cache, get_insper_cache_info

__all__ = [
    "InsperAuth",
    "InsperCrypto",
    "InsperUserData",
    "InsperAcademicData",
    "InsperCalendar",
    "InsperEvent",
    "validate_insper_credentials",
    "encrypt_insper_password",
    "clear_insper_cache",
    "get_insper_cache_info",
    "InsperConnectionError",
    "InsperAuthError",
    "InsperCryptoError",
]
