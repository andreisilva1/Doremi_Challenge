"""Relatório das inconsistências dos dados (DAD-01 a DAD-07 em knowledge/rules.md).

Os achados não mudam o que o agente responde: o total de um pedido é informado como registrado
[PED-04]. Uso: python -m emporio.audit
"""

from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from emporio import rules
from emporio.data import Order, Store, load_store


@dataclass(frozen=True)
class Finding:
    code: str
    ids: tuple[int, ...]
    message: str


def _list_total(store: Store, order: Order) -> Decimal:
    return sum((store.products[i.product_id].price * i.quantity for i in order.items), Decimal("0"))


def expected_total(store: Store, order: Order) -> Decimal:
    """Total pelas regras atuais: promoção ativa ou, sem ela, desconto do PIX."""
    total = Decimal("0")
    for item in order.items:
        price = store.products[item.product_id].price
        discount = rules.active_discount(item.product_id, store.promotions)
        if discount is not None:
            price = rules.promo_price(price, discount)
        elif order.payment_method == "pix":
            price = rules.pix_price(price, on_promotion=False)
        total += price * item.quantity
    return total


def _has_active_promo(store: Store, order: Order) -> bool:
    return any(
        rules.active_discount(i.product_id, store.promotions) is not None for i in order.items
    )


def audit(store: Store) -> list[Finding]:
    orders = sorted(store.orders.values(), key=lambda o: o.id)
    findings = []

    def add(code: str, ids: list[int], message: str) -> None:
        if ids:
            findings.append(Finding(code, tuple(ids), message))

    add(
        "DAD-01",
        [o.id for o in orders if o.total not in (_list_total(store, o), expected_total(store, o))],
        "pedidos com total diferente da soma dos itens",
    )
    add(
        "DAD-02",
        [
            o.id
            for o in orders
            if o.payment_method == "pix"
            and o.total == _list_total(store, o) != expected_total(store, o)
        ],
        "pedidos em PIX sem os 5% de desconto",
    )
    add(
        "DAD-03",
        [
            o.id
            for o in orders
            if o.installments and o.total / o.installments < rules.min_installment(o.installments)
        ],
        "pedidos com parcela abaixo do mínimo do §3.1",
    )
    add(
        "DAD-04",
        [o.id for o in orders if _has_active_promo(store, o) and o.total == _list_total(store, o)],
        # As promoções não têm data: não dá para saber se valiam na data do pedido.
        "pedidos com item em promoção ativa cobrado pelo preço de tabela",
    )
    add(
        "DAD-05",
        sorted(
            {
                i.product_id
                for o in orders
                for i in o.items
                if store.products[i.product_id].status == "coming_soon"
            }
        ),
        "produtos 'em breve' presentes em pedidos",
    )
    add(
        "DAD-06",
        sorted(p.id for p in store.products.values() if p.status == "discontinued" and p.stock),
        "produtos descontinuados com estoque",
    )
    by_email = defaultdict(list)
    for c in store.customers.values():
        by_email[c.email.strip().lower()].append(c.id)
    add(
        "DAD-07",
        sorted(cid for ids in by_email.values() if len(ids) > 1 for cid in ids),
        "clientes com o mesmo e-mail",
    )
    return findings


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for f in audit(load_store()):
        print(f"{f.code}  {f.message}: {', '.join(map(str, f.ids))}")
