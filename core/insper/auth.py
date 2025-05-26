"""
Utilitários para autenticação com o sistema do Insper
"""

import base64
import json
from typing import Optional

import httpx

from .crypto import InsperCrypto
from .exceptions import InsperAuthError
from .models import InsperAcademicData, InsperUserData


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
            raise InsperAuthError(f"Erro ao processar dados do usuário: {str(e)}")

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
