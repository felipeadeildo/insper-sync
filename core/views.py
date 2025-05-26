from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


def home(request):
    """Homepage with email verification form"""
    return render(request, "index.html")


def terms_of_use(request):
    """Página de termos de uso"""
    return render(request, "terms_of_use.html")


@login_required
def dashboard(request):
    """Dashboard do usuário"""
    if not request.user.email_verified:
        messages.error(request, "Você precisa verificar seu email primeiro.")
        return redirect("home")

    if not request.user.credentials_configured:
        messages.info(request, "Configure suas credenciais do Insper para continuar.")
        return redirect("setup_credentials")

    # Calcular estatísticas para o dashboard
    user = request.user

    context = {
        "google_status": {
            "connected": user.google_connected,
            "calendar_id": user.google_calendar_id,
            "token_expired": user.is_google_token_expired()
            if user.google_connected
            else False,
            "expires_at": user.google_token_expires_at,
        },
        "sync_stats": {
            "can_sync": user.can_sync(),
            "last_sync": user.last_sync,
            "sync_enabled": user.sync_enabled,
        },
        "account_status": {
            "email_verified": user.email_verified,
            "credentials_configured": user.credentials_configured,
            "is_insper_email": user.is_insper_email(),
            "has_insper_credentials": user.has_insper_credentials(),
            "has_google_credentials": user.has_google_credentials(),
        },
    }

    return render(request, "dashboard.html", context)
