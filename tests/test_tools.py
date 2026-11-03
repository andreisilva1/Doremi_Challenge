from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from emporio import tools

TZ = ZoneInfo("America/Campo_Grande")


def test_brl_format():
    """PAG-09"""
    assert tools.brl(Decimal("1234.565")) == "R$ 1.234,57"
    assert tools.brl(Decimal("35")) == "R$ 35,00"


def test_search_returns_formatted_summaries():
    hit = tools.search_products("ukulele kalani tenor")["resultados"][0]
    assert hit == {
        "id": 127,
        "nome": "Kalani KAL-700T Tenor Natural",
        "status": "disponível",
        "preco": "R$ 323,10",
        "preco_pix": "R$ 323,10",
        "preco_original": "R$ 359,00",
        "desconto_percent": "10%",
        "cartao_credito": "até 4x de R$ 80,78 sem juros",
    }


def test_product_sheet_has_installments():
    """PAG-07: 599,90 sai em até 6x."""
    assert tools.get_product(81)["cartao_credito"] == "até 6x de R$ 99,98 sem juros"


def test_search_without_results_explains_scope():
    """CAT-08"""
    result = tools.search_products("saxofone")
    assert result["resultados"] == [] and "Sopro" in result["observacao"]


def test_unavailable_product_brings_alternatives():
    """CAT-03"""
    info = tools.get_product(96)
    assert info["status"] == "sem estoque" and len(info["alternativas"]) == 3


def test_unknown_product():
    assert "erro" in tools.get_product(9999)


def test_quote_payment_and_local_shipping():
    """PAG-07, PRO-02, FRE-01: 323,10 em promoção + 599,90 (PIX 569,91)."""
    result = tools.quote(
        [{"product_id": 127, "quantity": 1}, {"product_id": 81, "quantity": 1}], "Campo Grande"
    )
    assert result["total"] == "R$ 923,00"
    assert result["total_pix"] == "R$ 893,01"
    assert result["cartao_credito"] == "até 9x de R$ 102,56 sem juros"
    assert result["frete"]["valor"] == "R$ 0,00"


def test_quote_tells_boleto_clearing_time():
    """PAG-03"""
    result = tools.quote([{"product_id": 81, "quantity": 1}])
    assert result["debito_ou_boleto"] == "R$ 599,90"
    assert result["boleto_compensacao"] == "até 3 dias úteis"


def test_quote_large_item_outside_campo_grande():
    """FRE-04"""
    result = tools.quote([{"product_id": 139, "quantity": 1}], "Dourados")
    assert "cotação individual" in result["frete"]["valor"]
    assert "checkout" not in result["frete"]["valor"]


def test_quote_refuses_unavailable_or_excess():
    """CAT-04, CAT-05"""
    assert "erro" in tools.quote([{"product_id": 136, "quantity": 1}])
    assert "erro" in tools.quote([{"product_id": 130, "quantity": 1}])
    assert "erro" in tools.quote([{"product_id": 81, "quantity": 10_000}])


def test_order_requires_identity():
    """PED-01, LGPD-01"""
    assert tools.get_order(7, "leticia.rocha@jmail.com")["status"] == "entregue"
    assert tools.get_order(7, "lucas.mendes@jmail.com") == {"erro": tools.NOT_VERIFIED}
    assert tools.get_order(999, "lucas.mendes@jmail.com") == {"erro": tools.NOT_VERIFIED}


def test_return_check_with_formatted_dates():
    """DEV-05, GAR-01"""
    result = tools.check_return(7, "leticia.rocha@jmail.com", "defeito")
    assert result["elegivel"] is False
    assert result["prazo_ate"] == "05/03/2026"
    assert result["garantia_legal_ate"] == "18/05/2026"


def test_return_check_requires_identity():
    """LGPD-01"""
    assert tools.check_return(7, "0000", "defeito") == {"erro": tools.NOT_VERIFIED}


def test_store_status_closed_on_saturday_afternoon():
    """LOJ-04"""
    result = tools.store_status_at(datetime(2026, 3, 28, 14, 0, tzinfo=TZ))
    assert result["aberta"] is False
    assert result["abre"] == "segunda (30/03) às 09:00"


def test_store_status_on_holiday():
    """LOJ-03"""
    result = tools.store_status_at(datetime(2026, 11, 2, 10, 0, tzinfo=TZ))
    assert result["feriado_hoje"] == "Finados" and result["abre"] == "amanhã às 09:00"


def test_policy_sections_without_internal_notes():
    for topic in tools.TOPIC_SECTIONS:
        text = tools.get_policy(topic)
        assert text.startswith("## §") and "🟡" not in text
    assert "Itens não elegíveis" in tools.get_policy("trocas")


def test_handoff_gives_response_time():
    """ATD-03"""
    assert tools.handoff_to_human("reclamação")["retorno"] == "até 24 horas úteis"
