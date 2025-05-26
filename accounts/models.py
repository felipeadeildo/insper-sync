import datetime
import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields) -> "User":
        if not email:
            raise ValueError("O campo de email deve ser preenchido")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_active", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if not extra_fields.get("is_staff") or not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_staff=True and is_superuser=True")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    username = None
    first_name = None
    last_name = None

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=150, blank=True)

    insper_username = models.CharField(
        max_length=100, blank=True, help_text="Username do Portal Acadêmico do Insper"
    )
    insper_enc_password = models.CharField(
        max_length=255, blank=True, help_text="Senha criptografada do Portal Acadêmico"
    )
    insper_portal_id = models.CharField(
        max_length=255, blank=True, help_text="ID do Portal Acadêmico"
    )
    insper_matricula = models.CharField(
        max_length=255, blank=True, help_text="Matricula do Portal Acadêmico"
    )
    insper_turma = models.CharField(
        max_length=255, blank=True, help_text="Turma do Portal Acadêmico"
    )
    insper_curso = models.CharField(
        max_length=255, blank=True, help_text="Curso do Portal Acadêmico"
    )

    # Google Calendar integration fields
    google_access_token = models.TextField(
        blank=True, help_text="Token de acesso do Google Calendar"
    )
    google_refresh_token = models.TextField(
        blank=True, help_text="Token de refresh do Google Calendar"
    )
    google_token_expires_at = models.DateTimeField(
        null=True, blank=True, help_text="Data de expiração do token do Google"
    )
    google_calendar_id = models.CharField(
        max_length=255, blank=True, help_text="ID do calendário principal do Google"
    )
    google_connected = models.BooleanField(
        default=False, help_text="Indica se a conta Google está conectada"
    )

    email_verified = models.BooleanField(default=False)
    credentials_configured = models.BooleanField(default=False)
    sync_enabled = models.BooleanField(default=False)
    last_sync = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)

    objects: UserManager = UserManager()  # type: ignore

    def __str__(self) -> str:
        return f"{self.name or self.email} <{self.email}>"

    def is_insper_email(self) -> bool:
        """Verifica se o email é do domínio do Insper"""
        return self.email.endswith(("@al.insper.edu.br", "@insper.edu.br"))

    def can_sync(self) -> bool:
        """Verifica se o usuário pode sincronizar (email verificado, credenciais configuradas e Google conectado)"""
        return (
            self.email_verified
            and self.credentials_configured
            and self.google_connected
            and self.is_active
        )

    def has_insper_credentials(self) -> bool:
        """Verifica se o usuário tem credenciais do Insper configuradas"""
        return bool(self.insper_username and self.insper_enc_password)

    def has_google_credentials(self) -> bool:
        """Verifica se o usuário tem credenciais do Google configuradas"""
        return bool(self.google_access_token and self.google_refresh_token)

    def is_google_token_expired(self) -> bool:
        """Verifica se o token do Google expirou"""
        if not self.google_token_expires_at:
            return True
        return (
            datetime.datetime.now(datetime.timezone.utc) >= self.google_token_expires_at
        )

    def update_google_credentials(
        self,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        calendar_id: str = "",
    ):
        """
        Atualiza as credenciais do Google do usuário.

        Args:
            access_token: Token de acesso do Google
            refresh_token: Token de refresh do Google
            expires_in: Tempo em segundos até a expiração do token
            calendar_id: ID do calendário principal (opcional)
        """
        self.google_access_token = access_token
        self.google_refresh_token = refresh_token
        self.google_token_expires_at = datetime.datetime.now(
            datetime.timezone.utc
        ) + datetime.timedelta(seconds=expires_in)
        if calendar_id:
            self.google_calendar_id = calendar_id
        self.google_connected = True
        self.save(
            update_fields=[
                "google_access_token",
                "google_refresh_token",
                "google_token_expires_at",
                "google_calendar_id",
                "google_connected",
            ]
        )

    def disconnect_google(self):
        """Desconecta a conta do Google"""
        self.google_access_token = ""
        self.google_refresh_token = ""
        self.google_token_expires_at = None
        self.google_calendar_id = ""
        self.google_connected = False
        self.save(
            update_fields=[
                "google_access_token",
                "google_refresh_token",
                "google_token_expires_at",
                "google_calendar_id",
                "google_connected",
            ]
        )

    def update_insper_credentials(
        self, username: str, encrypted_password: str, portal_id: str
    ):
        """
        Atualiza as credenciais do Insper do usuário.

        Args:
            username: Nome de usuário do Insper
            encrypted_password: Senha já criptografada
            portal_id: ID do Portal Acadêmico
        """
        self.insper_username = username
        self.insper_enc_password = encrypted_password
        self.insper_portal_id = portal_id
        self.credentials_configured = True
        self.save(
            update_fields=[
                "insper_username",
                "insper_enc_password",
                "insper_portal_id",
                "credentials_configured",
            ]
        )


class EmailVerificationToken(models.Model):
    """Token para verificação de email"""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="verification_tokens"
    )
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()

    def __str__(self) -> str:
        return f"Token para {self.user.email}"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = str(uuid.uuid4())
        if not self.expires_at:
            self.expires_at = datetime.datetime.now(
                datetime.timezone.utc
            ) + datetime.timedelta(hours=24)
        super().save(*args, **kwargs)

    def is_valid(self) -> bool:
        """Verifica se o token ainda é válido"""
        return (
            not self.used_at
            and datetime.datetime.now(datetime.timezone.utc) < self.expires_at
        )

    def use(self):
        """Marca o token como usado"""
        self.used_at = datetime.datetime.now(datetime.timezone.utc)
        self.save()
