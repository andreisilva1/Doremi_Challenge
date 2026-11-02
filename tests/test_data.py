import shutil
from datetime import date
from decimal import Decimal

import pytest

from emporio.data import DATA_DIR, FILE_PREFIX, DataError, load_store


@pytest.fixture(scope="module")
def store():
    return load_store()


def test_loads_all_tables(store):
    assert len(store.categories) == 9
    assert len(store.products) == 65
    assert len(store.promotions) == 25
    assert len(store.customers) == 50
    assert len(store.orders) == 20
    assert sum(len(o.items) for o in store.orders.values()) == 22


def test_parses_types(store):
    p = store.products[81]
    assert p.price == Decimal("599.9")
    assert p.specs["top"] == "Spruce"
    assert p.created_at == date(2021, 3, 15)
    o = store.orders[3]
    assert o.items[0].quantity == 2
    assert o.estimated_delivery == date(2025, 12, 5)
    assert store.orders[9].tracking_code is None


@pytest.mark.parametrize(
    ("order_id", "installments"), [(1, None), (4, None), (8, None), (3, 12), (7, 3)]
)
def test_installments(store, order_id, installments):
    assert store.orders[order_id].installments == installments


@pytest.fixture
def data_copy(tmp_path):
    for f in DATA_DIR.glob("*.csv"):
        shutil.copy(f, tmp_path)
    return tmp_path


def _edit(data_dir, table, old, new):
    path = data_dir / f"{FILE_PREFIX}{table}.csv"
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


@pytest.mark.parametrize(
    ("table", "old", "new", "message"),
    [
        ("orders", "1,3,2025-10-15", "1,999,2025-10-15", "cliente 999 inexistente"),
        ("order_items", "1,1,93", "1,1,9999", "produto 9999 inexistente"),
        ("orders", "delivered,11499", "lost,11499", "status 'lost'"),
        ("orders", "11499,pix", "11499,cheque", "pagamento 'cheque'"),
        ("products", "82,849", "81,849", "produto 81: id duplicado"),
        ("promotions", "1,102,10", "1,102,0", "desconto fora"),
    ],
)
def test_rejects_broken_data(data_copy, table, old, new, message):
    _edit(data_copy, table, old, new)
    with pytest.raises(DataError, match=message):
        load_store(data_copy)


def test_rejects_unparseable_value(data_copy):
    _edit(data_copy, "orders", "11499,pix", "abc,pix")
    with pytest.raises(DataError, match="valor ou coluna inválida"):
        load_store(data_copy)
