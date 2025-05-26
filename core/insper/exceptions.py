"""
Exceções customizadas para o módulo Insper
"""


class InsperConnectionError(Exception):
    """Exceção customizada para erros de conexão com o Insper"""

    pass


class InsperAuthError(Exception):
    """Exceção customizada para erros de autenticação com o Insper"""

    pass


class InsperCryptoError(Exception):
    """Exceção customizada para erros de criptografia"""

    pass
