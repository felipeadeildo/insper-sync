import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from core.google_calendar import GoogleCalendarClient, get_or_refresh_access_token
from core.insper import InsperAuth, InsperCalendar
from core.insper import InsperEvent as InsperEventSrc

from .models import (
    EventMapping,
    GoogleEvent,
    InsperEvent,
    SyncConfiguration,
    SyncSession,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def sync_user_calendar(
    self, user_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None
):
    """
    Task principal para sincronizar calendário de um usuário

    Args:
        user_id: ID do usuário
        start_date: Data inicial (formato YYYY-MM-DD, opcional)
        end_date: Data final (formato YYYY-MM-DD, opcional)
    """
    try:
        # Busca o usuário
        user = User.objects.get(id=user_id)

        # Verifica se o usuário pode sincronizar
        if not user.can_sync():
            return (
                f"Usuário {user.email} não pode sincronizar (configurações incompletas)"
            )

        # Define datas padrão (próximo mês se não especificado)
        if not start_date or not end_date:
            now = timezone.now()
            default_start = now.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            if now.month == 12:
                default_end = default_start.replace(
                    year=now.year + 1, month=1
                ) + timedelta(days=31)
            else:
                default_end = default_start.replace(month=now.month + 1) + timedelta(
                    days=31
                )

            start_date = start_date or default_start.date().isoformat()
            end_date = end_date or default_end.date().isoformat()

        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)

        # Obtém ou cria configuração de sincronização
        sync_config, _ = SyncConfiguration.objects.get_or_create(
            user=user,
            defaults={"sync_enabled": True, "google_calendar_name": "Insper Sync"},
        )

        if not sync_config.sync_enabled:
            return f"Sincronização desabilitada para {user.email}"

        # Cria sessão de sincronização
        sync_session = SyncSession.objects.create(
            user=user,
            sync_start_date=start_dt.date(),
            sync_end_date=end_dt.date(),
            status="running",
        )

        try:
            # Executa a sincronização
            result = _perform_sync(user, sync_config, sync_session, start_dt, end_dt)

            # Marca sessão como concluída
            sync_session.mark_completed()

            # Atualiza última sincronização do usuário
            user.last_sync = timezone.now()
            user.save(update_fields=["last_sync"])

            return result

        except Exception as e:
            # Marca sessão como falhada
            sync_session.mark_failed(str(e))
            raise

    except User.DoesNotExist:
        return f"Usuário com ID {user_id} não encontrado"
    except Exception as e:
        logger.error(f"Erro na sincronização do usuário {user_id}: {str(e)}")

        # Retry logic
        if self.request.retries < self.max_retries:
            logger.info(
                f"Tentando novamente em 60 segundos (tentativa {self.request.retries + 1})"
            )
            raise self.retry(countdown=60, exc=e)
        else:
            return (
                f"Falha na sincronização após {self.max_retries} tentativas: {str(e)}"
            )


def _perform_sync(
    user: User,
    sync_config: SyncConfiguration,
    sync_session: SyncSession,
    start_dt: datetime,
    end_dt: datetime,
) -> str:
    """
    Executa o processo de sincronização

    Args:
        user: Usuário
        sync_config: Configuração de sincronização
        sync_session: Sessão de sincronização
        start_dt: Data de início
        end_dt: Data de fim

    Returns:
        Mensagem de resultado
    """

    # Passo 1: Buscar eventos do Insper
    logger.info(f"Buscando eventos do Insper para {user.email}")
    insper_events = _fetch_insper_events(user, start_dt, end_dt)
    sync_session.insper_events_found = len(insper_events)
    sync_session.save(update_fields=["insper_events_found"])

    # Passo 2: Configurar Google Calendar
    logger.info(f"Configurando Google Calendar para {user.email}")
    google_calendar_id = _setup_google_calendar(user, sync_config)

    # Passo 3: Buscar eventos existentes do Google
    logger.info(f"Buscando eventos do Google para {user.email}")
    google_events = _fetch_google_events(user, google_calendar_id, start_dt, end_dt)
    sync_session.google_events_found = len(google_events)
    sync_session.save(update_fields=["google_events_found"])

    # Passo 4: Sincronizar eventos
    logger.info(f"Sincronizando eventos para {user.email}")
    sync_stats = _synchronize_events(
        user,
        sync_config,
        sync_session,
        google_calendar_id,
        insper_events,
        google_events,
    )

    # Atualiza estatísticas da sessão
    sync_session.events_created = sync_stats["created"]
    sync_session.events_updated = sync_stats["updated"]
    sync_session.events_deleted = sync_stats["deleted"]
    sync_session.events_failed = sync_stats["failed"]
    sync_session.save(
        update_fields=[
            "events_created",
            "events_updated",
            "events_deleted",
            "events_failed",
        ]
    )

    return (
        f"Sincronização concluída para {user.email}: "
        f"{sync_stats['created']} criados, "
        f"{sync_stats['updated']} atualizados, "
        f"{sync_stats['deleted']} removidos, "
        f"{sync_stats['failed']} falharam"
    )


