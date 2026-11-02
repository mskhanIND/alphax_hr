from decimal import Decimal

import pytest

from alphax_hr.saudi.salary import from_basic, split_total


def test_from_basic():
    p = from_basic(10000, 25, 10)
    assert p == {"basic": Decimal("10000.00"), "housing": Decimal("2500.00"), "transport": Decimal("1000.00")}


def test_split_total_adds_up_exactly():
    p = split_total(13500, 25, 10)
    assert p["basic"] == Decimal("10000.00") and p["housing"] == Decimal("2500.00") and p["transport"] == Decimal("1000.00")
    odd = split_total(9999.99, 25, 10, other=500)
    assert odd["basic"] + odd["housing"] + odd["transport"] + odd["other"] == Decimal("9999.99")
    assert odd["other"] == Decimal("500.00")


def test_split_total_rejects_bad_input():
    with pytest.raises(ValueError):
        split_total(0, 25, 10)
    with pytest.raises(ValueError):
        split_total(1000, 25, 10, other=2000)
