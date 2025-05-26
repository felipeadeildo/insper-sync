import base64
import json
from dataclasses import dataclass
from typing import Optional

import httpx
from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from django.core.cache import cache


@dataclass
class InsperUserData:
    """Dados do usuário do Insper retornados após login"""

    id: str
    name: str
    login: str
    senhaAlterada: str
    roles: str
    root: bool
    theme: str


@dataclass
class InsperAcademicData:
    """Dados acadêmicos do usuário do Insper retornados após consulta"""

    id: str
    matricula: str
    codAluno: str
    situacaoAluno: str
    nomeAluno: str
    codCurso: str
    nomeCurso: str
    sexo: str
    turma: str
    serie: str
    ano: str
    semestre: str
    descrSemestre: str
    # user: dict
    # usuarioLogado: dict
    # foto: Optional[str]
    # links: list

    @classmethod
    def from_dict(cls, data: dict):
        """
        Cria uma instância da classe a partir de um dicionário,
        ignorando campos extras que não estão definidos na classe.
        """
        # Filtra apenas as chaves que existem como campos na classe
        valid_fields = {k: v for k, v in data.items() if k in cls.__annotations__}
        return cls(**valid_fields)


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
                raise Exception(f"Erro ao obter chave pública do Insper: {str(e)}")

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
            raise Exception(f"Erro ao criptografar senha: {str(e)}")


class InsperAuth:
    """Utilitários para autenticação com o sistema do Insper"""

    user_data: InsperUserData

    def __init__(self):
        self.session = httpx.Client(base_url="https://sga.insper.edu.br")
        # Define cookies iniciais
        self.session.get("/AOnline/auth")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def _parse_user_data(self, response: httpx.Response) -> InsperUserData:
        """Parse dos dados do usuário a partir da resposta de login"""
        try:
            user_data_cookie = response.cookies["user-data"]
            user_data_bytes = base64.b64decode(user_data_cookie)
            user_data_str = user_data_bytes.decode("utf-8")
            user_data_dict = json.loads(user_data_str)

            self.user_data = InsperUserData(**user_data_dict)
            return self.user_data

        except Exception as e:
            raise Exception(f"Erro ao processar dados do usuário: {str(e)}")

    def login(self, username: str, password: str, encrypt: bool = True) -> bool:
        """
        Autentica o usuário no sistema do Insper para manter a sessão ativa.

        Args:
            username: Nome de usuário do Insper
            password: Senha em texto plano
            encrypt: Se a senha deve ser criptografada

        Returns:
            True se a autenticação foi bem-sucedida, False caso contrário
        """
        try:
            encrypted_password = (
                InsperCrypto.encrypt_password(password) if encrypt else password
            )

            response = self.session.post(
                "/AOnline/auth",
                data={"username": username, "password": encrypted_password},
                headers={"content-type": "application/x-www-form-urlencoded"},
            )

            try:
                self._parse_user_data(response)
            except Exception:
                pass

            return response.status_code == 200 and "user-data" in response.cookies

        except Exception:
            return False

    def get_user_academic_data(self) -> Optional[InsperAcademicData]:
        """
        Busca os dados acadêmicos do usuário no portal do Insper.

        Returns:
            Dados acadêmicos do usuário ou None se não encontrados

        Raises:
            Exception: Em caso de erro na requisição
        """
        portal_id = self.user_data.id
        try:
            response = self.session.get(
                f"/AOnline/apix/api/rest/alunos/user/{portal_id}", timeout=30
            )

            if response.status_code == 200:
                data = response.json()

                # Verifica se há conteúdo na resposta
                if data.get("content") and len(data["content"]) > 0:
                    return InsperAcademicData.from_dict(data["content"][0])

            return None

        except Exception as e:
            raise Exception(f"Erro ao buscar dados acadêmicos: {str(e)}")

    def validate_credentials(
        self, username: str, password: str
    ) -> Optional[InsperUserData]:
        """
        Valida as credenciais do usuário no sistema do Insper.

        Args:
            username: Nome de usuário do Insper
            password: Senha em texto plano

        Returns:
            Dados do usuário se as credenciais forem válidas, None caso contrário

        Raises:
            Exception: Em caso de erro na comunicação com o Insper
        """
        try:
            # Criptografa a senha
            encrypted_password = InsperCrypto.encrypt_password(password)

            # Faz login
            response = self.session.post(
                "/AOnline/auth",
                data={"username": username, "password": encrypted_password},
                headers={"content-type": "application/x-www-form-urlencoded"},
            )

            # Verifica se o login foi bem-sucedido
            if response.status_code == 200 and "user-data" in response.cookies:
                return self._parse_user_data(response)

            return None

        except Exception as e:
            raise Exception(f"Erro ao validar credenciais: {str(e)}")

    def test_connection(self) -> bool:
        """
        Testa se é possível conectar com o sistema do Insper.

        Returns:
            True se a conexão foi bem-sucedida, False caso contrário
        """
        try:
            response = self.session.get("/AOnline/#/login", timeout=10)
            return response.status_code == 200
        except Exception:
            return False


def validate_insper_credentials(
    username: str, password: str
) -> tuple[bool, Optional[InsperUserData], Optional[str]]:
    """
    Função de conveniência para validar credenciais do Insper.

    Args:
        username: Nome de usuário do Insper
        password: Senha em texto plano

    Returns:
        Tupla contendo:
        - bool: Se as credenciais são válidas
        - InsperUserData: Dados do usuário (se válidas)
        - str: Mensagem de erro (se houver)
    """
    try:
        with InsperAuth() as auth:
            # Primeiro testa a conexão
            if not auth.test_connection():
                return False, None, "Não foi possível conectar com o sistema do Insper"

            # Valida as credenciais
            user_data = auth.validate_credentials(username, password)

            if user_data:
                return True, user_data, None
            else:
                return False, None, "Credenciais inválidas"

    except Exception as e:
        return False, None, str(e)


def encrypt_insper_password(password: str) -> str:
    """
    Função de conveniência para criptografar senha do Insper.

    Args:
        password: Senha em texto plano

    Returns:
        Senha criptografada em base64

    Raises:
        Exception: Em caso de erro na criptografia
    """
    return InsperCrypto.encrypt_password(password)


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


class InsperConnectionError(Exception):
    """Exceção customizada para erros de conexão com o Insper"""

    pass


class InsperAuthError(Exception):
    """Exceção customizada para erros de autenticação com o Insper"""

    pass


class InsperCryptoError(Exception):
    """Exceção customizada para erros de criptografia"""

    pass