def _fetch_insper_events(
    user: User, start_dt: datetime, end_dt: datetime
) -> List[InsperEvent]:
    """
    Busca eventos do calendário do Insper e salva/atualiza no banco,
    retornando objetos InsperEvent (model Django)

    Args:
        user: Usuário
        start_dt: Data de início
        end_dt: Data de fim

    Returns:
        Lista de objetos InsperEvent
    """
    try:
        from core.insper import InsperEvent as InsperEventSrc

        with InsperAuth() as auth:
            # Faz login no Insper
            success = auth.login(
                user.insper_username, user.insper_enc_password, encrypt=False
            )
            if not success:
                raise Exception("Falha na autenticação com o Insper")

            # Busca eventos
            calendar = InsperCalendar(auth)
            events: List[InsperEventSrc] = calendar.get_events_for_range(
                start_dt, end_dt
            )

            # Salva/atualiza todos no banco e retorna objetos
            insper_event_objs = []
            for event in events:
                # Converte para dict e salva usando função já existente
                event_dict = _convert_insper_event_to_dict(event)
                insper_event_obj = _save_insper_event(user, event_dict)
                insper_event_objs.append(insper_event_obj)
            return insper_event_objs

    except Exception as e:
        logger.error(f"Erro ao buscar eventos do Insper: {str(e)}")
        raise


def _convert_insper_event_to_dict(insper_event: InsperEventSrc) -> Dict:
    """
    Converte evento do Insper para dicionário padrão

    Args:
        insper_event: Evento do Insper

    Returns:
        Dicionário com dados do evento
    """
    from django.utils import timezone

    start_dt = insper_event.start_datetime
    end_dt = insper_event.end_datetime

    # Make timezone-aware if naive
    if start_dt and timezone.is_naive(start_dt):
        start_dt = timezone.make_aware(start_dt)
    if end_dt and timezone.is_naive(end_dt):
        end_dt = timezone.make_aware(end_dt)

    return {
        "id": insper_event.event_id,
        "internal_id": insper_event.id or f"insper-{insper_event.event_id}",
        "title": insper_event.title,
        "description": insper_event.descricao,
        "start_datetime": start_dt,
        "end_datetime": end_dt,
        "all_day": insper_event.all_day,
        "disciplina_codigo": insper_event.disciplina_codigo,
        "docente": insper_event.docente,
        "turma": insper_event.turma,
        "dependencia": insper_event.dependencia,
        "tipo_evento": insper_event.tipo_evento,
        "timezone": insper_event.time_zone,
        "raw_data": {
            "title": insper_event.title,
            "startStr": insper_event.start_str,
            "endStr": insper_event.end_str,
            "startDate": insper_event.start_date,
            "endDate": insper_event.end_date,
            "timeZone": insper_event.time_zone,
            "descricao": insper_event.descricao,
            "icone": insper_event.icone,
            "eventId": insper_event.event_id,
            "tipoEvento": insper_event.tipo_evento,
            "hoverInfo": insper_event.hover_info,
            "className": insper_event.class_name,
        },
    }


def _setup_google_calendar(user: User, sync_config: SyncConfiguration) -> str:
    """
    Configura calendário do Google (cria se necessário)

    Args:
        user: Usuário
        sync_config: Configuração de sincronização

    Returns:
        ID do calendário
    """
    # Obtém token válido
    success, access_token, error = get_or_refresh_access_token(user)
    if not success or not access_token:
        raise Exception(f"Erro ao obter token do Google: {error}")

    # Cria cliente do Google Calendar
    client = GoogleCalendarClient(access_token)

    # Obtém ou cria calendário do Insper Sync
    success, calendar_id, error = client.get_or_create_insper_calendar(
        sync_config.google_calendar_name
    )

    if not success or not calendar_id:
        raise Exception(f"Erro ao configurar calendário: {error}")

    # Atualiza ID do calendário no usuário se mudou
    if user.google_calendar_id != calendar_id:
        user.google_calendar_id = calendar_id
        user.save(update_fields=["google_calendar_id"])

    return calendar_id


