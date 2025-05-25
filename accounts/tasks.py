from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

from core.settings import DOMAIN

from .models import EmailVerificationToken, User


@shared_task
def send_verification_email(user_id):
    """
    Task para enviar email de verificação de forma assíncrona
    """
    # Buscar o usuário
    user = User.objects.get(id=user_id)

    # Criar token de verificação
    token = EmailVerificationToken.objects.create(user=user)

    base_url = f"https://{DOMAIN}/"

    verification_url = (
        f"{base_url}{reverse('verify_token', kwargs={'token': token.token})}"
    )

    # Renderizar template do email
    email_html = render_to_string(
        "emails/verify_email.html",
        {
            "verification_url": verification_url,
            "user": user,
        },
    )

    # Enviar email
    send_mail(
        subject="Verificação de Email - Insper Sync",
        message=f"Acesse o link para verificar seu email: {verification_url}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=email_html,
        fail_silently=False,
    )

    return f"Email de verificação enviado com sucesso para {user.email}"
