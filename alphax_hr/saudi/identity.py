"""Saudi identity numbers and IBANs.

* National ID: 10 digits starting with 1 (Saudi citizens).
* Iqama (resident ID): 10 digits starting with 2.
* Border number: 10 digits starting with 3 or 4 (visitors / new arrivals
  before an Iqama is issued).
* Saudi IBAN: ``SA`` + 2 check digits + 20 digits (24 characters), validated
  with the ISO 13616 mod-97 check.
"""
from __future__ import annotations

SAUDI, RESIDENT, BORDER = "saudi_national_id", "iqama", "border_number"


def normalise(value) -> str:
    return "".join(str(value or "").split())


def classify_id(value) -> tuple[str | None, str | None]:
    """Return (kind, error). ``kind`` is None when the number is invalid."""
    number = normalise(value)
    if not number:
        return None, None
    if not number.isdigit():
        return None, "id_not_digits"
    if len(number) != 10:
        return None, "id_wrong_length"
    first = number[0]
    if first == "1":
        return SAUDI, None
    if first == "2":
        return RESIDENT, None
    if first in "34":
        return BORDER, None
    return None, "id_bad_prefix"


def normalise_iban(value) -> str:
    return normalise(value).upper()


def iban_error(value) -> str | None:
    """None when the IBAN is valid (or empty)."""
    iban = normalise_iban(value)
    if not iban:
        return None
    if not iban.isalnum():
        return "iban_bad_characters"
    if iban.startswith("SA") and len(iban) != 24:
        return "iban_wrong_length"
    if len(iban) < 15 or len(iban) > 34:
        return "iban_wrong_length"
    rearranged = iban[4:] + iban[:4]
    digits = "".join(str(int(ch, 36)) for ch in rearranged)
    if int(digits) % 97 != 1:
        return "iban_bad_checksum"
    return None