def _fetch_google_events(
    user: User, calendar_id: str, start_dt: datetime, end_dt: datetime
) -> List[GoogleEvent]:
    """
    Busca eventos existentes do Google Calendar e salva/atualiza no banco,
    retornando objetos GoogleEvent (model Django)

    Args:
        user: Usuário
        calendar_id: ID do calendário
        start_dt: Data de início
        end_dt: Data de fim

    Returns:
        Lista de objetos GoogleEvent
    """
    # Obtém token válido
    success, access_token, error = get_or_refresh_access_token(user)
    if not success or not access_token:
        raise Exception(f"Erro ao obter token do Google: {error}")

    # Busca eventos
    client = GoogleCalendarClient(access_token)
    success, events, error = client.list_events(
        calendar_id=calendar_id, time_min=start_dt, time_max=end_dt, max_results=2500
    )

    if not success:
        raise Exception(f"Erro ao buscar eventos do Google: {error}")

    # Filtra apenas eventos criados pelo Insper Sync e salva/atualiza no banco
    google_event_objs = []
    for event in events or []:
        extended_props = event.get("extendedProperties", {}).get("private", {})
        if extended_props.get("sync_source") == "insper":
            google_event_obj = _save_google_event(user, event)
            google_event_objs.append(google_event_obj)

    return google_event_objs


def _synchronize_events(
    user: User,
    sync_config: SyncConfiguration,
    sync_session: SyncSession,
    google_calendar_id: str,
    insper_events: List[InsperEvent],
    google_events: List[GoogleEvent],
) -> Dict[str, int]:
    """
    Sincroniza eventos entre Insper e Google

    Args:
        user: Usuário
        sync_config: Configuração de sincronização
        sync_session: Sessão de sincronização
        google_calendar_id: ID do calendário do Google
        insper_events: Eventos do Insper
        google_events: Eventos do Google

    Returns:
        Estatísticas de sincronização
    """
    stats = {"created": 0, "updated": 0, "deleted": 0, "failed": 0}

    # Obtém token válido
    success, access_token, error = get_or_refresh_access_token(user)
    if not success or not access_token:
        raise Exception(f"Erro ao obter token do Google: {error}")

    client = GoogleCalendarClient(access_token)

    # Cria mapeamento de eventos existentes
    google_events_map = {}
    for event in google_events:
        ext_props = event.raw_data.get("extendedProperties", {})
        private = ext_props.get("private", {})
        insper_event_id = private.get("insper_event_id", "")
        if insper_event_id:
            google_events_map[insper_event_id] = event

    # Processa eventos do Insper
    for insper_event in insper_events:
        try:
            if not _should_sync_event(insper_event, sync_config):
                continue
            insper_event_id = insper_event.insper_event_id
            existing_google_event = google_events_map.get(insper_event_id)
            if existing_google_event:
                if _event_needs_update(
                    insper_event, existing_google_event, sync_config
                ):
                    success = _update_google_event(
                        client,
                        google_calendar_id,
                        existing_google_event,
                        insper_event,
                        sync_config,
                    )
                    if success:
                        stats["updated"] += 1
                        _create_event_mapping(
                            sync_session, insper_event, existing_google_event, "synced"
                        )
                    else:
                        stats["failed"] += 1
            else:
                google_event = _create_google_event(
                    client, google_calendar_id, insper_event, sync_config
                )
                if google_event:
                    stats["created"] += 1
                    google_event_obj = _save_google_event(user, google_event)
                    _create_event_mapping(
                        sync_session, insper_event, google_event_obj, "synced"
                    )
                else:
                    stats["failed"] += 1
        except Exception as e:
            logger.error(
                f"Erro ao processar evento {getattr(insper_event, 'insper_event_id', 'unknown')}: {str(e)}"
            )
            stats["failed"] += 1

    # Remove eventos que não existem mais no Insper
    insper_event_ids = {event.insper_event_id for event in insper_events}
    for google_event in google_events:
        ext_props = google_event.raw_data.get("extendedProperties", {})
        private = ext_props.get("private", {})
        google_insper_id = private.get("insper_event_id", "")
        if google_insper_id and google_insper_id not in insper_event_ids:
            success, error = client.delete_event(
                google_calendar_id, google_event.google_event_id
            )
            if success:
                stats["deleted"] += 1
                GoogleEvent.objects.filter(
                    user=user, google_event_id=google_event.google_event_id
                ).update(is_active=False)
            else:
                logger.error(
                    f"Erro ao deletar evento {google_event.google_event_id}: {error}"
                )
    return stats


