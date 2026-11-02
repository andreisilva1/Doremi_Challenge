from decimal import Decimal

import pytest

from emporio import rules
from emporio.data import Promotion


def _promo(product_id, percent, active):
    return Promotion(0, product_id, Decimal(percent), "", active)


def test_pix_discount():
    """PAG-01"""
    assert rules.pix_price(Decimal("1000"), on_promotion=False) == Decimal("950.00")


def test_pix_not_on_promotion():
    """PAG-02"""
    assert rules.pix_price(Decimal("359"), on_promotion=True) == Decimal("359")


@pytest.mark.parametrize(
    ("n", "minimum"),
    [(2, 50), (3, 50), (4, 80), (6, 80), (7, 100), (12, 100)],
)
def test_min_installment(n, minimum):
    """PAG-05"""
    assert rules.min_installment(n) == Decimal(minimum)


def test_single_installment_has_no_minimum():
    """PAG-06"""
    assert rules.min_installment(1) == 0


@pytest.mark.parametrize("n", [0, 13])
def test_installments_out_of_range(n):
    with pytest.raises(ValueError):
        rules.min_installment(n)


def test_round_half_up():
    """PAG-09"""
    assert rules.round_brl(Decimal("10.005")) == Decimal("10.01")
    assert rules.round_brl(Decimal("10.004")) == Decimal("10.00")


def test_only_active_promotions():
    """PRO-01"""
    promos = [_promo(1, "30", False), _promo(1, "10", True), _promo(2, "50", True)]
    assert rules.active_discount(1, promos) == Decimal("10")
    assert rules.active_discount(3, promos) is None


def test_highest_active_promotion_wins():
    """PRO-04"""
    promos = [_promo(1, "10", True), _promo(1, "25", True)]
    assert rules.active_discount(1, promos) == Decimal("25")


def test_promo_price():
    assert rules.promo_price(Decimal("359"), Decimal("10")) == Decimal("323.10")
