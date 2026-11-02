"""Configuração lida do ambiente (.env)."""

from __future__ import annotations

import os
from datetime import date
from zoneinfo import ZoneInfo


def reference_date() -> date:
    """Data "de hoje" para pedidos e prazos: os dados são um retrato de março/2026 [PED-05]."""
    return date.fromisoformat(os.environ.get("REFERENCE_DATE", "2026-03-23"))


def store_timezone() -> ZoneInfo:
    """Fuso da loja, usado com o relógio real no horário de funcionamento [LOJ-02]."""
    return ZoneInfo(os.environ.get("STORE_TIMEZONE", "America/Campo_Grande"))
