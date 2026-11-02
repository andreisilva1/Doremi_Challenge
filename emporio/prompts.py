"""Prompt de sistema do agente, mantido em prompts/system.md para ser lido fora do código."""

from __future__ import annotations

from datetime import date
from pathlib import Path

SYSTEM_PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "system.md"


def system_prompt(today: date) -> str:
    return SYSTEM_PROMPT.read_text(encoding="utf-8").replace("{today}", f"{today:%d/%m/%Y}")
