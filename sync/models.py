import hashlib
import json
from typing import Dict

from django.conf import settings
from django.db import models
from django.utils import timezone


class SyncSession(models.Model):
    """Sessão de sincronização - rastreia cada execução do processo de sync"""

    STATUS_CHOICES = [
        ("running", "Em Execução"),
        ("completed", "Concluída"),
        ("failed", "Falhou"),
        ("partial", "Parcialmente Concluída"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sync_sessions"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="running")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Período sincronizado
    sync_start_date = models.DateField(help_text="Data inicial do período sincronizado")
    sync_end_date = models.DateField(help_text="Data final do período sincronizado")

    # Estatísticas
    insper_events_found = models.IntegerField(default=0)
    google_events_found = models.IntegerField(default=0)
    events_created = models.IntegerField(default=0)
    events_updated = models.IntegerField(default=0)
    events_deleted = models.IntegerField(default=0)
    events_failed = models.IntegerField(default=0)

    # Logs de erro
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["user", "-started_at"]),
            models.Index(fields=["status", "-started_at"]),
        ]

    def __str__(self):
        return f"Sync {self.user.email} - {self.started_at.strftime('%d/%m/%Y %H:%M')} ({self.status})"

    def duration(self):
        """Retorna a duração da sincronização"""
        if self.completed_at and self.started_at:
            return self.completed_at - self.started_at
        elif self.started_at:
            return timezone.now() - self.started_at
        return None

    def mark_completed(self):
        """Marca a sessão como concluída"""
        self.status = "completed"
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at"])

    def mark_failed(self, error_message: str, error_details: Dict | None = None):
        """Marca a sessão como falhada"""
        self.status = "failed"
        self.completed_at = timezone.now()
        self.error_message = error_message
        if error_details:
            self.error_details = error_details
        self.save(
            update_fields=["status", "completed_at", "error_message", "error_details"]
        )


class InsperEvent(models.Model):
    """Evento do calendário do Insper"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="insper_events"
    )

    # IDs únicos
    insper_event_id = models.CharField(
        max_length=255, help_text="ID único do evento no Insper"
    )
    insper_internal_id = models.CharField(
        max_length=255, blank=True, help_text="ID interno do sistema Insper"
    )

    # Dados básicos do evento
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    all_day = models.BooleanField(default=False)

    # Dados específicos do Insper
    disciplina_codigo = models.CharField(max_length=200, blank=True)
    docente = models.CharField(max_length=200, blank=True)
    turma = models.CharField(max_length=100, blank=True)
    dependencia = models.CharField(max_length=200, blank=True)
    tipo_evento = models.CharField(max_length=100, blank=True)

    # Dados técnicos
    timezone = models.CharField(max_length=50, default="America/Sao_Paulo")
    raw_data = models.JSONField(help_text="Dados brutos do evento do Insper")
    content_hash = models.CharField(
        max_length=64, help_text="Hash MD5 do conteúdo para detectar mudanças"
    )

    # Metadados
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(
        default=True, help_text="Se o evento ainda existe no Insper"
    )

    class Meta:
        unique_together = ["user", "insper_event_id"]
        indexes = [
            models.Index(fields=["user", "start_datetime"]),
            models.Index(fields=["user", "insper_event_id"]),
            models.Index(fields=["content_hash"]),
            models.Index(fields=["is_active", "user"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.start_datetime.strftime('%d/%m/%Y %H:%M')}"

    def calculate_content_hash(self) -> str:
        """Calcula hash do conteúdo do evento para detectar mudanças"""
        content = {
            "title": self.title,
            "description": self.description,
            "start_datetime": self.start_datetime.isoformat(),
            "end_datetime": self.end_datetime.isoformat(),
            "all_day": self.all_day,
            "disciplina_codigo": self.disciplina_codigo,
            "docente": self.docente,
            "turma": self.turma,
            "tipo_evento": self.tipo_evento,
        }
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.md5(content_str.encode()).hexdigest()

    def has_content_changed(self) -> bool:
        """Verifica se o conteúdo do evento mudou"""
        current_hash = self.calculate_content_hash()
        return current_hash != self.content_hash

    def update_content_hash(self):
        """Atualiza o hash do conteúdo"""
        self.content_hash = self.calculate_content_hash()

    def save(self, *args, **kwargs):
        # Sempre atualiza o hash antes de salvar
        self.update_content_hash()
        super().save(*args, **kwargs)


class GoogleEvent(models.Model):
    """Evento do Google Calendar"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="google_events"
    )

    # IDs únicos
    google_event_id = models.CharField(
        max_length=255, help_text="ID único do evento no Google Calendar"
    )
    google_calendar_id = models.CharField(
        max_length=255, help_text="ID do calendário no Google"
    )

    # Dados básicos do evento
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    all_day = models.BooleanField(default=False)

    # Dados específicos do Google
    location = models.CharField(max_length=500, blank=True)
    html_link = models.URLField(blank=True)

    # Dados técnicos
    timezone = models.CharField(max_length=50, default="America/Sao_Paulo")
    raw_data = models.JSONField(help_text="Dados brutos do evento do Google")
    content_hash = models.CharField(
        max_length=64, help_text="Hash MD5 do conteúdo para detectar mudanças"
    )

    # Metadados
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(
        default=True, help_text="Se o evento ainda existe no Google"
    )

    # Origem da sincronização
    synced_from_insper = models.BooleanField(
        default=False, help_text="Se foi criado a partir de evento do Insper"
    )

    class Meta:
        unique_together = ["user", "google_event_id"]
        indexes = [
            models.Index(fields=["user", "start_datetime"]),
            models.Index(fields=["user", "google_event_id"]),
            models.Index(fields=["content_hash"]),
            models.Index(fields=["is_active", "user"]),
            models.Index(fields=["synced_from_insper"]),
        ]

    def __str__(self):
        return (
            f"{self.title} - {self.start_datetime.strftime('%d/%m/%Y %H:%M')} (Google)"
        )

    def calculate_content_hash(self) -> str:
        """Calcula hash do conteúdo do evento para detectar mudanças"""
        content = {
            "title": self.title,
            "description": self.description,
            "start_datetime": self.start_datetime.isoformat(),
            "end_datetime": self.end_datetime.isoformat(),
            "all_day": self.all_day,
            "location": self.location,
        }
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.md5(content_str.encode()).hexdigest()

    def has_content_changed(self) -> bool:
        """Verifica se o conteúdo do evento mudou"""
        current_hash = self.calculate_content_hash()
        return current_hash != self.content_hash

    def update_content_hash(self):
        """Atualiza o hash do conteúdo"""
        self.content_hash = self.calculate_content_hash()

    def save(self, *args, **kwargs):
        # Sempre atualiza o hash antes de salvar
        self.update_content_hash()
        super().save(*args, **kwargs)


