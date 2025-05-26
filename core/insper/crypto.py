"""
Utilitários para criptografia com o sistema do Insper
"""

import base64

import httpx
from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from django.core.cache import cache

from .exceptions import InsperCryptoError


class InsperCrypto:
    """Utilitários para criptografia com o sistema do Insper"""

    PADDING = PKCS1v15()
    ENCODING = "utf-8"
    CACHE_KEY = "insper_public_key"
    CACHE_TIMEOUT = 3600  # 1 hora

    @classmethod
    def get_public_key(cls) -> bytes:
        """
        Obtém a chave pública do Insper.
        Utiliza cache para evitar requisições desnecessárias.
        """
        # Tenta obter da cache primeiro
        public_key_pem = cache.get(cls.CACHE_KEY)

        if public_key_pem is None:
            # Se não está em cache, faz requisição
            try:
                with httpx.Client(base_url="https://sga.insper.edu.br") as client:
                    # Primeiro faz uma requisição para definir cookies
                    client.get("/AOnline/auth")

                    # Depois obtém a chave pública
                    response = client.get("/AOnline/config-properties/public-key")
                    response.raise_for_status()

                    public_key_pem = response.content

                    # Armazena em cache
                    cache.set(cls.CACHE_KEY, public_key_pem, cls.CACHE_TIMEOUT)

            except Exception as e:
                raise InsperCryptoError(
                    f"Erro ao obter chave pública do Insper: {str(e)}"
                )

        return public_key_pem

    @classmethod
    def encrypt_password(cls, password: str) -> str:
        """
        Criptografa uma senha usando a chave pública do Insper.

        Args:
            password: Senha em texto plano

        Returns:
            Senha criptografada em base64
        """
        try:
            # Obtém a chave pública
            public_key_pem = cls.get_public_key()
            public_key = load_pem_public_key(public_key_pem)

            # Codifica a senha
            encoded_password = password.encode(cls.ENCODING)

            # Criptografa a senha
            encrypted_password = public_key.encrypt(encoded_password, cls.PADDING)  # type: ignore

            # Retorna em base64
            return base64.b64encode(encrypted_password).decode("utf-8")

        except Exception as e:
            raise InsperCryptoError(f"Erro ao criptografar senha: {str(e)}")


def encrypt_insper_password(password: str) -> str:
    """
    Função de conveniência para criptografar senha do Insper.

    Args:
        password: Senha em texto plano

    Returns:
        Senha criptografada em base64

    Raises:
        InsperCryptoError: Em caso de erro na criptografia
    """
    return InsperCrypto.encrypt_password(password)
