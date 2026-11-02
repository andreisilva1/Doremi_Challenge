from datetime import date

import pytest

from emporio import orders
from emporio.config import reference_date
from emporio.data import load_store

TODAY = date(2026, 3, 23)


@pytest.fixture(scope="module")
def store():
    return load_store()


@pytest.mark.parametrize(
    "contact",
    [
        "leticia.rocha@jmail.com",
        " LETICIA.ROCHA@jmail.com ",
        "(67) 99789-0123",
        "67997890123",
        "+55 67 99789-0123",
        "99789-0123",
    ],
)
def test_verify_with_email_or_phone(store, contact):
    """PED-01: pedido 7 é da cliente 14."""
    assert orders.verify(store, 7, contact).id == 7


@pytest.mark.parametrize(
    ("order_id", "contact"),
    [(7, "lucas.mendes@jmail.com"), (7, "(67) 99812-3456"), (7, "0123"), (999, "x@y.com")],
)
def test_verification_fails_without_leaking(store, order_id, contact):
    """LGPD-01: e-mail de outro cliente, telefone incompleto ou pedido inexistente."""
    assert orders.verify(store, order_id, contact) is None


def test_duplicated_email_only_opens_own_orders(store):
    """LGPD-01: clientes 11 e 43 dividem o e-mail; o pedido 10 é do 11."""
    email = store.customers[43].email
    assert orders.verify(store, 10, email).customer_id == 11
    assert all(o.customer_id != 43 for o in store.orders.values())


def test_status_labels(store):
    """PED-02"""
    assert orders.describe(store, store.orders[13], TODAY)["status"] == "aguardando pagamento"
    assert "em preparação" in orders.describe(store, store.orders[9], TODAY)["status"]


def test_late_shipment(store):
    """PED-03: pedido 8 enviado com previsão em 28/02."""
    assert orders.describe(store, store.orders[8], TODAY)["atrasado"]
    assert not orders.is_late(store.orders[8], date(2026, 2, 28))


def test_total_as_registered(store):
    """PED-04: pedido 3 registra 3450, embora os itens somem 3498."""
    assert orders.describe(store, store.orders[3], TODAY)["total"] == 3450


def test_reference_date_default(monkeypatch):
    """PED-05"""
    monkeypatch.delenv("REFERENCE_DATE", raising=False)
    assert reference_date() == TODAY
    monkeypatch.setenv("REFERENCE_DATE", "2026-04-01")
    assert reference_date() == date(2026, 4, 1)


def test_cancelled_order_shows_reason(store):
    info = orders.describe(store, store.orders[18], TODAY)
    assert info["status"] == "cancelado"
    assert info["observacao"] == "Item fora de estoque no momento do pedido"
