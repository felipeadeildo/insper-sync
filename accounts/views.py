from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from core.utils import encrypt_insper_password, validate_insper_credentials

from .models import EmailVerificationToken, User
from .tasks import send_verification_email


def verify_email(request):
    """View para solicitar verificação de email"""
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()

        if not email.endswith(("@al.insper.edu.br", "@insper.edu.br")):
            messages.error(
                request,
                "Apenas emails do Insper (@al.insper.edu.br ou @insper.edu.br) são aceitos.",
            )
            return redirect("home")

        user, _ = User.objects.get_or_create(
            email=email, defaults={"name": email.split("@")[0]}
        )

        try:
            transaction.on_commit(lambda: send_verification_email.delay(user.pk))

            messages.success(
                request,
                f"Email de verificação enviado para {email}. Verifique sua caixa de entrada (e spam).",
            )
        except Exception:
            messages.warning(
                request,
                "Erro ao processar solicitação de verificação. Tente novamente.",
            )

        return redirect("home")

    return redirect("home")


def verify_token(request, token):
    """View para verificar o token enviado por email"""
    verification_token = get_object_or_404(EmailVerificationToken, token=token)

    if not verification_token.is_valid():
        messages.error(request, "Token inválido ou expirado.")
        return redirect("home")

    # Ativar usuário e marcar email como verificado
    user = verification_token.user
    user.email_verified = True
    user.is_active = True
    user.save()

    # Marcar token como usado
    verification_token.use()

    # Fazer login automático
    login(request, user)

    messages.success(
        request, f"Email verificado com sucesso! Bem-vindo(a), {user.name}!"
    )

    # Redirecionar para configuração de credenciais
    return redirect("setup_credentials")


@login_required
def setup_credentials(request):
    """View para configurar credenciais do Insper"""
    if not request.user.is_authenticated:
        messages.error(request, "Você precisa estar logado para acessar esta página.")
        return redirect("home")

    if not request.user.email_verified:
        messages.error(request, "Você precisa verificar seu email primeiro.")
        return redirect("home")

    if request.method == "POST":
        insper_username = request.POST.get("insper_username", "").strip()
        insper_password = request.POST.get("insper_password", "")

        if not insper_username or not insper_password:
            messages.error(request, "Todos os campos são obrigatórios.")
            return render(
                request,
                "accounts/setup_credentials.html",
                {"insper_username": insper_username},
            )

        # Validar credenciais com o sistema do Insper
        is_valid, user_data, error_message = validate_insper_credentials(
            insper_username, insper_password
        )

        if not is_valid:
            messages.error(
                request,
                f"Erro ao validar credenciais: {error_message or 'Credenciais inválidas'}",
            )
            return render(
                request,
                "accounts/setup_credentials.html",
                {"insper_username": insper_username},
            )

        try:
            # Criptografar a senha antes de salvar
            encrypted_password = encrypt_insper_password(insper_password)

            # Salvar credenciais
            request.user.insper_username = insper_username
            request.user.insper_password = encrypted_password
            request.user.credentials_configured = True

            # Atualizar nome do usuário se disponível
            if user_data and user_data.name and not request.user.name:
                request.user.name = user_data.name

            request.user.save()

            messages.success(
                request,
                f"Credenciais configuradas com sucesso! Bem-vindo(a), {user_data.name if user_data else request.user.name}!",
            )
            return redirect("dashboard")

        except Exception as e:
            messages.error(
                request, f"Erro ao salvar credenciais: {str(e)}. Tente novamente."
            )
            return render(
                request,
                "accounts/setup_credentials.html",
                {"insper_username": insper_username},
            )

    # Pass the user's existing insper_username to the template if it exists
    context = {}
    if hasattr(request.user, "insper_username") and request.user.insper_username:
        context["insper_username"] = request.user.insper_username

    return render(request, "accounts/setup_credentials.html", context)


@login_required
def logout_view(request):
    logout(request)
    return redirect("home")