def _should_sync_event(
    insper_event: InsperEvent, sync_config: SyncConfiguration
) -> bool:
    """
    Verifica se um evento deve ser sincronizado baseado nas configurações

    Args:
        insper_event: Evento do Insper (objeto model)
        sync_config: Configuração de sincronização

    Returns:
        True se deve sincronizar
    """
    # Verifica tipo de evento
    if not sync_config.should_sync_event_type(getattr(insper_event, "tipo_evento", "")):
        return False

    # Verifica disciplina
    disciplina = getattr(insper_event, "disciplina_codigo", "")
    if disciplina and not sync_config.should_sync_discipline(disciplina):
        return False

    return True


def _save_insper_event(user: User, event_data: Dict) -> InsperEvent:
    """
    Salva ou atualiza evento do Insper no banco de dados

    Args:
        user: Usuário
        event_data: Dados do evento

    Returns:
        Instância do InsperEvent
    """
    from django.utils import timezone

    # Ensure datetime fields are timezone-aware
    start_dt = event_data["start_datetime"]
    end_dt = event_data["end_datetime"]

    if start_dt and timezone.is_naive(start_dt):
        start_dt = timezone.make_aware(start_dt)
    if end_dt and timezone.is_naive(end_dt):
        end_dt = timezone.make_aware(end_dt)

    insper_internal_id = event_data.get("internal_id") or f"auto-{event_data['id']}"

    with transaction.atomic():
        insper_event, created = InsperEvent.objects.get_or_create(
            user=user,
            insper_event_id=event_data["id"],
            defaults={
                "insper_internal_id": insper_internal_id,
                "title": event_data["title"],
                "description": event_data.get("description", ""),
                "start_datetime": start_dt,
                "end_datetime": end_dt,
                "all_day": event_data.get("all_day", False),
                "disciplina_codigo": event_data.get("disciplina_codigo", ""),
                "docente": event_data.get("docente", ""),
                "turma": event_data.get("turma", ""),
                "dependencia": event_data.get("dependencia", ""),
                "tipo_evento": event_data.get("tipo_evento", ""),
                "timezone": event_data.get("timezone", "America/Sao_Paulo"),
                "raw_data": event_data.get("raw_data", {}),
                "is_active": True,
                "last_synced_at": timezone.now(),
            },
        )

        # Se não foi criado, atualiza os campos
        if not created:
            fields_to_update = []

            if insper_event.title != event_data["title"]:
                insper_event.title = event_data["title"]
                fields_to_update.append("title")

            if insper_event.description != event_data.get("description", ""):
                insper_event.description = event_data.get("description", "")
                fields_to_update.append("description")

            if insper_event.start_datetime != start_dt:
                insper_event.start_datetime = start_dt
                fields_to_update.append("start_datetime")

            if insper_event.end_datetime != end_dt:
                insper_event.end_datetime = end_dt
                fields_to_update.append("end_datetime")

            # Atualiza outros campos conforme necessário
            insper_event.docente = event_data.get("docente", "")
            insper_event.turma = event_data.get("turma", "")
            insper_event.dependencia = event_data.get("dependencia", "")
            insper_event.is_active = True
            insper_event.last_synced_at = timezone.now()

            fields_to_update.extend(
                ["docente", "turma", "dependencia", "is_active", "last_synced_at"]
            )

            if fields_to_update:
                insper_event.save(update_fields=fields_to_update)

        return insper_event


def _event_needs_update(
    insper_event: InsperEvent, google_event: Dict, sync_config: SyncConfiguration
) -> bool:
    """
    Verifica se um evento do Google precisa ser atualizado

    Args:
        insper_event: Evento do Insper (objeto model)
        google_event: Dados do evento do Google
        sync_config: Configuração de sincronização

    Returns:
        True se precisa atualizar
    """
    # Compara títulos
    expected_title = _format_event_title(insper_event, sync_config)
    if google_event.get("summary", "") != expected_title:
        return True

    # Compara descrições
    expected_description = _format_event_description(insper_event, sync_config)
    if google_event.get("description", "") != expected_description:
        return True

    # Compara datas
    google_start = google_event.get("start", {})
    google_end = google_event.get("end", {})

    if google_start.get("dateTime"):
        google_start_dt = datetime.fromisoformat(
            google_start["dateTime"].replace("Z", "+00:00")
        )
        if google_start_dt != insper_event.start_datetime:
            return True

    if google_end.get("dateTime"):
        google_end_dt = datetime.fromisoformat(
            google_end["dateTime"].replace("Z", "+00:00")
        )
        if google_end_dt != insper_event.end_datetime:
            return True

    return False


