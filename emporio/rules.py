"""Regras de negócio do manual. Códigos entre colchetes remetem a knowledge/rules.md."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from emporio.data import Order, Promotion

CENT = Decimal("0.01")

# Pagamento

PIX_DISCOUNT = Decimal("0.05")
MAX_INSTALLMENTS = 12
# (maior número de parcelas da faixa, parcela mínima)
MIN_INSTALLMENT = ((1, Decimal("0")), (3, Decimal("50")), (6, Decimal("80")), (12, Decimal("100")))
COMBINED_PAYMENT_ABOVE = Decimal("2000")
BOLETO_CLEARING = "até 3 dias úteis"


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


def max_installments(total: Decimal) -> int:
    """Maior número de parcelas sem juros que respeita a parcela mínima [PAG-04, PAG-07]."""
    return max(n for n in range(1, MAX_INSTALLMENTS + 1) if total / n >= min_installment(n))


def can_combine_payments(total: Decimal) -> bool:
    """Combinar formas (ex.: PIX + cartão) só acima de R$ 2.000 [PAG-08]."""
    return total > COMBINED_PAYMENT_ABOVE


@dataclass(frozen=True)
class PaymentQuote:
    total: Decimal  # débito, boleto e crédito [PAG-03]
    pix_total: Decimal
    can_combine: bool


def quote_payment(lines: Iterable[tuple[Decimal, bool, int]]) -> PaymentQuote:
    """Condições de pagamento para linhas (preço efetivo, está em promoção, quantidade)."""
    lines = list(lines)
    total = sum((price * qty for price, _, qty in lines), Decimal("0"))
    pix_total = sum((pix_price(price, promo) * qty for price, promo, qty in lines), Decimal("0"))
    return PaymentQuote(total, pix_total, can_combine_payments(total))


# Frete

LOCAL_CITY = "campo grande"
FREE_SHIPPING_ABOVE = Decimal("500")
LOCAL_FEE = Decimal("35")
LOCAL_DAYS = "1 a 3 dias úteis"
CARRIERS = (
    ("PAC (Correios)", "5 a 12 dias úteis"),
    ("SEDEX (Correios)", "2 a 5 dias úteis"),
    ("Jadlog", "3 a 8 dias úteis"),
)


@dataclass(frozen=True)
class ShippingQuote:
    local: bool
    fee: Decimal | None  # None: calculado pelo CEP, peso e dimensões
    options: tuple[tuple[str, str], ...]  # (modalidade, prazo)
    special_freight: bool


def shipping_quote(city: str, subtotal: Decimal, large_item: bool = False) -> ShippingQuote:
    """Frete pela cidade [FRE-01, FRE-03]; o subtotal já vem com os descontos [FRE-02].

    Item de grande porte fora de Campo Grande pede cotação individual [FRE-04].
    """
    if city.strip().lower() == LOCAL_CITY:
        fee = Decimal("0") if subtotal > FREE_SHIPPING_ABOVE else LOCAL_FEE
        return ShippingQuote(True, fee, (("Motoboy próprio", LOCAL_DAYS),), False)
    return ShippingQuote(False, None, CARRIERS, large_item)


# Horário de funcionamento

OPENING_HOURS = {  # dia da semana (0 = segunda) -> (abre, fecha) [LOJ-01]
    **{d: (time(9), time(18)) for d in range(5)},
    5: (time(9), time(13)),
}
FIXED_HOLIDAYS = {  # feriados nacionais de data fixa (mês, dia) [LOJ-03]
    (1, 1): "Confraternização Universal",
    (4, 21): "Tiradentes",
    (5, 1): "Dia do Trabalho",
    (9, 7): "Independência do Brasil",
    (10, 12): "Nossa Senhora Aparecida",
    (11, 2): "Finados",
    (11, 15): "Proclamação da República",
    (11, 20): "Dia da Consciência Negra",
    (12, 25): "Natal",
}


def holiday(d: date) -> str | None:
    return FIXED_HOLIDAYS.get((d.month, d.day))


def opening_hours(d: date) -> tuple[time, time] | None:
    """Horário do dia, ou None se a loja não abre (domingo ou feriado)."""
    return None if holiday(d) else OPENING_HOURS.get(d.weekday())


@dataclass(frozen=True)
class StoreStatus:
    is_open: bool
    closes_at: datetime | None
    next_opening: datetime | None  # preenchido quando está fechada [LOJ-04]


def store_status(now: datetime) -> StoreStatus:
    """Aberta ou fechada em `now`, que deve estar no fuso da loja [LOJ-02]."""
    for offset in range(8):
        day = now.date() + timedelta(days=offset)
        hours = opening_hours(day)
        if hours is None:
            continue
        opens = datetime.combine(day, hours[0], now.tzinfo)
        closes = datetime.combine(day, hours[1], now.tzinfo)
        if offset == 0 and opens <= now < closes:
            return StoreStatus(True, closes, None)
        if now < opens:
            return StoreStatus(False, None, opens)
    raise AssertionError("a loja abre pelo menos uma vez por semana")


# Trocas, devoluções e garantia

REGRET_DAYS = 7
DEFECT_DAYS = 30
PREFERENCE_DAYS = 7
LEGAL_WARRANTY_DAYS = 90
REFUND_DEADLINE = "até 10 dias úteis"

REGRET, DEFECT, PREFERENCE = "arrependimento", "defeito", "preferencia"


@dataclass(frozen=True)
class ReturnCheck:
    eligible: bool | None  # None: encaminhar para a equipe
    deadline: date | None
    reason: str


def received_on(order: Order) -> date | None:
    """Data de recebimento: os dados só têm a previsão de entrega [DEV-02]."""
    return order.estimated_delivery if order.status == "delivered" else None


def legal_warranty_until(order: Order) -> date | None:
    """Garantia legal de 90 dias contados do recebimento [GAR-01]."""
    received = received_on(order)
    return received + timedelta(days=LEGAL_WARRANTY_DAYS) if received else None


def check_return(order: Order, kind: str, today: date) -> ReturnCheck:
    """Elegibilidade de devolução ou troca na data `today` [DEV-01 a DEV-08]."""
    received = received_on(order)
    if received is None:
        return ReturnCheck(None, None, "pedido ainda não entregue; encaminhar para a equipe")
    if kind == REGRET:
        if order.tracking_code is None:  # pedido com rastreio = compra online [DEV-03]
            return ReturnCheck(False, None, "arrependimento vale só para compra online")
        deadline = received + timedelta(days=REGRET_DAYS)
        reason = (
            "embalagem original, sem uso, com acessórios e manuais; reembolso na mesma forma de "
            f"pagamento em {REFUND_DEADLINE}; frete de devolução por conta da loja"
        )
    elif kind == DEFECT:
        deadline = order.order_date + timedelta(days=DEFECT_DAYS)
        if today > deadline:
            return ReturnCheck(
                False,
                deadline,
                "prazo de troca na loja encerrado; acionar a garantia do fabricante, com a loja "
                "intermediando se o cliente pedir",
            )
        reason = "defeito de fabricação; mau uso, queda, umidade ou modificação não são cobertos"
    elif kind == PREFERENCE:
        deadline = received + timedelta(days=PREFERENCE_DAYS)
        reason = "sujeita à disponibilidade; produto perfeito e na embalagem original"
    else:
        raise ValueError(f"tipo de troca desconhecido: {kind!r}")
    return ReturnCheck(today <= deadline, deadline, reason)


# Atendimento

COMPLAINT_RESPONSE = "até 24 horas úteis"  # [ATD-03]

STORE_INFO = {  # [LOJ-05 a LOJ-07]
    "endereco": "Rua 14 de Maio, 3200 — Centro, Campo Grande - MS, 79202-333",
    "telefone": "(67) 3341-4444",
    "whatsapp": "(67) 3321-4500",
    "email": "contato@emporiodamusica.com.br",
}
