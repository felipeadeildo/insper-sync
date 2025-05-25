from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase

from .utils import InsperAuth, InsperCrypto, validate_insper_credentials


class InsperCryptoTest(TestCase):
    """Testes para a classe InsperCrypto"""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch("core.utils.httpx.Client")
    def test_get_public_key_success(self, mock_client):
        """Testa a obtenção bem-sucedida da chave pública"""
        # Mock da resposta
        mock_response = MagicMock()
        mock_response.content = (
            b"-----BEGIN PUBLIC KEY-----\nfake_key\n-----END PUBLIC KEY-----"
        )
        mock_response.raise_for_status.return_value = None

        # Mock do cliente
        mock_client_instance = MagicMock()
        mock_client_instance.__enter__.return_value = mock_client_instance
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value = mock_client_instance

        # Testa a função
        public_key = InsperCrypto.get_public_key()

        # Verifica se a chave foi retornada
        self.assertEqual(
            public_key,
            b"-----BEGIN PUBLIC KEY-----\nfake_key\n-----END PUBLIC KEY-----",
        )

        # Verifica se foi armazenada em cache
        cached_key = cache.get(InsperCrypto.CACHE_KEY)
        self.assertEqual(cached_key, public_key)

    @patch("core.utils.httpx.Client")
    def test_get_public_key_from_cache(self, mock_client):
        """Testa a obtenção da chave pública do cache"""
        # Coloca uma chave fake no cache
        fake_key = b"cached_public_key"
        cache.set(InsperCrypto.CACHE_KEY, fake_key)

        # Testa a função
        public_key = InsperCrypto.get_public_key()

        # Verifica se retornou a chave do cache
        self.assertEqual(public_key, fake_key)

        # Verifica se não fez requisição HTTP
        mock_client.assert_not_called()

    @patch("core.utils.load_pem_public_key")
    @patch("core.utils.InsperCrypto.get_public_key")
    def test_encrypt_password_success(self, mock_get_key, mock_load_key):
        """Testa a criptografia bem-sucedida de senha"""
        # Mock da chave pública
        mock_public_key = MagicMock()
        mock_public_key.encrypt.return_value = b"encrypted_password"
        mock_load_key.return_value = mock_public_key
        mock_get_key.return_value = b"fake_pem_key"

        # Testa a função
        encrypted = InsperCrypto.encrypt_password("test_password")

        # Verifica se a senha foi criptografada e convertida para base64
        import base64

        expected = base64.b64encode(b"encrypted_password").decode("utf-8")
        self.assertEqual(encrypted, expected)


class InsperAuthTest(TestCase):
    """Testes para a classe InsperAuth"""

    @patch("core.utils.httpx.Client")
    def test_test_connection_success(self, mock_client):
        """Testa conexão bem-sucedida"""
        # Mock da resposta
        mock_response = MagicMock()
        mock_response.status_code = 200

        # Mock do cliente
        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value = mock_client_instance

        # Testa a função
        auth = InsperAuth()
        result = auth.test_connection()

        # Verifica se retornou True
        self.assertTrue(result)

    @patch("core.utils.httpx.Client")
    def test_test_connection_failure(self, mock_client):
        """Testa falha na conexão"""
        # Mock do cliente que gera exceção no __init__
        mock_client_instance = MagicMock()
        mock_client_instance.get.side_effect = Exception("Connection error")
        mock_client.return_value = mock_client_instance

        # Usar patch adicional para o __init__ para evitar erro
        with patch.object(InsperAuth, "__init__", lambda x: None):
            # Testa a função
            auth = InsperAuth()
            auth.session = mock_client_instance
            result = auth.test_connection()

            # Verifica se retornou False
            self.assertFalse(result)


class ValidateInsperCredentialsTest(TestCase):
    """Testes para a função validate_insper_credentials"""

    @patch("core.utils.InsperAuth")
    def test_validate_credentials_success(self, mock_auth_class):
        """Testa validação bem-sucedida de credenciais"""
        # Mock dos dados do usuário
        from core.utils import InsperUserData

        fake_user_data = InsperUserData(
            id="123",
            name="Test User",
            login="test@insper.edu.br",
            senhaAlterada="false",
            roles="student",
            root=False,
            theme="light",
        )

        # Mock da classe InsperAuth
        mock_auth_instance = MagicMock()
        mock_auth_instance.test_connection.return_value = True
        mock_auth_instance.validate_credentials.return_value = fake_user_data
        mock_auth_instance.__enter__.return_value = mock_auth_instance
        mock_auth_instance.__exit__.return_value = None
        mock_auth_class.return_value = mock_auth_instance

        # Testa a função
        is_valid, user_data, error = validate_insper_credentials(
            "test_user", "test_password"
        )

        # Verifica o resultado
        self.assertTrue(is_valid)
        self.assertEqual(user_data, fake_user_data)
        self.assertIsNone(error)

    @patch("core.utils.InsperAuth")
    def test_validate_credentials_invalid(self, mock_auth_class):
        """Testa credenciais inválidas"""
        # Mock da classe InsperAuth
        mock_auth_instance = MagicMock()
        mock_auth_instance.test_connection.return_value = True
        mock_auth_instance.validate_credentials.return_value = None
        mock_auth_instance.__enter__.return_value = mock_auth_instance
        mock_auth_instance.__exit__.return_value = None
        mock_auth_class.return_value = mock_auth_instance

        # Testa a função
        is_valid, user_data, error = validate_insper_credentials(
            "test_user", "wrong_password"
        )

        # Verifica o resultado
        self.assertFalse(is_valid)
        self.assertIsNone(user_data)
        self.assertEqual(error, "Credenciais inválidas")

    @patch("core.utils.InsperAuth")
    def test_validate_credentials_connection_error(self, mock_auth_class):
        """Testa erro de conexão"""
        # Mock da classe InsperAuth
        mock_auth_instance = MagicMock()
        mock_auth_instance.test_connection.return_value = False
        mock_auth_instance.__enter__.return_value = mock_auth_instance
        mock_auth_instance.__exit__.return_value = None
        mock_auth_class.return_value = mock_auth_instance

        # Testa a função
        is_valid, user_data, error = validate_insper_credentials(
            "test_user", "test_password"
        )

        # Verifica o resultado
        self.assertFalse(is_valid)
        self.assertIsNone(user_data)
        self.assertEqual(error, "Não foi possível conectar com o sistema do Insper")
