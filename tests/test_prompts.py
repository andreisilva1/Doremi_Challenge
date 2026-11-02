from datetime import date

from emporio import tools
from emporio.prompts import system_prompt


def test_reference_date_is_injected():
    """PED-05"""
    prompt = system_prompt(date(2026, 3, 23))
    assert "23/03/2026" in prompt and "{today}" not in prompt


def test_prompt_mentions_every_tool():
    prompt = system_prompt(date(2026, 3, 23))
    assert [f.__name__ for f in tools.TOOLS if f"`{f.__name__}`" not in prompt] == []
