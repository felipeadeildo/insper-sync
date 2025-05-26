from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from .models import SyncConfiguration, SyncSession
from .tasks import sync_user_calendar


@login_required
def sync_configuration(request):
    """View para configurar opções de sincronização"""
    sync_config, created = SyncConfiguration.objects.get_or_create(
        user=request.user,
        defaults={"sync_enabled": True, "google_calendar_name": "Insper Sync"},
    )

    if request.method == "POST":
        # Atualiza configurações
        sync_config.sync_enabled = request.POST.get("sync_enabled") == "on"
        sync_config.sync_frequency_hours = int(
            request.POST.get("sync_frequency_hours", 6)
        )
        sync_config.google_calendar_name = request.POST.get(
            "google_calendar_name", "Insper Sync"
        )
        sync_config.add_insper_prefix = request.POST.get("add_insper_prefix") == "on"
        sync_config.include_teacher_in_description = (
            request.POST.get("include_teacher_in_description") == "on"
        )
        sync_config.include_discipline_code = (
            request.POST.get("include_discipline_code") == "on"
        )

        # Filtros de evento (se fornecidos)
        excluded_event_types = request.POST.get("excluded_event_types", "").split(",")
        excluded_event_types = [t.strip() for t in excluded_event_types if t.strip()]
        sync_config.excluded_event_types = excluded_event_types

        excluded_disciplines = request.POST.get("excluded_disciplines", "").split(",")
        excluded_disciplines = [d.strip() for d in excluded_disciplines if d.strip()]
        sync_config.excluded_disciplines = excluded_disciplines

        sync_config.save()

        messages.success(
            request, "Configurações de sincronização atualizadas com sucesso!"
        )
        return redirect("sync_configuration")

    context = {
        "sync_config": sync_config,
        "excluded_event_types_str": ", ".join(sync_config.excluded_event_types),
        "excluded_disciplines_str": ", ".join(sync_config.excluded_disciplines),
    }

    return render(request, "sync/configuration.html", context)


@login_required
@require_POST
def manual_sync(request):
    """View para iniciar sincronização manual"""
    if not request.user.can_sync():
        messages.error(
            request,
            "Você não pode sincronizar. Verifique se seu email está verificado, "
            "credenciais do Insper configuradas e Google Calendar conectado.",
        )
        return redirect("dashboard")

    # Verifica se já há uma sincronização em andamento
    running_sessions = SyncSession.objects.filter(
        user=request.user,
        status="running",
        started_at__gte=timezone.now() - timezone.timedelta(minutes=30),
    )

    if running_sessions.exists():
        messages.warning(
            request, "Já há uma sincronização em andamento. Aguarde a conclusão."
        )
        return redirect("dashboard")

    # Obtém parâmetros opcionais
    start_date = request.POST.get("start_date")
    end_date = request.POST.get("end_date")

    try:
        # Inicia task de sincronização
        task_result = sync_user_calendar.delay(request.user.id, start_date, end_date)

        messages.success(
            request,
            "Sincronização iniciada com sucesso! "
            "Você pode acompanhar o progresso no dashboard.",
        )

        # Armazena ID da task na sessão para acompanhamento
        request.session["current_sync_task_id"] = task_result.id

    except Exception as e:
        messages.error(request, f"Erro ao iniciar sincronização: {str(e)}")

    return redirect("dashboard")


