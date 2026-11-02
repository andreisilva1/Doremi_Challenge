"""Regras de negócio do manual. Códigos entre colchetes remetem a knowledge/rules.md."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

from emporio.data import Promotion

CENT = Decimal("0.01")
PIX_DISCOUNT = Decimal("0.05")
MAX_INSTALLMENTS = 12
# (maior número de parcelas da faixa, parcela mínima)
MIN_INSTALLMENT = ((1, Decimal("0")), (3, Decimal("50")), (6, Decimal("80")), (12, Decimal("100")))


def round_brl(value: Decimal) -> Decimal:
    """Arredondamento comercial ao centavo [PAG-09]."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def active_discount(product_id: int, promotions: Iterable[Promotion]) -> Decimal | None:
    """Maior desconto ativo do produto [PRO-01, PRO-04]; None se não houver."""
    return max(
        (p.discount_percent for p in promotions if p.product_id == product_id and p.is_active),
        default=None,
    )


def promo_price(price: Decimal, discount_percent: Decimal) -> Decimal:
    return round_brl(price * (100 - discount_percent) / 100)


def pix_price(price: Decimal, on_promotion: bool) -> Decimal:
    """PIX dá 5% sobre o preço de tabela [PAG-01] e não se soma à promoção [PAG-02]."""
    return price if on_promotion else round_brl(price * (1 - PIX_DISCOUNT))


def min_installment(n: int) -> Decimal:
    """Parcela mínima para n vezes [PAG-05]; 1x não tem mínimo [PAG-06]."""
    if n < 1:
        raise ValueError("número de parcelas deve ser positivo")
    for upper, minimum in MIN_INSTALLMENT:
        if n <= upper:
            return minimum
    raise ValueError(f"máximo de {MAX_INSTALLMENTS} parcelas")
