from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.crypto import get_random_string

from core.google_calendar import GoogleCalendarClient, get_or_refresh_access_token
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
            if user_data:
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


@login_required
def google_auth(request):
    """Inicia o processo de autenticação OAuth com Google"""
    if not request.user.email_verified:
        messages.error(request, "Você precisa verificar seu email primeiro.")
        return redirect("home")

    if not request.user.credentials_configured:
        messages.error(request, "Configure suas credenciais do Insper primeiro.")
        return redirect("setup_credentials")

    # Gerar estado CSRF para validação
    state = get_random_string(32)
    request.session["google_oauth_state"] = state

    # Criar cliente e obter URL de autorização
    client = GoogleCalendarClient()
    auth_url = client.get_authorization_url(state=state)

    return redirect(auth_url)


@login_required
def google_callback(request):
    """Callback do OAuth do Google"""
    code = request.GET.get("code")
    state = request.GET.get("state")
    error = request.GET.get("error")

    # Verificar se houve erro na autorização
    if error:
        messages.error(request, f"Erro na autorização: {error}")
        return redirect("dashboard")

    # Verificar estado CSRF
    if not state or state != request.session.get("google_oauth_state"):
        messages.error(request, "Estado de autorização inválido.")
        return redirect("dashboard")

    # Limpar estado da sessão
    request.session.pop("google_oauth_state", None)

    if not code:
        messages.error(request, "Código de autorização não fornecido.")
        return redirect("dashboard")

    # Trocar código por tokens
    client = GoogleCalendarClient()
    success, token_data, error_msg = client.exchange_code_for_tokens(code)

    if not success or not token_data:
        messages.error(request, f"Erro ao obter tokens: {error_msg}")
        return redirect("dashboard")

    try:
        # Obter informações do calendário principal
        client.access_token = token_data["access_token"]
        calendar_success, calendar_data, calendar_error = client.get_primary_calendar()

        calendar_id = "primary"
        if calendar_success and calendar_data:
            calendar_id = calendar_data.get("id", "primary")

        # Salvar credenciais do Google
        request.user.update_google_credentials(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_in=token_data.get("expires_in", 3600),
            calendar_id=calendar_id,
        )

        messages.success(
            request,
            "Google Calendar conectado com sucesso! Agora você pode sincronizar seus eventos.",
        )

    except Exception as e:
        messages.error(request, f"Erro ao salvar credenciais do Google: {str(e)}")

    return redirect("dashboard")


@login_required
def google_disconnect(request):
    """Desconecta a conta do Google"""
    if request.method == "POST":
        try:
            request.user.disconnect_google()
            messages.success(request, "Conta do Google desconectada com sucesso.")
        except Exception as e:
            messages.error(request, f"Erro ao desconectar conta do Google: {str(e)}")

    return redirect("dashboard")


@login_required
def test_google_connection(request):
    """Testa a conexão com Google Calendar"""
    if not request.user.google_connected:
        messages.error(request, "Conta do Google não está conectada.")
        return redirect("dashboard")

    # Obter token válido
    success, access_token, error_msg = get_or_refresh_access_token(request.user)

    if not success or not access_token:
        messages.error(request, f"Erro ao obter token de acesso: {error_msg}")
        return redirect("dashboard")

    # Testar listagem de calendários
    client = GoogleCalendarClient(access_token)
    success, calendars, error_msg = client.get_calendar_list()

    if success and calendars is not None:
        messages.success(
            request,
            f"Conexão testada com sucesso! Encontrados {len(calendars)} calendários.",
        )
    else:
        messages.error(request, f"Erro ao testar conexão: {error_msg}")

    return redirect("dashboard")