def _create_google_event(
    client: GoogleCalendarClient,
    calendar_id: str,
    insper_event: InsperEvent,
    sync_config: SyncConfiguration,
) -> Optional[Dict]:
    """
    Cria evento no Google Calendar

    Args:
        client: Cliente do Google Calendar
        calendar_id: ID do calendário
        insper_event: Evento do Insper (objeto model)
        sync_config: Configuração de sincronização

    Returns:
        Dados do evento criado ou None se falhou
    """
    try:
        event_data = {
            "summary": _format_event_title(insper_event, sync_config),
            "description": _format_event_description(insper_event, sync_config),
            "start": {
                "dateTime": insper_event.start_datetime.isoformat(),
                "timeZone": "America/Sao_Paulo",
            },
            "end": {
                "dateTime": insper_event.end_datetime.isoformat(),
                "timeZone": "America/Sao_Paulo",
            },
            "location": insper_event.dependencia or "",
            "source": {
                "title": "Insper Sync",
                "url": "https://sync.insper.dev",
            },
            "extendedProperties": {
                "private": {
                    "insper_event_id": insper_event.insper_event_id,
                    "sync_source": "insper",
                    "disciplina_codigo": insper_event.disciplina_codigo or "",
                    "docente": insper_event.docente or "",
                    "turma": insper_event.turma or "",
                }
            },
        }

        success, google_event, error = client.create_event(calendar_id, event_data)

        if success and google_event:
            return google_event
        else:
            logger.error(f"Erro ao criar evento no Google: {error}")
            return None

    except Exception as e:
        logger.error(f"Erro ao criar evento no Google: {str(e)}")
        return None


def _update_google_event(
    client: GoogleCalendarClient,
    calendar_id: str,
    google_event: Dict,
    insper_event: InsperEvent,
    sync_config: SyncConfiguration,
) -> bool:
    """
    Atualiza evento no Google Calendar

    Args:
        client: Cliente do Google Calendar
        calendar_id: ID do calendário
        google_event: Evento existente do Google
        insper_event: Evento do Insper (objeto model)
        sync_config: Configuração de sincronização

    Returns:
        True se atualizou com sucesso
    """
    try:
        updated_data = {
            "summary": _format_event_title(insper_event, sync_config),
            "description": _format_event_description(insper_event, sync_config),
            "start": {
                "dateTime": insper_event.start_datetime.isoformat(),
                "timeZone": "America/Sao_Paulo",
            },
            "end": {
                "dateTime": insper_event.end_datetime.isoformat(),
                "timeZone": "America/Sao_Paulo",
            },
            "location": insper_event.dependencia or "",
            "extendedProperties": {
                "private": {
                    "insper_event_id": insper_event.insper_event_id,
                    "sync_source": "insper",
                    "disciplina_codigo": insper_event.disciplina_codigo or "",
                    "docente": insper_event.docente or "",
                    "turma": insper_event.turma or "",
                }
            },
        }

        success, _, error = client.update_event(
            calendar_id, google_event["id"], updated_data
        )

        if not success:
            logger.error(f"Erro ao atualizar evento no Google: {error}")

        return success

    except Exception as e:
        logger.error(f"Erro ao atualizar evento no Google: {str(e)}")
        return False


def _save_google_event(user: User, google_event: Dict) -> GoogleEvent:
    """
    Salva evento do Google no banco de dados

    Args:
        user: Usuário
        google_event: Dados do evento do Google

    Returns:
        Instância do GoogleEvent
    """
    start_dt = None
    end_dt = None

    # Parse das datas
    if google_event.get("start", {}).get("dateTime"):
        start_dt = datetime.fromisoformat(
            google_event["start"]["dateTime"].replace("Z", "+00:00")
        )
    if google_event.get("end", {}).get("dateTime"):
        end_dt = datetime.fromisoformat(
            google_event["end"]["dateTime"].replace("Z", "+00:00")
        )

    google_event_obj, created = GoogleEvent.objects.get_or_create(
        user=user,
        google_event_id=google_event["id"],
        defaults={
            "google_calendar_id": google_event.get("organizer", {}).get("email", ""),
            "title": google_event.get("summary", ""),
            "description": google_event.get("description", ""),
            "start_datetime": start_dt,
            "end_datetime": end_dt,
            "all_day": "date" in google_event.get("start", {}),
            "location": google_event.get("location", ""),
            "html_link": google_event.get("htmlLink", ""),
            "timezone": google_event.get("start", {}).get(
                "timeZone", "America/Sao_Paulo"
            ),
            "raw_data": google_event,
            "is_active": True,
            "synced_from_insper": True,
            "last_synced_at": timezone.now(),
        },
    )

    return google_event_obj


