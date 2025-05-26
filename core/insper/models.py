"""
Modelos de dados para o módulo Insper
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class InsperUserData:
    """Dados do usuário do Insper retornados após login"""

    id: str
    name: str
    login: str
    senhaAlterada: str
    roles: str
    root: bool
    theme: str


@dataclass
class InsperAcademicData:
    """Dados acadêmicos do usuário do Insper retornados após consulta"""

    id: str
    matricula: str
    codAluno: str
    situacaoAluno: str
    nomeAluno: str
    codCurso: str
    nomeCurso: str
    sexo: str
    turma: str
    serie: str
    ano: str
    semestre: str
    descrSemestre: str

    @classmethod
    def from_dict(cls, data: dict):
        """
        Cria uma instância da classe a partir de um dicionário,
        ignorando campos extras que não estão definidos na classe.
        """
        # Filtra apenas as chaves que existem como campos na classe
        valid_fields = {k: v for k, v in data.items() if k in cls.__annotations__}
        return cls(**valid_fields)


@dataclass
class InsperEvent:
    """Representa um evento do calendário do Insper"""

    id: Optional[str]
    title: str
    all_day: bool
    start_str: str
    end_str: str
    start_date: int  # timestamp em milissegundos
    end_date: int  # timestamp em milissegundos
    time_zone: str
    descricao: str
    icone: str
    event_id: str
    tipo_evento: str
    hover_info: str
    class_name: str

    # Campos opcionais
    url: Optional[str] = None
    nome_subdisciplina: Optional[str] = None
    color: Optional[str] = None
    background_color: Optional[str] = None
    border_color: Optional[str] = None
    text_color: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict):
        """
        Cria uma instância da classe a partir de um dicionário da API do Insper
        """
        return cls(
            id=data.get("id"),
            title=data["title"],
            all_day=data["allDay"],
            start_str=data["startStr"],
            end_str=data["endStr"],
            start_date=data["startDate"],
            end_date=data["endDate"],
            time_zone=data["timeZone"],
            descricao=data["descricao"],
            icone=data["icone"],
            event_id=data["eventId"],
            tipo_evento=data["tipoEvento"],
            hover_info=data["hoverInfo"],
            class_name=data["className"],
            url=data.get("url"),
            nome_subdisciplina=data.get("nomeSubdisciplina"),
            color=data.get("color"),
            background_color=data.get("backgroundColor"),
            border_color=data.get("borderColor"),
            text_color=data.get("textColor"),
        )

    @property
    def start_datetime(self) -> datetime:
        """Converte start_date (timestamp em ms) para datetime"""
        return datetime.fromtimestamp(self.start_date / 1000)

    @property
    def end_datetime(self) -> datetime:
        """Converte end_date (timestamp em ms) para datetime"""
        return datetime.fromtimestamp(self.end_date / 1000)

    @property
    def disciplina_codigo(self) -> Optional[str]:
        """Extrai o código da disciplina do título"""
        if "\n" in self.title:
            return self.title.split("\n")[1].strip()
        return None

    @property
    def dependencia(self) -> str:
        """Extrai a dependência da descrição"""
        if "Dependencia:" in self.descricao:
            return self.descricao.split("Dependencia: ")[1].strip()
        return "NÃO INFORMADA"

    @property
    def turma(self) -> Optional[str]:
        """Extrai a turma da descrição"""
        if "Turma:" in self.descricao:
            turma_part = self.descricao.split("Turma: ")[1]
            if "|" in turma_part:
                return turma_part.split(" |")[0].strip()
        return None

    @property
    def docente(self) -> Optional[str]:
        """Extrai o nome do docente do hover_info"""
        if "Docente:" in self.hover_info:
            return self.hover_info.split("Docente: ")[1].strip()
        return None


@dataclass
class InsperCalendarResponse:
    """Representa a resposta completa da API de calendário do Insper"""

    events: List[InsperEvent]
    total_elements: int
    total_pages: int
    current_page: int
    page_size: int

    @classmethod
    def from_dict(cls, data: dict):
        """Cria uma instância da classe a partir da resposta da API"""
        events = [InsperEvent.from_dict(event_data) for event_data in data["content"]]
        page_info = data["page"]

        return cls(
            events=events,
            total_elements=page_info["totalElements"],
            total_pages=page_info["totalPages"],
            current_page=page_info["number"],
            page_size=page_info["size"],
        )
