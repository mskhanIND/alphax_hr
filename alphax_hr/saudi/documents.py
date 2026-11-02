"""Expiry tracking for Iqama, passport, work permit, contracts, insurance."""
from __future__ import annotations

from datetime import date

BUCKETS = ((0, "expired"), (30, "within_30"), (60, "within_60"), (90, "within_90"))


def bucket(expiry: date | None, today: date) -> str:
    if expiry is None:
        return "missing"
    days = (expiry - today).days
    if days < 0:
        return "expired"
    for limit, name in BUCKETS[1:]:
        if days <= limit:
            return name
    return "valid"


def summarize(rows, today: date) -> dict:
    """``rows``: iterable of dicts with ``expiry`` (date or None)."""
    counts = {"expired": 0, "within_30": 0, "within_60": 0, "within_90": 0, "valid": 0, "missing": 0}
    for row in rows:
        counts[bucket(row.get("expiry"), today)] += 1
    return counts
