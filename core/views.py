from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


def home(request):
    """Homepage with email verification form"""
    return render(request, "index.html")


@login_required
def dashboard(request):
    """Dashboard do usuário"""
    if not request.user.email_verified:
        messages.error(request, "Você precisa verificar seu email primeiro.")
        return redirect("home")

    if not request.user.credentials_configured:
        messages.info(request, "Configure suas credenciais do Insper para continuar.")
        return redirect("setup_credentials")

    context = {}

    return render(request, "accounts/dashboard.html", context)
    return render(request, "accounts/dashboard.html", context)
