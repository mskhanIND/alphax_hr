"""Salary package maths for the new-employee salary step.

The usual Saudi package is Basic + Housing (a % of basic, 25% by default) +
Transport (a % of basic, 10% by default) + optional other allowances. HR
either types the total monthly package and AlphaX works out the components,
or types the components itself.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def _money(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def from_basic(basic, housing_pct, transport_pct) -> dict:
    """Housing and transport as percentages of basic."""
    b = _money(basic)
    return {"basic": b, "housing": _money(b * Decimal(str(housing_pct)) / 100),
            "transport": _money(b * Decimal(str(transport_pct)) / 100)}


def split_total(total, housing_pct, transport_pct, other=0) -> dict:
    """Split a total monthly package (minus fixed other allowances) into basic, housing and transport.

    total = basic * (1 + h% + t%) + other. Rounding differences go to basic so the
    parts always add up to the total exactly.
    """
    t = _money(total)
    o = _money(other or 0)
    if t <= 0 or o > t:
        raise ValueError("total_must_cover_other")
    factor = 1 + Decimal(str(housing_pct)) / 100 + Decimal(str(transport_pct)) / 100
    parts = from_basic((t - o) / factor, housing_pct, transport_pct)
    parts["basic"] = t - o - parts["housing"] - parts["transport"]
    parts["other"] = o
    return parts