class EventMapping(models.Model):
    """Mapeamento entre eventos do Insper e Google Calendar"""

    SYNC_STATUS_CHOICES = [
        ("synced", "Sincronizado"),
        ("pending", "Pendente"),
        ("failed", "Falhou"),
        ("conflict", "Conflito"),
        ("deleted", "Deletado"),
    ]

    DIRECTION_CHOICES = [
        ("insper_to_google", "Insper → Google"),
        ("google_to_insper", "Google → Insper"),
        ("bidirectional", "Bidirecional"),
    ]

    # Relacionamentos
    insper_event = models.ForeignKey(
        InsperEvent, on_delete=models.CASCADE, related_name="mappings"
    )
    google_event = models.ForeignKey(
        GoogleEvent, on_delete=models.CASCADE, related_name="mappings"
    )
    sync_session = models.ForeignKey(
        SyncSession, on_delete=models.CASCADE, related_name="event_mappings"
    )

    # Status da sincronização
    status = models.CharField(
        max_length=20, choices=SYNC_STATUS_CHOICES, default="pending"
    )
    direction = models.CharField(
        max_length=20, choices=DIRECTION_CHOICES, default="insper_to_google"
    )

    # Metadados
    created_at = models.DateTimeField(auto_now_add=True)
    last_synced_at = models.DateTimeField(auto_now=True)
    error_message = models.TextField(blank=True)

    # Controle de conflitos
    needs_manual_review = models.BooleanField(default=False)
    review_notes = models.TextField(blank=True)

    class Meta:
        unique_together = ["insper_event", "google_event"]
        indexes = [
            models.Index(fields=["status", "-last_synced_at"]),
            models.Index(fields=["sync_session", "status"]),
            models.Index(fields=["needs_manual_review"]),
        ]

    def __str__(self):
        return f"Mapping: {self.insper_event.title} ↔ {self.google_event.title} ({self.status})"

    def mark_synced(self):
        """Marca o mapeamento como sincronizado com sucesso"""
        self.status = "synced"
        self.error_message = ""
        self.save(update_fields=["status", "error_message", "last_synced_at"])

    def mark_failed(self, error_message: str):
        """Marca o mapeamento como falhado"""
        self.status = "failed"
        self.error_message = error_message
        self.save(update_fields=["status", "error_message", "last_synced_at"])

    def mark_conflict(self, review_notes: str = ""):
        """Marca o mapeamento como em conflito"""
        self.status = "conflict"
        self.needs_manual_review = True
        self.review_notes = review_notes
        self.save(
            update_fields=[
                "status",
                "needs_manual_review",
                "review_notes",
                "last_synced_at",
            ]
        )


class SyncConfiguration(models.Model):
    """Configurações de sincronização por usuário"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sync_config"
    )

    # Configurações de sincronização
    sync_enabled = models.BooleanField(default=True)
    sync_frequency_hours = models.IntegerField(
        default=6, help_text="Frequência de sincronização em horas"
    )

    # Filtros de sincronização
    sync_all_events = models.BooleanField(default=True)
    excluded_event_types = models.JSONField(
        default=list, blank=True, help_text="Tipos de evento para excluir"
    )
    excluded_disciplines = models.JSONField(
        default=list, blank=True, help_text="Disciplinas para excluir"
    )

    # Configurações do Google Calendar
    google_calendar_name = models.CharField(
        max_length=255, default="Insper - Calendário Acadêmico"
    )
    add_insper_prefix = models.BooleanField(
        default=True, help_text="Adicionar '[Insper]' no título dos eventos"
    )
    include_teacher_in_description = models.BooleanField(default=True)
    include_discipline_code = models.BooleanField(default=True)

    # Metadados
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_sync_attempt = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["sync_enabled", "last_sync_attempt"]),
        ]

    def __str__(self):
        return f"Config de Sync: {self.user.email} ({'Ativo' if self.sync_enabled else 'Inativo'})"

    def should_sync_event_type(self, event_type: str) -> bool:
        """Verifica se um tipo de evento deve ser sincronizado"""
        if not self.sync_all_events:
            return event_type not in self.excluded_event_types
        return True

    def should_sync_discipline(self, discipline_code: str) -> bool:
        """Verifica se uma disciplina deve ser sincronizada"""
        if not self.sync_all_events:
            return discipline_code not in self.excluded_disciplines
        return True
