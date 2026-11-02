"""Busca e apresentação de produtos. Códigos entre colchetes remetem a knowledge/rules.md."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from emporio import rules
from emporio.data import Product, Store

AVAILABLE, OUT_OF_STOCK, DISCONTINUED, COMING_SOON = (
    "disponível",
    "sem estoque",
    "fora de catálogo",
    "em breve",
)

# Descrições que contradizem nome e specs (ex.: "Music Man" descrito como Fender) [CAT-07]
UNRELIABLE_DESCRIPTION = range(135, 145)

CATEGORY_ALIASES = {2: "contrabaixo bass", 3: "percussao", 4: "piano sintetizador", 9: "uke"}

SPEC_LABELS = {
    "top": "tampo",
    "back_sides": "fundo e laterais",
    "neck": "braço",
    "body": "corpo",
    "strings": "cordas",
    "scale": "escala",
    "electronics": "captação",
    "color": "cor",
    "shells": "cascos",
    "pieces": "peças",
    "hardware": "ferragens",
    "keys": "teclas",
    "polyphony": "polifonia",
    "type": "tipo",
}
SPEC_VALUES = {"steel": "aço", "yes": "sim", "no": "não", "included": "inclusas"}

STOPWORDS = {"com", "para", "uma", "uns", "que", "tem", "voces", "quero", "algum", "alguma"}


def normalize(text: str) -> str:
    """Minúsculas e sem acento, para a busca [CAT-09]."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _stem(word: str) -> str:
    """Singular simples: violões -> violao, guitarras -> guitarra."""
    for plural, singular in (("oes", "ao"), ("aes", "ao"), ("s", "")):
        if word.endswith(plural) and len(word) > 3:
            return word[: -len(plural)] + singular
    return word


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", normalize(text))
    return {_stem(w) for w in words if len(w) > 1 and w not in STOPWORDS}


def availability(product: Product) -> str:
    """Disponível = ativo com estoque [CAT-02, CAT-04, CAT-05]."""
    if product.status == "discontinued":
        return DISCONTINUED
    if product.status == "coming_soon":
        return COMING_SOON
    return AVAILABLE if product.stock > 0 else OUT_OF_STOCK


@dataclass(frozen=True)
class Price:
    price: Decimal  # preço efetivo
    list_price: Decimal
    discount_percent: Decimal | None
    pix_price: Decimal

    @property
    def on_promotion(self) -> bool:
        return self.discount_percent is not None


def price_of(store: Store, product: Product) -> Price:
    """Preço efetivo, com o original e o percentual quando há promoção [PRO-02]."""
    discount = rules.active_discount(product.id, store.promotions)
    price = rules.promo_price(product.price, discount) if discount else product.price
    return Price(price, product.price, discount, rules.pix_price(price, discount is not None))


def _haystack(store: Store, product: Product) -> set[str]:
    category = store.categories[product.category_id]
    text = " ".join(
        [
            product.name,
            category.name,
            CATEGORY_ALIASES.get(category.id, ""),
            *(SPEC_VALUES.get(str(v).lower(), str(v)) for v in product.specs.values()),
        ]
    )
    return _tokens(text)


def _matches(query_tokens: set[str], haystack: set[str]) -> int:
    return sum(any(h.startswith(q) for h in haystack) for q in query_tokens)


def search(
    store: Store,
    query: str = "",
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    limit: int = 8,
) -> list[Product]:
    """Busca por nome, categoria e specs, tolerante a acento e plural [CAT-09].

    Sem `query`, lista só produtos disponíveis. Com `query`, inclui os indisponíveis que
    casarem, para o agente explicar o status e sugerir alternativas [CAT-03]. A faixa de
    preço usa o preço efetivo [CAT-06].
    """
    query_tokens = _tokens(query)
    scored = []
    for p in store.products.values():
        price = price_of(store, p).price
        if (min_price is not None and price < min_price) or (
            max_price is not None and price > max_price
        ):
            continue
        if query_tokens:
            score = _matches(query_tokens, _haystack(store, p))
            if score:
                scored.append((score, p))
        elif availability(p) == AVAILABLE:
            scored.append((0, p))
    if not scored:
        return []
    best = max(score for score, _ in scored)
    hits = [p for score, p in scored if score == best]
    hits.sort(key=lambda p: (availability(p) != AVAILABLE, price_of(store, p).price))
    return hits[:limit]


def alternatives(store: Store, product: Product, limit: int = 3) -> list[Product]:
    """Disponíveis da mesma categoria, do preço mais próximo [CAT-03]."""
    pool = [
        p
        for p in store.products.values()
        if p.category_id == product.category_id
        and p.id != product.id
        and availability(p) == AVAILABLE
    ]
    pool.sort(key=lambda p: abs(price_of(store, p).price - product.price))
    return pool[:limit]


def is_large_item(product: Product) -> bool:
    """Bateria acústica, piano digital ou contrabaixo acústico: frete especial [FRE-04].

    Os baixos elétricos do catálogo (descritos como "contrabaixo") não entram.
    """
    name = normalize(product.name)
    return any(k in name for k in ("bateria acustica", "piano digital", "contrabaixo acustico"))


def empty_categories(store: Store) -> list[str]:
    """Categorias sem nenhum produto [CAT-08]."""
    used = {p.category_id for p in store.products.values()}
    return [c.name for c in store.categories.values() if c.id not in used]


def price_fields(store: Store, product: Product) -> dict:
    """Preço, PIX e promoção; vazio para produto fora de catálogo ou em breve."""
    if availability(product) not in (AVAILABLE, OUT_OF_STOCK):
        return {}
    price = price_of(store, product)
    info = {"preco": price.price, "preco_pix": price.pix_price}
    if price.on_promotion:
        info |= {"preco_original": price.list_price, "desconto_percent": price.discount_percent}
    return info


def describe(store: Store, product: Product) -> dict:
    """Ficha do produto para o agente, com specs em português."""
    ended = [
        p.description for p in store.promotions if p.product_id == product.id and not p.is_active
    ]
    info = {
        "id": product.id,
        "nome": product.name,
        "categoria": store.categories[product.category_id].name,
        "status": availability(product),
        "specs": {
            SPEC_LABELS.get(k, k): SPEC_VALUES.get(str(v).lower(), v)
            for k, v in product.specs.items()
        },
    }
    info |= price_fields(store, product)
    if ended and "preco" in info:
        info["promocoes_encerradas"] = ended  # [PRO-03]
    if product.id not in UNRELIABLE_DESCRIPTION:
        info["descricao"] = product.description
    return info
