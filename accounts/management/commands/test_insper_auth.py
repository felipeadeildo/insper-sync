from django.core.management.base import BaseCommand
from django.utils import timezone

from core.utils import InsperAuth, InsperCrypto, validate_insper_credentials


class Command(BaseCommand):
    help = "Testa a autenticação com o sistema do Insper"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            help="Nome de usuário do Insper",
        )
        parser.add_argument(
            "--password",
            type=str,
            help="Senha do Insper",
        )
        parser.add_argument(
            "--test-connection",
            action="store_true",
            help="Apenas testa a conexão com o Insper",
        )
        parser.add_argument(
            "--test-crypto",
            action="store_true",
            help="Testa a obtenção da chave pública e criptografia",
        )

    def handle(self, *args, **options):
        if options["test_connection"]:
            self.test_connection()
        elif options["test_crypto"]:
            self.test_crypto()
        elif options["username"] and options["password"]:
            self.test_full_auth(options["username"], options["password"])
        else:
            self.stdout.write(
                self.style.ERROR(
                    "Uso: --test-connection, --test-crypto ou --username <user> --password <pass>"
                )
            )

    def test_connection(self):
        """Testa apenas a conexão com o Insper"""
        self.stdout.write("Testando conexão com o Insper...")

        try:
            with InsperAuth() as auth:
                if auth.test_connection():
                    self.stdout.write(
                        self.style.SUCCESS(
                            "✓ Conexão com o Insper estabelecida com sucesso!"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR("✗ Falha ao conectar com o Insper")
                    )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Erro durante teste de conexão: {str(e)}")
            )

    def test_crypto(self):
        """Testa a obtenção da chave pública e criptografia"""
        self.stdout.write("Testando criptografia...")

        try:
            # Testa obtenção da chave pública
            self.stdout.write("Obtendo chave pública do Insper...")
            public_key = InsperCrypto.get_public_key()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Chave pública obtida ({len(public_key)} bytes)")
            )

            # Testa criptografia
            self.stdout.write("Testando criptografia de senha...")
            test_password = "test_password_123"
            encrypted = InsperCrypto.encrypt_password(test_password)
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Senha criptografada com sucesso ({len(encrypted)} chars)"
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Erro durante teste de criptografia: {str(e)}")
            )

    def test_full_auth(self, username: str, password: str):
        """Testa autenticação completa com credenciais"""
        self.stdout.write(f"Testando autenticação para usuário: {username}")

        start_time = timezone.now()

        try:
            is_valid, user_data, error_message = validate_insper_credentials(
                username, password
            )

            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()

            if is_valid and user_data:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Autenticação bem-sucedida! ({duration:.2f}s)"
                    )
                )
                self.stdout.write(f"  ID: {user_data.id}")
                self.stdout.write(f"  Nome: {user_data.name}")
                self.stdout.write(f"  Login: {user_data.login}")
                self.stdout.write(f"  Roles: {user_data.roles}")
                self.stdout.write(f"  Root: {user_data.root}")
                self.stdout.write(f"  Theme: {user_data.theme}")
            else:
                self.stdout.write(
                    self.style.ERROR(f"✗ Falha na autenticação: {error_message}")
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Erro durante autenticação: {str(e)}")
            )
