from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse

from .models import EmailVerificationToken, User


def verify_email(request):
    """View para solicitar verificação de email"""
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()

        # Validar se é email do Insper
        if not email.endswith(("@al.insper.edu.br", "@insper.edu.br")):
            messages.error(
                request,
                "Apenas emails do Insper (@al.insper.edu.br ou @insper.edu.br) são aceitos.",
            )
            return redirect("home")

        # Criar ou buscar usuário
        user, created = User.objects.get_or_create(
            email=email, defaults={"name": email.split("@")[0]}
        )

        # Criar token de verificação
        token = EmailVerificationToken.objects.create(user=user)

        # Enviar email de verificação
        verification_url = request.build_absolute_uri(
            reverse("verify_token", kwargs={"token": token.token})
        )

        # Renderizar template do email
        email_html = render_to_string(
            "emails/verify_email.html",
            {
                "verification_url": verification_url,
                "user": user,
            },
        )

        try:
            # Enviar email
            send_mail(
                subject="Verificação de Email - Insper Sync",
                message=f"Acesse o link para verificar seu email: {verification_url}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=email_html,
                fail_silently=False,
            )

            messages.success(
                request,
                f"Email de verificação enviado para {email}. Verifique sua caixa de entrada (e spam).",
            )
        except Exception:
            # Em caso de erro no envio, mostrar o link para desenvolvimento
            messages.warning(
                request,
                f"Erro ao enviar email. Para desenvolvimento, acesse: {verification_url}",
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
            return render(request, "accounts/setup_credentials.html")

        # TODO: Criptografar a senha antes de salvar
        request.user.insper_username = insper_username
        request.user.insper_password = insper_password  # TODO: criptografar
        request.user.credentials_configured = True
        request.user.save()

        messages.success(request, "Credenciais configuradas com sucesso!")
        return redirect("dashboard")

    return render(request, "accounts/setup_credentials.html")


def dashboard(request):
    """Dashboard do usuário"""
    if not request.user.is_authenticated:
        return redirect("home")

    if not request.user.email_verified:
        messages.error(request, "Você precisa verificar seu email primeiro.")
        return redirect("home")

    if not request.user.credentials_configured:
        messages.info(request, "Configure suas credenciais do Insper para continuar.")
        return redirect("setup_credentials")

    context = {}

    return render(request, "accounts/dashboard.html", context)
