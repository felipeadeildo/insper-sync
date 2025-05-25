from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import EmailVerificationToken, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Informações Pessoais", {"fields": ("name",)}),
        ("Credenciais Insper", {"fields": ("insper_username", "insper_password")}),
        (
            "Status",
            {
                "fields": (
                    "email_verified",
                    "credentials_configured",
                    "sync_enabled",
                    "last_sync",
                )
            },
        ),
        (
            "Permissões",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Datas Importantes", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "name", "password1", "password2"),
            },
        ),
    )
    list_display = (
        "email",
        "name",
        "email_verified",
        "credentials_configured",
        "sync_enabled",
        "is_active",
        "last_sync",
    )
    list_filter = (
        "email_verified",
        "credentials_configured",
        "sync_enabled",
        "is_staff",
        "is_superuser",
        "is_active",
    )
    search_fields = ("email", "name")
    ordering = ("email",)
    readonly_fields = ("last_sync",)


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "token", "created_at", "expires_at", "used_at")
    list_filter = ("created_at", "expires_at", "used_at")
    search_fields = ("user__email", "token")
    readonly_fields = ("token", "created_at", "expires_at", "used_at")
