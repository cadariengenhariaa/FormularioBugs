"""Funções e constantes usadas por mais de uma tela."""

import unicodedata
from datetime import datetime

from tkcalendar import DateEntry

from . import tema

SEM_RESPONSAVEL = "Sem responsável (definir depois)"
CALENDARIOS = []  # campos de data abertos, para trocar tema e zoom


def chave_ordenacao(nome):
    texto = unicodedata.normalize("NFKD", nome or "")
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def data_brasil(iso):
    """'2026-10-17' -> '17/10/2026'; '2026-10-17 09:30:00' -> '17/10/2026 09:30'."""
    if not iso:
        return ""
    try:
        if len(iso) > 10:
            return datetime.strptime(iso[:16], "%Y-%m-%d %H:%M").strftime("%d/%m/%Y %H:%M")
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return iso


def seletor_data(pai):
    entrada = DateEntry(pai, locale="pt_BR", date_pattern="dd/MM/yyyy", width=12, borderwidth=0)
    tema.ajustar_calendario(entrada)
    CALENDARIOS.append(entrada)
    return entrada