def _create_event_mapping(
    sync_session: SyncSession,
    insper_event: InsperEvent,
    google_event,
    status: str = "synced",
):
    """
    Cria mapeamento entre eventos do Insper e Google

    Args:
        sync_session: Sessão de sincronização
        insper_event: Evento do Insper
        google_event: Evento do Google (dict ou GoogleEvent)
        status: Status do mapeamento
    """
    try:
        # Se google_event é um dict, busca ou cria o GoogleEvent
        from .models import GoogleEvent as GoogleEventModel

        if isinstance(google_event, dict):
            google_event_obj, _ = GoogleEventModel.objects.get_or_create(
                user=insper_event.user, google_event_id=google_event["id"]
            )
        else:
            google_event_obj = google_event
        EventMapping.objects.get_or_create(
            insper_event=insper_event,
            google_event=google_event_obj,
            defaults={
                "sync_session": sync_session,
                "status": status,
                "direction": "insper_to_google",
            },
        )
    except Exception as e:
        logger.error(f"Erro ao criar mapeamento de evento: {str(e)}")


def _format_event_title(
    insper_event: InsperEvent, sync_config: SyncConfiguration
) -> str:
    """
    Formata título do evento conforme configurações

    Args:
        insper_event: Evento do Insper (objeto model)
        sync_config: Configuração de sincronização

    Returns:
        Título formatado
    """
    title = insper_event.title

    if sync_config.add_insper_prefix:
        title = f"[Insper] {title}"

    return title


def _format_event_description(
    insper_event: InsperEvent, sync_config: SyncConfiguration
) -> str:
    """
    Formata descrição do evento conforme configurações

    Args:
        insper_event: Evento do Insper (objeto model)
        sync_config: Configuração de sincronização

    Returns:
        Descrição formatada
    """
    description_parts = []

    # Descrição original
    if insper_event.description:
        description_parts.append(insper_event.description)

    # Informações adicionais conforme configuração
    if sync_config.include_discipline_code and insper_event.disciplina_codigo:
        description_parts.append(
            f"Código da disciplina: {insper_event.disciplina_codigo}"
        )

    if insper_event.docente:
        description_parts.append(f"Docente: {insper_event.docente}")

    if insper_event.turma:
        description_parts.append(f"Turma: {insper_event.turma}")

    if insper_event.dependencia:
        description_parts.append(f"Local: {insper_event.dependencia}")

    # Adiciona informações de sincronização
    description_parts.append("\n---")
    description_parts.append("Sincronizado automaticamente via Insper Sync")
    description_parts.append(
        f"Última atualização: {timezone.now().strftime('%d/%m/%Y %H:%M')}"
    )

    return "\n".join(description_parts)


@shared_task
def sync_all_users():
    """
    Task para sincronizar todos os usuários que podem ser sincronizados
    """
    users = User.objects.filter(
        email_verified=True,
        credentials_configured=True,
        google_connected=True,
        is_active=True,
    )

    results = []
    for user in users:
        try:
            # Verifica configuração de sincronização
            sync_config = getattr(user, "sync_config", None)
            if sync_config and sync_config.sync_enabled:
                result = sync_user_calendar.delay(user.pk)
                results.append(f"Sincronização iniciada para {user.email}: {result.id}")
            else:
                results.append(f"Sincronização desabilitada para {user.email}")
        except Exception as e:
            results.append(f"Erro ao iniciar sincronização para {user.email}: {str(e)}")

    return results


@shared_task
def cleanup_old_sync_sessions():
    """
    Task para limpar sessões de sincronização antigas (mais de 30 dias)
    """
    cutoff_date = timezone.now() - timedelta(days=30)

    deleted_count = SyncSession.objects.filter(started_at__lt=cutoff_date).delete()[0]

    return f"Removidas {deleted_count} sessões de sincronização antigas"
