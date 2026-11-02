from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from emporio import rules
from emporio.data import Order, OrderItem, Promotion

TZ = ZoneInfo("America/Campo_Grande")
D = Decimal


def _promo(product_id, percent, active):
    return Promotion(0, product_id, D(percent), "", active)


def _order(status="delivered", ordered=date(2026, 3, 1), delivered=date(2026, 3, 10), tracking="X"):
    return Order(
        1, 1, ordered, status, D("100"), "pix", tracking, delivered, None, (OrderItem(1, 1),)
    )


# Pagamento


def test_pix_discount():
    """PAG-01"""
    assert rules.pix_price(D("1000"), on_promotion=False) == D("950.00")


def test_pix_not_on_promotion():
    """PAG-02"""
    assert rules.pix_price(D("359"), on_promotion=True) == D("359")


def test_other_methods_pay_full_price():
    """PAG-03"""
    quote = rules.quote_payment([(D("1000"), False, 1)])
    assert quote.total == D("1000")
    assert rules.BOLETO_CLEARING == "até 3 dias úteis"


def test_up_to_12_installments():
    """PAG-04"""
    assert rules.max_installments(D("100000")) == 12


@pytest.mark.parametrize(
    ("n", "minimum"),
    [(2, 50), (3, 50), (4, 80), (6, 80), (7, 100), (12, 100)],
)
def test_min_installment(n, minimum):
    """PAG-05"""
    assert rules.min_installment(n) == D(minimum)


def test_single_installment_has_no_minimum():
    """PAG-06"""
    assert rules.min_installment(1) == 0
    assert rules.max_installments(D("30")) == 1


@pytest.mark.parametrize("n", [0, 13])
def test_installments_out_of_range(n):
    with pytest.raises(ValueError):
        rules.min_installment(n)


@pytest.mark.parametrize(
    ("total", "n"),
    [
        ("99.99", 1),
        ("100", 2),
        ("150", 3),
        ("319.99", 3),
        ("320", 4),
        ("599.9", 6),
        ("700", 7),
        ("1199.99", 11),
        ("1200", 12),
    ],
)
def test_max_installments(total, n):
    """PAG-07"""
    assert rules.max_installments(D(total)) == n


def test_combined_payment_only_above_2000():
    """PAG-08"""
    assert not rules.can_combine_payments(D("2000"))
    assert rules.can_combine_payments(D("2000.01"))


def test_round_half_up():
    """PAG-09"""
    assert rules.round_brl(D("10.005")) == D("10.01")
    assert rules.round_brl(D("10.004")) == D("10.00")
    assert rules.quote_payment([(D("599.9"), False, 1)]).installment_value == D("99.98")


def test_quote_mixes_promo_and_regular_items():
    """PAG-02"""
    quote = rules.quote_payment([(D("323.10"), True, 1), (D("1000"), False, 2)])
    assert quote.total == D("2323.10")
    assert quote.pix_total == D("323.10") + D("1900.00")
    assert quote.can_combine


# Promoções


def test_only_active_promotions():
    """PRO-01"""
    promos = [_promo(1, "30", False), _promo(1, "10", True), _promo(2, "50", True)]
    assert rules.active_discount(1, promos) == D("10")
    assert rules.active_discount(3, promos) is None


def test_highest_active_promotion_wins():
    """PRO-04"""
    promos = [_promo(1, "10", True), _promo(1, "25", True)]
    assert rules.active_discount(1, promos) == D("25")


def test_promo_price():
    assert rules.promo_price(D("359"), D("10")) == D("323.10")


# Frete


@pytest.mark.parametrize(("subtotal", "fee"), [("500", "35"), ("500.01", "0"), ("100", "35")])
def test_local_shipping(subtotal, fee):
    """FRE-01"""
    quote = rules.shipping_quote("Campo Grande", D(subtotal))
    assert quote.local and quote.fee == D(fee)
    assert quote.options == (("Motoboy próprio", "1 a 3 dias úteis"),)


def test_free_shipping_uses_discounted_subtotal():
    """FRE-02: R$ 539 de tabela com 10% off fica abaixo do frete grátis."""
    subtotal = rules.promo_price(D("539"), D("10"))
    assert rules.shipping_quote("campo grande", subtotal).fee == D("35")


def test_other_cities_get_carriers_without_price():
    """FRE-03"""
    quote = rules.shipping_quote("Dourados", D("5000"))
    assert not quote.local and quote.fee is None
    assert [name for name, _ in quote.options] == ["PAC (Correios)", "SEDEX (Correios)", "Jadlog"]


def test_large_item_needs_special_freight_outside_campo_grande():
    """FRE-04"""
    assert rules.shipping_quote("Corumbá", D("5000"), large_item=True).special_freight
    assert not rules.shipping_quote("Campo Grande", D("5000"), large_item=True).special_freight


