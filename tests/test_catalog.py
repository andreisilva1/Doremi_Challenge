from decimal import Decimal

import pytest

from emporio import catalog
from emporio.data import load_store


@pytest.fixture(scope="module")
def store():
    return load_store()


def _ids(products):
    return [p.id for p in products]


def test_promotion_shows_original_and_percent(store):
    """PRO-02"""
    info = catalog.describe(store, store.products[127])
    assert info["preco"] == Decimal("323.10")
    assert info["preco_original"] == Decimal("359")
    assert info["desconto_percent"] == Decimal("10")
    assert info["preco_pix"] == info["preco"]


def test_ended_promotions_are_listed(store):
    """PRO-03: produto 96 teve duas promoções, nenhuma ativa."""
    info = catalog.describe(store, store.products[96])
    assert "desconto_percent" not in info
    assert info["preco"] == Decimal("799.9")
    assert sorted(info["promocoes_encerradas"]) == ["Semana do Músico", "Semana do Músico"]


def test_available_means_active_with_stock(store):
    """CAT-02"""
    assert catalog.availability(store.products[81]) == catalog.AVAILABLE


def test_out_of_stock_gets_alternatives(store):
    """CAT-03"""
    product = store.products[96]
    assert catalog.availability(product) == catalog.OUT_OF_STOCK
    alts = catalog.alternatives(store, product)
    assert alts and all(
        p.category_id == product.category_id and catalog.availability(p) == catalog.AVAILABLE
        for p in alts
    )


def test_discontinued_with_stock_is_not_sold(store):
    """CAT-04"""
    product = store.products[136]
    assert product.stock > 0
    assert catalog.availability(product) == catalog.DISCONTINUED
    assert "preco" not in catalog.describe(store, product)
    assert 136 not in _ids(catalog.search(store, limit=len(store.products)))


def test_coming_soon_is_not_sold(store):
    """CAT-05"""
    product = store.products[130]
    assert catalog.availability(product) == catalog.COMING_SOON
    assert "preco" not in catalog.describe(store, product)


def test_price_filter_uses_effective_price(store):
    """CAT-06: 127 custa 359 de tabela e 323,10 em promoção."""
    assert 127 in _ids(catalog.search(store, max_price=Decimal("330"), limit=50))


def test_unreliable_descriptions_are_hidden(store):
    """CAT-07"""
    assert "descricao" not in catalog.describe(store, store.products[135])
    assert "descricao" in catalog.describe(store, store.products[145])


def test_empty_categories(store):
    """CAT-08"""
    assert catalog.empty_categories(store) == [
        "Instrumentos de Sopro (Madeiras)",
        "Instrumentos de Sopro (Metais)",
        "Cordas Orquestrais",
    ]
    assert catalog.search(store, "saxofone") == []


@pytest.mark.parametrize("query", ["VIOLÃO yamaha", "violao Yamaha", "violões yamaha"])
def test_search_ignores_accents_case_and_plural(store, query):
    """CAT-09"""
    hits = catalog.search(store, query)
    assert hits and all("Yamaha" in p.name and p.category_id == 5 for p in hits)


def test_search_partial_name(store):
    """CAT-09"""
    assert _ids(catalog.search(store, "giannini gf-3d")) == [96]


def test_search_lists_unavailable_last(store):
    hits = catalog.search(store, "contrabaixo")
    assert hits[-1].id == 136


def test_specs_in_portuguese(store):
    info = catalog.describe(store, store.products[81])
    assert info["specs"]["tampo"] == "Spruce"
    assert info["specs"]["captação"] == "não"


def test_large_items(store):
    """FRE-04"""
    assert [p.id for p in store.products.values() if catalog.is_large_item(p)] == [139, 140, 141]
