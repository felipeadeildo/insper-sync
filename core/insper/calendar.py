"""
Utilitários para trabalhar com o calendário do Insper
"""

from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urlencode

from .auth import InsperAuth
from .exceptions import InsperAuthError, InsperConnectionError
from .models import InsperAcademicData, InsperCalendarResponse, InsperEvent


class InsperCalendar:
    """Utilitário para obter e manipular eventos do calendário do Insper"""

    def __init__(self, auth: InsperAuth):
        """
        Inicializa o calendário com uma sessão autenticada

        Args:
            auth: Instância autenticada do InsperAuth
        """
        self.auth = auth
        if not hasattr(auth, "user_data"):
            raise InsperAuthError("Sessão não autenticada. Faça login primeiro.")

    def _build_calendar_url(
        self,
        pessoa_id: str,
        cod_aluno: str,
        start_date: datetime,
        end_date: datetime,
        page: int = 0,
        size: int = 1000,
        timezone: bool = False,
    ) -> str:
        """
        Constrói a URL para buscar eventos do calendário

        Args:
            pessoa_id: ID da pessoa no sistema
            cod_aluno: Código do aluno
            start_date: Data de início
            end_date: Data de fim
            page: Página (padrão 0)
            size: Tamanho da página (padrão 1000)
            timezone: Se deve considerar timezone (padrão False)

        Returns:
            URL formatada para a API
        """
        # Formata as datas no formato esperado pela API
        start_str = start_date.strftime("%Y-%m-%dT00:00:00.000-03:00")
        end_str = end_date.strftime("%Y-%m-%dT00:00:00.000-03:00")

        params = {
            "codAluno": cod_aluno,
            "start": start_str,
            "end": end_str,
            "page": page,
            "size": size,
            "timezone": str(timezone).lower(),
        }

        query_string = urlencode(params)
        return f"/AOnline/apix/api/rest/alunos/pessoa/{pessoa_id}/events?{query_string}"

    def get_events_for_month(
        self, year: int, month: int, academic_data: Optional[InsperAcademicData] = None
    ) -> InsperCalendarResponse:
        """
        Obtém eventos de um mês específico

        Args:
            year: Ano
            month: Mês (1-12)
            academic_data: Dados acadêmicos (se não fornecidos, serão buscados)

        Returns:
            Resposta com os eventos do mês

        Raises:
            InsperConnectionError: Se houver erro na conexão
            InsperAuthError: Se não houver dados acadêmicos
        """
        if academic_data is None:
            academic_data = self.auth.get_user_academic_data()
            if academic_data is None:
                raise InsperAuthError("Não foi possível obter dados acadêmicos")

        # Define o primeiro e último dia do mês
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(days=1)

        return self._get_events_range(
            start_date=start_date, end_date=end_date, academic_data=academic_data
        )

    def get_events_for_range(
        self,
        start_date: datetime,
        end_date: datetime,
        academic_data: Optional[InsperAcademicData] = None,
    ) -> List[InsperEvent]:
        """
        Obtém eventos para um range de datas, lidando com a limitação da API
        que só retorna um mês por vez.

        Args:
            start_date: Data de início
            end_date: Data de fim
            academic_data: Dados acadêmicos (se não fornecidos, serão buscados)

        Returns:
            Lista com todos os eventos no range especificado

        Raises:
            InsperConnectionError: Se houver erro na conexão
            InsperAuthError: Se não houver dados acadêmicos
        """
        if academic_data is None:
            academic_data = self.auth.get_user_academic_data()
            if academic_data is None:
                raise InsperAuthError("Não foi possível obter dados acadêmicos")

        all_events = []
        current_date = start_date.replace(day=1)  # Início do mês

        while current_date <= end_date:
            try:
                # Busca eventos do mês atual
                response = self.get_events_for_month(
                    year=current_date.year,
                    month=current_date.month,
                    academic_data=academic_data,
                )

                # Filtra eventos que estão dentro do range solicitado
                filtered_events = [
                    event
                    for event in response.events
                    if start_date <= event.start_datetime <= end_date
                ]

                all_events.extend(filtered_events)

            except Exception as e:
                # Log do erro, mas continua para o próximo mês
                print(
                    f"Erro ao buscar eventos de {current_date.strftime('%m/%Y')}: {e}"
                )

            # Vai para o próximo mês
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)

        return all_events

    def _get_events_range(
        self,
        start_date: datetime,
        end_date: datetime,
        academic_data: InsperAcademicData,
        page: int = 0,
        size: int = 1000,
    ) -> InsperCalendarResponse:
        """
        Método interno para buscar eventos em um range específico

        Args:
            start_date: Data de início
            end_date: Data de fim
            academic_data: Dados acadêmicos
            page: Página
            size: Tamanho da página

        Returns:
            Resposta da API
        """
        try:
            url = self._build_calendar_url(
                pessoa_id=academic_data.id,
                cod_aluno=academic_data.codAluno,
                start_date=start_date,
                end_date=end_date,
                page=page,
                size=size,
            )

            response = self.auth.session.get(url, timeout=30)
            response.raise_for_status()

            data = response.json()
            return InsperCalendarResponse.from_dict(data)

        except Exception as e:
            raise InsperConnectionError(f"Erro ao buscar eventos: {str(e)}")

    def get_events_by_discipline(
        self,
        start_date: datetime,
        end_date: datetime,
        discipline_code: str,
        academic_data: Optional[InsperAcademicData] = None,
    ) -> List[InsperEvent]:
        """
        Obtém eventos de uma disciplina específica

        Args:
            start_date: Data de início
            end_date: Data de fim
            discipline_code: Código da disciplina (ex: "GRCIECOMP_202261_001")
            academic_data: Dados acadêmicos

        Returns:
            Lista de eventos da disciplina
        """
        events = self.get_events_for_range(start_date, end_date, academic_data)

        return [
            event
            for event in events
            if event.disciplina_codigo and discipline_code in event.disciplina_codigo
        ]

    def get_events_by_teacher(
        self,
        start_date: datetime,
        end_date: datetime,
        teacher_name: str,
        academic_data: Optional[InsperAcademicData] = None,
    ) -> List[InsperEvent]:
        """
        Obtém eventos de um professor específico

        Args:
            start_date: Data de início
            end_date: Data de fim
            teacher_name: Nome do professor
            academic_data: Dados acadêmicos

        Returns:
            Lista de eventos do professor
        """
        events = self.get_events_for_range(start_date, end_date, academic_data)

        return [
            event
            for event in events
            if event.docente and teacher_name.lower() in event.docente.lower()
        ]

    def get_weekly_schedule(
        self, week_start: datetime, academic_data: Optional[InsperAcademicData] = None
    ) -> List[InsperEvent]:
        """
        Obtém a programação semanal (7 dias a partir da data especificada)

        Args:
            week_start: Data de início da semana
            academic_data: Dados acadêmicos

        Returns:
            Lista de eventos da semana
        """
        week_end = week_start + timedelta(days=6)
        return self.get_events_for_range(week_start, week_end, academic_data)

    def get_today_events(
        self, academic_data: Optional[InsperAcademicData] = None
    ) -> List[InsperEvent]:
        """
        Obtém eventos de hoje

        Args:
            academic_data: Dados acadêmicos

        Returns:
            Lista de eventos de hoje
        """
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.get_events_for_range(today, today, academic_data)
