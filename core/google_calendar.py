"""
Utilitários para integração com Google Calendar API
"""

import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import httpx
from django.conf import settings

from core.settings import DOMAIN

# Type aliases para melhor clareza
GoogleCalendarEvent = Dict[str, Any]
GoogleTokenData = Dict[str, Any]
GoogleCalendarInfo = Dict[str, Any]
APIResponse = Tuple[bool, Optional[Any], Optional[str]]


class GoogleCalendarClient:
    """Cliente para interação com Google Calendar API"""

    BASE_URL = "https://www.googleapis.com/calendar/v3"
    AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"

    def __init__(self, access_token: str | None = None):
        """
        Inicializa o cliente com token de acesso opcional

        Args:
            access_token: Token de acesso do Google (opcional)
        """
        self.access_token = access_token
        self.client = httpx.Client()

    def get_authorization_url(self, state: str | None = None) -> str:
        """
        Gera URL de autorização OAuth para Google Calendar

        Args:
            state: Estado opcional para validação CSRF

        Returns:
            URL de autorização
        """
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "scope": " ".join(settings.GOOGLE_CALENDAR_SCOPES),
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
        }

        if state:
            params["state"] = state

        return f"{self.AUTH_URL}?{urlencode(params)}"

    def exchange_code_for_tokens(
        self, code: str
    ) -> Tuple[bool, Optional[GoogleTokenData], Optional[str]]:
        """
        Troca código de autorização por tokens de acesso e refresh

        Args:
            code: Código de autorização retornado pelo Google

        Returns:
            Tupla (sucesso, dados_do_token, mensagem_de_erro)
        """
        try:
            response = self.client.post(
                self.TOKEN_URL,
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                },
            )

            if response.status_code == 200:
                return True, response.json(), None
            else:
                return False, None, f"Erro HTTP {response.status_code}: {response.text}"

        except Exception as e:
            return False, None, f"Erro ao trocar código por tokens: {str(e)}"

    def refresh_access_token(
        self, refresh_token: str
    ) -> Tuple[bool, Optional[GoogleTokenData], Optional[str]]:
        """
        Atualiza token de acesso usando refresh token

        Args:
            refresh_token: Token de refresh

        Returns:
            Tupla (sucesso, dados_do_token, mensagem_de_erro)
        """
        try:
            response = self.client.post(
                self.TOKEN_URL,
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )

            if response.status_code == 200:
                return True, response.json(), None
            else:
                return False, None, f"Erro HTTP {response.status_code}: {response.text}"

        except Exception as e:
            return False, None, f"Erro ao atualizar token: {str(e)}"

    def get_calendar_list(
        self,
    ) -> Tuple[bool, Optional[List[GoogleCalendarInfo]], Optional[str]]:
        """
        Lista calendários do usuário

        Returns:
            Tupla (sucesso, lista_de_calendários, mensagem_de_erro)
        """
        if not self.access_token:
            return False, None, "Token de acesso não fornecido"

        try:
            response = self.client.get(
                f"{self.BASE_URL}/users/me/calendarList",
                headers={"Authorization": f"Bearer {self.access_token}"},
            )

            if response.status_code == 200:
                data = response.json()
                return True, data.get("items", []), None
            else:
                return False, None, f"Erro HTTP {response.status_code}: {response.text}"

        except Exception as e:
            return False, None, f"Erro ao listar calendários: {str(e)}"

    def get_primary_calendar(
        self,
    ) -> Tuple[bool, Optional[GoogleCalendarInfo], Optional[str]]:
        """
        Obtém o calendário principal do usuário

        Returns:
            Tupla (sucesso, dados_do_calendário, mensagem_de_erro)
        """
        if not self.access_token:
            return False, None, "Token de acesso não fornecido"

        try:
            response = self.client.get(
                f"{self.BASE_URL}/calendars/primary",
                headers={"Authorization": f"Bearer {self.access_token}"},
            )

            if response.status_code == 200:
                return True, response.json(), None
            else:
                return False, None, f"Erro HTTP {response.status_code}: {response.text}"

        except Exception as e:
            return False, None, f"Erro ao obter calendário principal: {str(e)}"

    def create_event(
        self, calendar_id: str, event_data: GoogleCalendarEvent
    ) -> Tuple[bool, Optional[GoogleCalendarEvent], Optional[str]]:
        """
        Cria um evento no calendário

        Args:
            calendar_id: ID do calendário
            event_data: Dados do evento

        Returns:
            Tupla (sucesso, dados_do_evento, mensagem_de_erro)
        """
        if not self.access_token:
            return False, None, "Token de acesso não fornecido"

        try:
            response = self.client.post(
                f"{self.BASE_URL}/calendars/{calendar_id}/events",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json=event_data,
            )

            if response.status_code == 200:
                return True, response.json(), None
            else:
                return False, None, f"Erro HTTP {response.status_code}: {response.text}"

        except Exception as e:
            return False, None, f"Erro ao criar evento: {str(e)}"

    def update_event(
        self, calendar_id: str, event_id: str, event_data: GoogleCalendarEvent
    ) -> Tuple[bool, Optional[GoogleCalendarEvent], Optional[str]]:
        """
        Atualiza um evento no calendário

        Args:
            calendar_id: ID do calendário
            event_id: ID do evento
            event_data: Dados atualizados do evento

        Returns:
            Tupla (sucesso, dados_do_evento, mensagem_de_erro)
        """
        if not self.access_token:
            return False, None, "Token de acesso não fornecido"

        try:
            response = self.client.put(
                f"{self.BASE_URL}/calendars/{calendar_id}/events/{event_id}",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json=event_data,
            )

            if response.status_code == 200:
                return True, response.json(), None
            else:
                return False, None, f"Erro HTTP {response.status_code}: {response.text}"

        except Exception as e:
            return False, None, f"Erro ao atualizar evento: {str(e)}"

    def delete_event(
        self, calendar_id: str, event_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Remove um evento do calendário

        Args:
            calendar_id: ID do calendário
            event_id: ID do evento

        Returns:
            Tupla (sucesso, mensagem_de_erro)
        """
        if not self.access_token:
            return False, "Token de acesso não fornecido"

        try:
            response = self.client.delete(
                f"{self.BASE_URL}/calendars/{calendar_id}/events/{event_id}",
                headers={"Authorization": f"Bearer {self.access_token}"},
            )

            if response.status_code == 204:
                return True, None
            else:
                return False, f"Erro HTTP {response.status_code}: {response.text}"

        except Exception as e:
            return False, f"Erro ao remover evento: {str(e)}"

    def list_events(
        self,
        calendar_id: str,
        time_min: Optional[datetime.datetime] = None,
        time_max: Optional[datetime.datetime] = None,
        max_results: int = 250,
    ) -> Tuple[bool, Optional[List[GoogleCalendarEvent]], Optional[str]]:
        """
        Lista eventos de um calendário

        Args:
            calendar_id: ID do calendário
            time_min: Data/hora mínima (opcional)
            time_max: Data/hora máxima (opcional)
            max_results: Número máximo de resultados

        Returns:
            Tupla (sucesso, lista_de_eventos, mensagem_de_erro)
        """
        if not self.access_token:
            return False, None, "Token de acesso não fornecido"

        try:
            params = {
                "maxResults": max_results,
                "singleEvents": True,
                "orderBy": "startTime",
            }

            if time_min:
                params["timeMin"] = time_min.isoformat()
            if time_max:
                params["timeMax"] = time_max.isoformat()

            response = self.client.get(
                f"{self.BASE_URL}/calendars/{calendar_id}/events",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params=params,
            )

            if response.status_code == 200:
                data = response.json()
                return True, data.get("items", []), None
            else:
                return False, None, f"Erro HTTP {response.status_code}: {response.text}"

        except Exception as e:
            return False, None, f"Erro ao listar eventos: {str(e)}"

    def __del__(self):
        """Cleanup do cliente HTTP"""
        if hasattr(self, "client"):
            self.client.close()


def format_insper_event_for_google(insper_event: Dict[str, Any]) -> GoogleCalendarEvent:
    """
    Converte um evento do Insper para o formato do Google Calendar

    Args:
        insper_event: Evento no formato do Insper

    Returns:
        Evento no formato do Google Calendar
    """
    # Exemplo de conversão - ajustar conforme estrutura real dos eventos do Insper
    return {
        "summary": insper_event.get("title", "Evento do Insper"),
        "description": insper_event.get("description", ""),
        "start": {
            "dateTime": insper_event.get("start_time"),
            "timeZone": "America/Sao_Paulo",
        },
        "end": {
            "dateTime": insper_event.get("end_time"),
            "timeZone": "America/Sao_Paulo",
        },
        "location": insper_event.get("location", ""),
        "source": {
            "title": "Insper Sync",
            "url": f"https://{DOMAIN}",
        },
        "extendedProperties": {
            "private": {
                "insper_event_id": str(insper_event.get("id", "")),
                "sync_source": "insper",
            }
        },
    }


def get_or_refresh_access_token(user) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Obtém um token de acesso válido, renovando se necessário

    Args:
        user: Instância do modelo User

    Returns:
        Tupla (sucesso, token_de_acesso, mensagem_de_erro)
    """
    if not user.has_google_credentials():
        return False, None, "Usuário não tem credenciais do Google configuradas"

    # Se o token não expirou, retorna o atual
    if not user.is_google_token_expired():
        return True, user.google_access_token, None

    # Token expirado, tenta renovar
    client = GoogleCalendarClient()
    success, token_data, error = client.refresh_access_token(user.google_refresh_token)

    if success and token_data:
        # Atualiza os tokens do usuário
        user.update_google_credentials(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", user.google_refresh_token),
            expires_in=token_data.get("expires_in", 3600),
        )
        return True, token_data["access_token"], None
    else:
        return False, None, error or "Erro ao renovar token de acesso"
