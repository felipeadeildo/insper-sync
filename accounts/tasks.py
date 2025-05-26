from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

from core.insper import InsperAuth
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

    base_url = f"https://{DOMAIN}"

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


@shared_task
def update_user_insper_academic_data(user_id):
    """
    Task para atualizar dados do Insper do usuário de forma assíncrona
    """

    try:
        user = User.objects.get(id=user_id)

        # Verifica se o usuário tem credenciais do Insper configuradas
        if not user.has_insper_credentials():
            return f"Usuário {user.email} não possui credenciais do Insper configuradas"

        if not user.insper_portal_id:
            return f"Usuário {user.email} não possui portal_id configurado"

        with InsperAuth() as auth:
            success = auth.login(
                user.insper_username, user.insper_enc_password, encrypt=False
            )
            if not success:
                return f"Erro ao logar no Insper para {user.email}"

            academic_data = auth.get_user_academic_data()

        if academic_data is None:
            return f"Erro ao buscar dados acadêmicos do Insper para {user.email}"

        # Atualiza os dados do usuário com as informações do portal
        updated_fields = ["name", "insper_matricula", "insper_turma", "insper_curso"]

        user.name = academic_data.nomeAluno
        user.insper_matricula = academic_data.matricula
        user.insper_turma = academic_data.turma
        user.insper_curso = academic_data.nomeCurso

        user.save(update_fields=updated_fields)

        return f"Dados do Insper atualizados com sucesso para {user.email}. Campos atualizados: {', '.join(updated_fields)}"

    except User.DoesNotExist:
        return f"Usuário com ID {user_id} não encontrado"
    except Exception as e:
        return f"Erro inesperado ao atualizar dados do Insper para usuário {user_id}: {str(e)}"
