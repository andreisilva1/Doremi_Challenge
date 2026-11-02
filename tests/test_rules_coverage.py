"""Toda regra marcada T em knowledge/rules.md precisa ser citada por algum teste."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_every_tested_rule_has_a_test():
    matrix = (ROOT / "knowledge" / "rules.md").read_text(encoding="utf-8")
    codes = re.findall(r"^\| ([A-Z]+-\d+) \|.*\| T \|$", matrix, re.MULTILINE)
    tests = "".join(
        p.read_text(encoding="utf-8")
        for p in (ROOT / "tests").glob("test_*.py")
        if p.name != Path(__file__).name
    )
    assert codes
    assert [c for c in codes if c not in tests] == []
