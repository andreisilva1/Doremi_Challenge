"""Ferramentas do agente: funções puras que devolvem fichas prontas para o LLM redigir.

Toda conta, prazo e verificação acontece aqui ou nos módulos de regras; o LLM só escolhe a
ferramenta e os argumentos. Valores saem formatados (R$ 1.234,56 e dd/mm/aaaa) para o modelo
não reformatar. As docstrings são a descrição que o LLM lê.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Literal, TypedDict

from emporio import catalog, orders, rules
from emporio.config import reference_date, store_timezone
from emporio.data import Store, load_store

POLICIES = Path(__file__).resolve().parent.parent / "knowledge" / "policies.md"

Topic = Literal[
    "loja",
    "horario",
    "pagamento",
    "trocas",
    "frete",
    "promocoes",
    "atendimento",
    "garantia",
    "privacidade",
]
TOPIC_SECTIONS: dict[str, str] = {
    "loja": "§1",
    "horario": "§2",
    "pagamento": "§3",
    "trocas": "§4",
    "frete": "§5",
    "promocoes": "§6",
    "atendimento": "§7",
    "garantia": "§8",
    "privacidade": "§9",
}
WEEKDAYS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")

NOT_VERIFIED = (
    "Não foi possível confirmar o pedido com esses dados. Peça ao cliente para conferir o número "
    "do pedido e o e-mail ou telefone do cadastro, sem dizer qual dado não bateu."
)


class Item(TypedDict):
    product_id: int
    quantity: int


@cache
def store() -> Store:
    return load_store()


def brl(value: Decimal) -> str:
    """R$ 1.234,56 [PAG-09]."""
    text = f"{rules.round_brl(value):,.2f}"
    return "R$ " + text.replace(",", "_").replace(".", ",").replace("_", ".")


def _format(value, key: str = ""):
    """Decimal vira R$ (ou % nas chaves de percentual) e data vira dd/mm/aaaa."""
    if isinstance(value, dict):
        return {k: _format(v, k) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_format(v, key) for v in value]
    if isinstance(value, Decimal):
        return f"{value.normalize():f}%" if key.endswith("percent") else brl(value)
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return value


def _summary(product) -> dict:
    s = store()
    info = {"id": product.id, "nome": product.name, "status": catalog.availability(product)}
    if info["status"] in (catalog.AVAILABLE, catalog.OUT_OF_STOCK):
        price = catalog.price_of(s, product)
        info["preco"] = price.price
        info["preco_pix"] = price.pix_price
        if price.on_promotion:
            info["preco_original"] = price.list_price
            info["desconto_percent"] = price.discount_percent
    return info


def _installments(price: Decimal) -> str:
    n = rules.max_installments(price)
    return f"até {n}x de {brl(price / n)} sem juros"


def search_products(
    query: str = "", min_price: float | None = None, max_price: float | None = None
) -> dict:
    """Busca instrumentos no catálogo por nome, marca, tipo ou característica.

    Use sempre antes de falar de qualquer produto, preço ou estoque. `query` aceita termos como
    "violão Yamaha" ou "bateria eletrônica"; os preços filtram pelo preço atual em reais.
    Sem `query`, lista instrumentos disponíveis na faixa de preço.
    """
    s = store()
    hits = catalog.search(
        s,
        query,
        min_price=Decimal(str(min_price)) if min_price is not None else None,
        max_price=Decimal(str(max_price)) if max_price is not None else None,
    )
    result: dict = {"resultados": [_summary(p) for p in hits]}
    if not hits:
        result["observacao"] = (
            "Nada encontrado. A loja vende só instrumentos (sem acessórios) e hoje não tem "
            "produtos nestas categorias: " + ", ".join(catalog.empty_categories(s)) + "."
        )
    return _format(result)


def get_product(product_id: int) -> dict:
    """Ficha completa de um produto pelo id: preço, PIX, parcelamento, promoção, estoque e specs.

    Para produto sem estoque, fora de catálogo ou em breve, traz alternativas disponíveis.
    """
    s = store()
    product = s.products.get(product_id)
    if product is None:
        return {"erro": f"produto {product_id} não existe; use search_products"}
    info = catalog.describe(s, product)
    if "preco" in info:
        info["cartao_credito"] = _installments(info["preco"])
    if info["status"] != catalog.AVAILABLE:
        info["alternativas"] = [_summary(p) for p in catalog.alternatives(s, product)]
    return _format(info)


def quote(items: list[Item], city: str | None = None) -> dict:
    """Calcula o total de uma compra: PIX, parcelamento no cartão e frete para a cidade.

    `items` são os produtos (id e quantidade). Informe `city` para calcular o frete.
    """
    s = store()
    lines, names, large = [], [], False
    for item in items:
        product = s.products.get(item["product_id"])
        if product is None or catalog.availability(product) != catalog.AVAILABLE:
            return {"erro": f"produto {item['product_id']} não está disponível para venda"}
        if item["quantity"] < 1 or item["quantity"] > product.stock:
            return {
                "erro": f"quantidade indisponível para {product.name} (estoque: {product.stock})"
            }
        price = catalog.price_of(s, product)
        lines.append((price.price, price.on_promotion, item["quantity"]))
        names.append(f"{item['quantity']}x {product.name}")
        large = large or catalog.is_large_item(product)
    if not lines:
        return {"erro": "nenhum item informado"}
    pay = rules.quote_payment(lines)
    result: dict = {
        "itens": names,
        "total": pay.total,
        "total_pix": pay.pix_total,
        "cartao_credito": _installments(pay.total),
        "debito_ou_boleto": pay.total,
        "pode_combinar_formas": pay.can_combine,
    }
    if pay.pix_total == pay.total:
        result["observacao_pix"] = "itens em promoção não têm o desconto extra do PIX"
    if city:
        ship = rules.shipping_quote(city, pay.total, large)
        result["frete"] = {
            "modalidades": [f"{name}: {days}" for name, days in ship.options],
            "valor": ship.fee if ship.local else "calculado no checkout pelo CEP, peso e dimensões",
        }
        if ship.special_freight:
            result["frete"]["frete_especial"] = (
                "item de grande porte: frete especial com cotação individual pela equipe"
            )
    return _format(result)


def get_order(order_id: int, contact: str) -> dict:
    """Status, itens, rastreio e previsão de entrega de um pedido.

    Exige o número do pedido e o e-mail ou telefone do cadastro, informados pelo cliente nesta
    conversa. Nunca invente nem reaproveite dados de outro cliente.
    """
    order = orders.verify(store(), order_id, contact)
    if order is None:
        return {"erro": NOT_VERIFIED}
    return _format(orders.describe(store(), order, reference_date()))


def check_return(
    order_id: int, contact: str, kind: Literal["arrependimento", "defeito", "preferencia"]
) -> dict:
    """Verifica se um pedido pode ser devolvido ou trocado hoje, com o prazo e as condições.

    `kind`: "arrependimento" (desistiu da compra online), "defeito" (problema de fabricação) ou
    "preferencia" (quer trocar por outro modelo). Exige pedido e e-mail ou telefone do cadastro.
    """
    order = orders.verify(store(), order_id, contact)
    if order is None:
        return {"erro": NOT_VERIFIED}
    check = rules.check_return(order, kind, reference_date())
    result: dict = {"pedido": order.id, "tipo": kind, "condicoes": check.reason}
    if check.eligible is None:
        result["elegivel"] = "encaminhar para a equipe"
    else:
        result["elegivel"] = check.eligible
    if check.deadline:
        result["prazo_ate"] = check.deadline
    if warranty := rules.legal_warranty_until(order):
        result["garantia_legal_ate"] = warranty
    return _format(result)


def _when(moment: datetime, today: date) -> str:
    if moment.date() == today:
        day = "hoje"
    elif (moment.date() - today).days == 1:
        day = "amanhã"
    else:
        day = f"{WEEKDAYS[moment.weekday()]} ({moment:%d/%m})"
    return f"{day} às {moment:%H:%M}"


def store_status() -> dict:
    """Diz se a loja está aberta agora, quando fecha ou quando abre, e endereço e contatos."""
    return store_status_at(datetime.now(store_timezone()))


def store_status_at(now: datetime) -> dict:
    status = rules.store_status(now)
    result: dict = {
        "agora": now,
        "aberta": status.is_open,
        "horario": "segunda a sexta 09:00–18:00, sábado 09:00–13:00, fechada domingo e feriados",
        **rules.STORE_INFO,
    }
    if name := rules.holiday(now.date()):
        result["feriado_hoje"] = name
    if status.is_open:
        result["fecha"] = _when(status.closes_at, now.date())
    else:
        result["abre"] = _when(status.next_opening, now.date())
    return _format(result)


def get_policy(topic: Topic) -> str:
    """Texto do manual da loja sobre um tema, para dúvidas de política que as outras ferramentas
    não cobrem (ex.: itens que não podem ser trocados, o que a garantia não cobre, LGPD)."""
    return _policy_sections()[TOPIC_SECTIONS[topic]]


@cache
def _policy_sections() -> dict[str, str]:
    """Seções `## §N` do manual, sem as notas 🟡 (interpretações internas)."""
    text = POLICIES.read_text(encoding="utf-8")
    sections = {}
    for chunk in re.split(r"^(?=## §)", text, flags=re.MULTILINE)[1:]:
        paragraphs = [p for p in chunk.strip().split("\n\n") if not p.startswith("🟡")]
        sections[chunk.split()[1]] = "\n\n".join(paragraphs)
    return sections


def handoff_to_human(reason: str) -> dict:
    """Encaminha para a equipe: reclamação, pedido não entregue com problema, exclusão de dados,
    ou qualquer caso que as ferramentas não resolvem."""
    return {
        "encaminhado": True,
        "motivo": reason,
        "retorno": rules.COMPLAINT_RESPONSE,
        "whatsapp": rules.STORE_INFO["whatsapp"],
        "email": rules.STORE_INFO["email"],
    }


TOOLS = [
    search_products,
    get_product,
    quote,
    get_order,
    check_return,
    store_status,
    get_policy,
    handoff_to_human,
]
