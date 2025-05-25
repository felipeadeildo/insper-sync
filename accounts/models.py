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
    insper_password = models.CharField(
        max_length=255, blank=True, help_text="Senha criptografada do Portal Acadêmico"
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
        """Verifica se o usuário pode sincronizar (email verificado e credenciais configuradas)"""
        return self.email_verified and self.credentials_configured and self.is_active


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