@login_required
def sync_status(request):
    """API endpoint para verificar status da sincronização"""
    # Busca sessões recentes do usuário
    recent_sessions = SyncSession.objects.filter(user=request.user).order_by(
        "-started_at"
    )[:5]

    # Informações sobre a sessão mais recente
    latest_session = recent_sessions.first() if recent_sessions else None

    # Verifica se há task em execução
    task_id = request.session.get("current_sync_task_id")
    task_status = None

    if task_id:
        try:
            from celery.result import AsyncResult

            task_result = AsyncResult(task_id)
            task_status = {
                "id": task_id,
                "status": task_result.status,
                "ready": task_result.ready(),
                "successful": task_result.successful() if task_result.ready() else None,
                "result": str(task_result.result) if task_result.ready() else None,
            }

            # Remove task ID da sessão se concluída
            if task_result.ready():
                request.session.pop("current_sync_task_id", None)

        except Exception:
            task_status = None

    data = {
        "latest_session": {
            "id": latest_session.pk if latest_session else None,
            "status": latest_session.status if latest_session else None,
            "started_at": latest_session.started_at.isoformat()
            if latest_session
            else None,
            "completed_at": latest_session.completed_at.isoformat()
            if latest_session and latest_session.completed_at
            else None,
            "events_created": latest_session.events_created if latest_session else 0,
            "events_updated": latest_session.events_updated if latest_session else 0,
            "events_deleted": latest_session.events_deleted if latest_session else 0,
            "events_failed": latest_session.events_failed if latest_session else 0,
            "error_message": latest_session.error_message if latest_session else None,
        },
        "task_status": task_status,
        "can_sync": request.user.can_sync(),
        "last_sync": request.user.last_sync.isoformat()
        if request.user.last_sync
        else None,
    }

    return JsonResponse(data)


@method_decorator(login_required, name="dispatch")
class SyncHistoryView(ListView):
    """View para mostrar histórico de sincronizações"""

    model = SyncSession
    template_name = "sync/history.html"
    context_object_name = "sync_sessions"
    paginate_by = 20

    def get_queryset(self):
        return SyncSession.objects.filter(user=self.request.user).order_by(
            "-started_at"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Estatísticas gerais
        sessions = self.get_queryset()
        context["total_sessions"] = sessions.count()
        context["successful_sessions"] = sessions.filter(status="completed").count()
        context["failed_sessions"] = sessions.filter(status="failed").count()

        # Última sincronização bem-sucedida
        last_successful = sessions.filter(status="completed").first()
        context["last_successful_sync"] = last_successful

        return context


@login_required
def sync_session_detail(request, session_id):
    """View para detalhes de uma sessão de sincronização"""
    session = get_object_or_404(SyncSession, id=session_id, user=request.user)

    # Busca mapeamentos de eventos desta sessão
    event_mappings = session.event_mappings.select_related(  # type: ignore
        "insper_event", "google_event"
    ).order_by("-created_at")

    context = {
        "session": session,
        "event_mappings": event_mappings,
        "duration": session.duration(),
    }

    return render(request, "sync/session_detail.html", context)


@login_required
@require_POST
def clear_sync_history(request):
    """View para limpar histórico de sincronizações"""
    # Remove sessões antigas (mantém as 10 mais recentes)
    sessions_to_keep = (
        SyncSession.objects.filter(user=request.user)
        .order_by("-started_at")[:10]
        .values_list("id", flat=True)
    )

    deleted_count = (
        SyncSession.objects.filter(user=request.user)
        .exclude(id__in=sessions_to_keep)
        .delete()[0]
    )

    if deleted_count > 0:
        messages.success(
            request,
            f"Histórico limpo com sucesso! {deleted_count} sessões antigas removidas.",
        )
    else:
        messages.info(request, "Não há sessões antigas para remover.")

    return redirect("sync_history")


@login_required
@require_POST
def reset_sync_data(request):
    """View para resetar todos os dados de sincronização (CUIDADO!)"""
    if request.POST.get("confirm") != "RESET":
        messages.error(
            request, 'Confirmação inválida. Digite "RESET" para confirmar a operação.'
        )
        return redirect("sync_configuration")

    try:
        # Remove todos os dados de sincronização do usuário
        from .models import EventMapping, GoogleEvent, InsperEvent

        EventMapping.objects.filter(insper_event__user=request.user).delete()

        GoogleEvent.objects.filter(user=request.user).delete()
        InsperEvent.objects.filter(user=request.user).delete()
        SyncSession.objects.filter(user=request.user).delete()

        # Reset da última sincronização
        request.user.last_sync = None
        request.user.save(update_fields=["last_sync"])

        messages.success(
            request,
            "Todos os dados de sincronização foram removidos com sucesso! "
            "Você pode iniciar uma nova sincronização a qualquer momento.",
        )

    except Exception as e:
        messages.error(request, f"Erro ao resetar dados: {str(e)}")

    return redirect("dashboard")
