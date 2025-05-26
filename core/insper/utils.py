"""
Utilitários gerais para o módulo Insper
"""

from django.core.cache import cache

from .crypto import InsperCrypto


def clear_insper_cache():
    """
    Limpa o cache da chave pública do Insper.
    Útil quando há problemas de conexão ou mudanças no sistema.
    """
    cache.delete(InsperCrypto.CACHE_KEY)


def get_insper_cache_info() -> dict:
    """
    Retorna informações sobre o cache da chave pública do Insper.

    Returns:
        Dicionário com informações do cache
    """
    public_key = cache.get(InsperCrypto.CACHE_KEY)

    return {
        "cached": public_key is not None,
        "key_size": len(public_key) if public_key else 0,
        "cache_key": InsperCrypto.CACHE_KEY,
        "timeout": InsperCrypto.CACHE_TIMEOUT,
    }
