import pytest

from emporio.audit import audit
from emporio.data import load_store


@pytest.fixture(scope="module")
def findings():
    return {f.code: f.ids for f in audit(load_store())}


def test_only_known_findings(findings):
    assert sorted(findings) == [f"DAD-0{i}" for i in range(1, 8)]


def test_total_differs_from_items(findings):
    """DAD-01"""
    assert findings["DAD-01"] == (3, 20)


def test_pix_without_discount(findings):
    """DAD-02"""
    assert findings["DAD-02"] == (1, 5, 10, 13, 17)


def test_installment_below_minimum(findings):
    """DAD-03"""
    assert findings["DAD-03"] == (9, 16, 18)


def test_active_promotion_not_applied(findings):
    """DAD-04"""
    assert findings["DAD-04"] == (2, 11)


def test_coming_soon_in_orders(findings):
    """DAD-05"""
    assert findings["DAD-05"] == (130,)


def test_discontinued_with_stock(findings):
    """DAD-06"""
    assert findings["DAD-06"] == (136,)


def test_duplicated_email(findings):
    """DAD-07"""
    assert findings["DAD-07"] == (11, 43)