@pytest.mark.parametrize(
    ("code", "valid"),
    [
        ("BR4K7M2X9P1BR", True),
        ("brab1234567br", True),
        ("BR12345678BR", False),
        ("XX123456789BR", False),
        ("BR1234-6789BR", False),
    ],
)
def test_tracking_format(code, valid):
    """FRE-05"""
    assert rules.is_valid_tracking(code) is valid


# Horário


@pytest.mark.parametrize(
    ("moment", "is_open"),
    [
        (datetime(2026, 3, 23, 8, 59), False),  # segunda
        (datetime(2026, 3, 23, 9, 0), True),
        (datetime(2026, 3, 23, 17, 59), True),
        (datetime(2026, 3, 23, 18, 0), False),
        (datetime(2026, 3, 28, 12, 0), True),  # sábado
        (datetime(2026, 3, 28, 13, 0), False),
        (datetime(2026, 3, 29, 10, 0), False),  # domingo
    ],
)
def test_opening_hours(moment, is_open):
    """LOJ-01"""
    assert rules.store_status(moment.replace(tzinfo=TZ)).is_open is is_open


def test_status_uses_given_timezone():
    """LOJ-02"""
    status = rules.store_status(datetime(2026, 3, 23, 10, 0, tzinfo=TZ))
    assert status.closes_at == datetime(2026, 3, 23, 18, 0, tzinfo=TZ)


def test_fixed_national_holidays_are_closed():
    """LOJ-03: 21/04/2026 é terça."""
    assert rules.holiday(date(2026, 4, 21)) == "Tiradentes"
    assert not rules.store_status(datetime(2026, 4, 21, 10, 0, tzinfo=TZ)).is_open


@pytest.mark.parametrize(
    ("moment", "next_opening"),
    [
        (datetime(2026, 3, 23, 7, 0), datetime(2026, 3, 23, 9, 0)),
        (datetime(2026, 3, 27, 19, 0), datetime(2026, 3, 28, 9, 0)),  # sexta à noite
        (datetime(2026, 3, 28, 14, 0), datetime(2026, 3, 30, 9, 0)),  # sábado à tarde
        (datetime(2026, 4, 20, 19, 0), datetime(2026, 4, 22, 9, 0)),  # véspera de Tiradentes
    ],
)
def test_next_opening(moment, next_opening):
    """LOJ-04"""
    status = rules.store_status(moment.replace(tzinfo=TZ))
    assert status.next_opening == next_opening.replace(tzinfo=TZ)


def test_store_contacts():
    """LOJ-05, LOJ-06, LOJ-07"""
    assert rules.STORE_INFO["endereco"].startswith("Rua 14 de Maio, 3200")
    assert rules.STORE_INFO["telefone"] == "(67) 3341-4444"
    assert rules.STORE_INFO["whatsapp"] == "(67) 3321-4500"
    assert rules.STORE_INFO["email"] == "contato@emporiodamusica.com.br"


# Trocas e garantia


@pytest.mark.parametrize(
    ("today", "eligible"), [(date(2026, 3, 17), True), (date(2026, 3, 18), False)]
)
def test_regret_7_days_after_receipt(today, eligible):
    """DEV-01, DEV-02: recebido em 10/03 (previsão de entrega), prazo até 17/03."""
    check = rules.check_return(_order(), rules.REGRET, today)
    assert check.deadline == date(2026, 3, 17)
    assert check.eligible is eligible


def test_regret_only_for_online_orders():
    """DEV-03"""
    assert (
        rules.check_return(_order(tracking=None), rules.REGRET, date(2026, 3, 11)).eligible is False
    )


def test_regret_conditions():
    """DEV-04"""
    reason = rules.check_return(_order(), rules.REGRET, date(2026, 3, 11)).reason
    assert "10 dias úteis" in reason and "frete de devolução por conta da loja" in reason


def test_defect_30_days_after_purchase():
    """DEV-05: comprado em 01/03, prazo até 31/03; depois, fabricante."""
    assert rules.check_return(_order(), rules.DEFECT, date(2026, 3, 31)).eligible
    late = rules.check_return(_order(), rules.DEFECT, date(2026, 4, 1))
    assert late.eligible is False and "fabricante" in late.reason


def test_preference_7_days_after_receipt():
    """DEV-06"""
    check = rules.check_return(_order(), rules.PREFERENCE, date(2026, 3, 17))
    assert check.eligible and check.deadline == date(2026, 3, 17)


@pytest.mark.parametrize("status", ["pending", "confirmed", "shipped", "cancelled"])
def test_not_delivered_goes_to_team(status):
    """DEV-08"""
    check = rules.check_return(_order(status=status), rules.DEFECT, date(2026, 3, 11))
    assert check.eligible is None


def test_legal_warranty_90_days_after_receipt():
    """GAR-01"""
    assert rules.legal_warranty_until(_order()) == date(2026, 6, 8)


def test_complaint_response_time():
    """ATD-03"""
    assert rules.COMPLAINT_RESPONSE == "até 24 horas úteis"
