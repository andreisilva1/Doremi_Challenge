"""Consulta de pedidos com verificação de identidade. Códigos remetem a knowledge/rules.md."""

from __future__ import annotations

import re
from datetime import date

from emporio.data import Order, Store

STATUS_LABELS = {  # [PED-02]
    "pending": "aguardando pagamento",
    "confirmed": "pagamento confirmado, em preparação",
    "shipped": "enviado",
    "delivered": "entregue",
    "cancelled": "cancelado",
}
PAYMENT_LABELS = {"pix": "PIX", "debit": "cartão de débito", "boleto": "boleto"}


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def _same_phone(given: str, registered: str) -> bool:
    given, registered = _digits(given), _digits(registered)
    if len(given) == 13 and given.startswith("55"):
        given = given[2:]
    if len(given) == 11:
        return given == registered
    return len(given) == 9 and registered.endswith(given)


def verify(store: Store, order_id: int, contact: str) -> Order | None:
    """Pedido, se o e-mail ou telefone for do cliente do pedido [PED-01].

    Qualquer falha devolve None, sem dizer se o pedido existe ou qual dado não bateu [LGPD-01].
    """
    order = store.orders.get(order_id)
    if order is None:
        return None
    customer = store.customers[order.customer_id]
    contact = contact.strip()
    if "@" in contact:
        ok = contact.lower() == customer.email.strip().lower()
    else:
        ok = _same_phone(contact, customer.phone)
    return order if ok else None


def payment_label(order: Order) -> str:
    n = order.installments
    return f"cartão de crédito em {n}x" if n else PAYMENT_LABELS[order.payment_method]


def is_late(order: Order, today: date) -> bool:
    """Enviado com previsão de entrega já vencida [PED-03]."""
    return (
        order.status == "shipped"
        and order.estimated_delivery is not None
        and order.estimated_delivery < today
    )


def describe(store: Store, order: Order, today: date) -> dict:
    """Resumo do pedido para o agente; o total vai como registrado [PED-04]."""
    info = {
        "pedido": order.id,
        "cliente": store.customers[order.customer_id].name,
        "data": order.order_date,
        "status": STATUS_LABELS[order.status],
        "itens": [
            {"produto": store.products[i.product_id].name, "quantidade": i.quantity}
            for i in order.items
        ],
        "total": order.total,
        "pagamento": payment_label(order),
    }
    if order.tracking_code:
        info["rastreio"] = order.tracking_code
    if order.estimated_delivery:
        key = "entregue_em" if order.status == "delivered" else "previsao_entrega"
        info[key] = order.estimated_delivery
    if is_late(order, today):
        info["atrasado"] = True
    if order.notes:
        info["observacao"] = order.notes
    return info
