"""Carrega e valida os CSVs da loja."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FILE_PREFIX = "desafio_tecnico_ai_eng - "

PRODUCT_STATUSES = {"active", "discontinued", "coming_soon"}
ORDER_STATUSES = {"pending", "confirmed", "shipped", "delivered", "cancelled"}
PAYMENT_RE = re.compile(r"^(pix|debit|boleto|credit_(\d{1,2})x)$")


class DataError(ValueError):
    """CSV com problema estrutural; a mensagem lista todos os problemas encontrados."""


@dataclass(frozen=True)
class Category:
    id: int
    name: str
    description: str


@dataclass(frozen=True)
class Product:
    id: int
    name: str
    category_id: int
    price: Decimal
    description: str
    stock: int
    status: str
    specs: dict
    created_at: date


@dataclass(frozen=True)
class Promotion:
    id: int
    product_id: int
    discount_percent: Decimal
    description: str
    is_active: bool


@dataclass(frozen=True)
class Customer:
    id: int
    name: str
    phone: str
    email: str
    city: str


@dataclass(frozen=True)
class OrderItem:
    product_id: int
    quantity: int


@dataclass(frozen=True)
class Order:
    id: int
    customer_id: int
    order_date: date
    status: str
    total: Decimal
    payment_method: str
    tracking_code: str | None
    estimated_delivery: date | None
    notes: str | None
    items: tuple[OrderItem, ...]

    @property
    def installments(self) -> int | None:
        """Número de parcelas no crédito; None nas outras formas."""
        match = PAYMENT_RE.match(self.payment_method)
        return int(match.group(2)) if match and match.group(2) else None


@dataclass(frozen=True)
class Store:
    categories: dict[int, Category]
    products: dict[int, Product]
    promotions: tuple[Promotion, ...]
    customers: dict[int, Customer]
    orders: dict[int, Order]


def _read(data_dir: Path, name: str) -> list[dict[str, str]]:
    with open(data_dir / f"{FILE_PREFIX}{name}.csv", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _optional(value: str) -> str | None:
    return value.strip() or None


def _index(rows, key, label: str, problems: list[str]) -> dict:
    out = {}
    for row in rows:
        k = getattr(row, key)
        if k in out:
            problems.append(f"{label} {k}: id duplicado")
        out[k] = row
    return out


def load_store(data_dir: Path = DATA_DIR) -> Store:
    """Lê os seis CSVs e valida tipos, ids e referências entre tabelas."""
    try:
        categories = [
            Category(int(r["category_id"]), r["name"], r["description"])
            for r in _read(data_dir, "categories")
        ]
        products = [
            Product(
                id=int(r["product_id"]),
                name=r["name"],
                category_id=int(r["category_id"]),
                price=Decimal(r["price_brl"]),
                description=r["description"],
                stock=int(r["stock_quantity"]),
                status=r["status"],
                specs=json.loads(r["specs"]) if r["specs"].strip() else {},
                created_at=date.fromisoformat(r["created_at"]),
            )
            for r in _read(data_dir, "products")
        ]
        promotions = tuple(
            Promotion(
                id=int(r["promotion_id"]),
                product_id=int(r["product_id"]),
                discount_percent=Decimal(r["discount_percent"]),
                description=r["description"],
                is_active=r["is_active"] == "1",
            )
            for r in _read(data_dir, "promotions")
        )
        customers = [
            Customer(int(r["customer_id"]), r["name"], r["phone"], r["email"], r["city"])
            for r in _read(data_dir, "customers")
        ]
        items: dict[int, list[OrderItem]] = {}
        for r in _read(data_dir, "order_items"):
            items.setdefault(int(r["order_id"]), []).append(
                OrderItem(int(r["product_id"]), int(r["quantity"]))
            )
        orders = [
            Order(
                id=int(r["order_id"]),
                customer_id=int(r["customer_id"]),
                order_date=date.fromisoformat(r["order_date"]),
                status=r["status"],
                total=Decimal(r["total_brl"]),
                payment_method=r["payment_method"],
                tracking_code=_optional(r["tracking_code"]),
                estimated_delivery=(
                    date.fromisoformat(r["estimated_delivery"])
                    if r["estimated_delivery"].strip()
                    else None
                ),
                notes=_optional(r["notes"]),
                items=tuple(items.pop(int(r["order_id"]), [])),
            )
            for r in _read(data_dir, "orders")
        ]
    except (KeyError, ValueError, InvalidOperation) as e:
        raise DataError(f"valor ou coluna inválida: {e!r}") from e

    problems: list[str] = []
    store = Store(
        categories=_index(categories, "id", "categoria", problems),
        products=_index(products, "id", "produto", problems),
        promotions=promotions,
        customers=_index(customers, "id", "cliente", problems),
        orders=_index(orders, "id", "pedido", problems),
    )
    problems += [f"item do pedido {oid}: pedido inexistente" for oid in items]
    problems += _check(store)
    if problems:
        raise DataError("; ".join(problems))
    return store


def _check(store: Store) -> list[str]:
    problems = []
    for p in store.products.values():
        if p.category_id not in store.categories:
            problems.append(f"produto {p.id}: categoria {p.category_id} inexistente")
        if p.status not in PRODUCT_STATUSES:
            problems.append(f"produto {p.id}: status {p.status!r} desconhecido")
        if p.price <= 0 or p.stock < 0:
            problems.append(f"produto {p.id}: preço ou estoque inválido")
    for promo in store.promotions:
        if promo.product_id not in store.products:
            problems.append(f"promoção {promo.id}: produto {promo.product_id} inexistente")
        if not 0 < promo.discount_percent < 100:
            problems.append(f"promoção {promo.id}: desconto fora de (0, 100)")
    for o in store.orders.values():
        if o.customer_id not in store.customers:
            problems.append(f"pedido {o.id}: cliente {o.customer_id} inexistente")
        if o.status not in ORDER_STATUSES:
            problems.append(f"pedido {o.id}: status {o.status!r} desconhecido")
        if not PAYMENT_RE.match(o.payment_method):
            problems.append(f"pedido {o.id}: pagamento {o.payment_method!r} desconhecido")
        if not o.items:
            problems.append(f"pedido {o.id}: sem itens")
        for item in o.items:
            if item.product_id not in store.products:
                problems.append(f"pedido {o.id}: produto {item.product_id} inexistente")
            if item.quantity <= 0:
                problems.append(f"pedido {o.id}: quantidade inválida")
    return problems
