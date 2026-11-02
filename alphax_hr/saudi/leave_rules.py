"""Statutory special leaves (Saudi Labor Law, as amended 19 Feb 2025).

Every value is a default: sites map their own Leave Types to a rule kind and
may change the numbers. Legal basis per kind:

* Maternity      – Art. 151: 12 weeks (84 days), may start up to 4 weeks
                   before the expected delivery date.
* Paternity      – Art. 113: 3 days, within 7 days following the birth.
* Marriage       – Art. 113: 5 days.
* Bereavement    – Art. 113: 5 days for spouse, ascendant or descendant.
* Sibling death  – Art. 113 (2025): 3 days.
* Iddah          – Art. 160: Muslim widow 4 months 10 days (130 days);
                   non-Muslim widow 15 days.
* Examination    – Art. 115: paid leave for exams, proof required.
* Hajj           – Art. 114: 10-15 days including the Eid al-Adha holiday,
                   once, after two consecutive years of service.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

MATERNITY, PATERNITY, MARRIAGE = "Maternity", "Paternity", "Marriage"
BEREAVEMENT, SIBLING = "Bereavement", "Bereavement (Sibling)"
IDDAH_MUSLIM, IDDAH_OTHER = "Iddah (Muslim)", "Iddah (Non-Muslim)"
EXAM, HAJJ, SICK = "Examination", "Hajj", "Sick"
KINDS = (MATERNITY, PATERNITY, MARRIAGE, BEREAVEMENT, SIBLING, IDDAH_MUSLIM, IDDAH_OTHER, EXAM, HAJJ, SICK)

CLOSE_FAMILY = ("Spouse", "Father", "Mother", "Son", "Daughter", "Grandfather", "Grandmother", "Grandson", "Granddaughter")
SIBLINGS = ("Brother", "Sister")


@dataclass
class Rule:
    kind: str
    max_days: float | None = None
    gender: str | None = None             # "Male" / "Female" / None
    min_service_days: int | None = None
    lifetime_limit: int | None = None      # times per employment; None = unlimited
    requires_event_date: bool = False
    days_before_event: int | None = None   # leave may start this many days before the event
    days_after_event: int | None = None    # leave must end within this many days after the event
    relations: tuple[str, ...] = field(default_factory=tuple)
    requires_attachment: bool = False
    event_label: str = ""


# Typical Leave Type names (CentralHRMS and common practice) used to map
# existing sites automatically.
DEFAULT_LEAVE_TYPE_NAMES = {
    MATERNITY: ("Maternity Leave",),
    PATERNITY: ("Paternity Leave",),
    MARRIAGE: ("Marriage Leave",),
    BEREAVEMENT: ("Bereavement Leave",),
    SIBLING: ("Bereavement Leave (Sibling)", "Sibling Bereavement Leave"),
    IDDAH_MUSLIM: ("Iddah Leave (Muslim)", "Iddah Leave"),
    IDDAH_OTHER: ("Iddah Leave (Non-Muslim)",),
    EXAM: ("Examination Leave", "Exam Leave"),
    HAJJ: ("Hajj Leave",),
    SICK: ("Sick Leave",),
}


def default_rule(kind: str) -> Rule:
    if kind == MATERNITY:
        return Rule(kind, max_days=84, gender="Female", requires_event_date=True, days_before_event=28,
                    event_label="Expected delivery date")
    if kind == PATERNITY:
        return Rule(kind, max_days=3, gender="Male", requires_event_date=True, days_before_event=0,
                    days_after_event=7, event_label="Child's date of birth")
    if kind == MARRIAGE:
        return Rule(kind, max_days=5, requires_event_date=True, event_label="Marriage date")
    if kind == BEREAVEMENT:
        return Rule(kind, max_days=5, requires_event_date=True, relations=CLOSE_FAMILY, event_label="Date of death")
    if kind == SIBLING:
        return Rule(kind, max_days=3, requires_event_date=True, relations=SIBLINGS, event_label="Date of death")
    if kind == IDDAH_MUSLIM:
        return Rule(kind, max_days=130, gender="Female", requires_event_date=True, days_before_event=0,
                    event_label="Husband's date of death")
    if kind == IDDAH_OTHER:
        return Rule(kind, max_days=15, gender="Female", requires_event_date=True, days_before_event=0,
                    event_label="Husband's date of death")
    if kind == EXAM:
        return Rule(kind, requires_attachment=True, requires_event_date=True, event_label="Exam date")
    if kind == HAJJ:
        return Rule(kind, max_days=15, min_service_days=730, lifetime_limit=1)
    if kind == SICK:
        return Rule(kind, requires_attachment=True)
    raise ValueError(f"Unknown leave rule kind: {kind}")


@dataclass
class Request:
    from_date: date
    to_date: date
    total_days: float
    gender: str | None
    date_of_joining: date | None
    event_date: date | None = None
    relation: str | None = None
    previous_uses: int = 0


def check(rule: Rule, req: Request) -> list[tuple[str, dict]]:
    """Return a list of (error_code, params). Empty = allowed."""
    errors: list[tuple[str, dict]] = []
    if rule.gender and req.gender and req.gender != rule.gender:
        errors.append(("leave_gender", {"gender": rule.gender}))
    # Sick leave is limited by the 120-day sick-leave year (Art. 117), not per request.
    if rule.kind != SICK and rule.max_days and req.total_days > rule.max_days:
        errors.append(("leave_max_days", {"max": rule.max_days}))
    if rule.min_service_days and req.date_of_joining:
        served = (req.from_date - req.date_of_joining).days
        if served < rule.min_service_days:
            errors.append(("leave_min_service", {"days": rule.min_service_days}))
    if rule.lifetime_limit is not None and req.previous_uses >= rule.lifetime_limit:
        errors.append(("leave_lifetime_limit", {"times": rule.lifetime_limit}))
    if rule.relations:
        if not req.relation:
            errors.append(("leave_relation_required", {}))
        elif req.relation not in rule.relations:
            errors.append(("leave_relation_not_allowed", {"allowed": ", ".join(rule.relations)}))
    if rule.requires_event_date and not req.event_date:
        errors.append(("leave_event_date_required", {"label": rule.event_label or "Event date"}))
    if req.event_date:
        if rule.days_before_event is not None and req.from_date < req.event_date - timedelta(days=rule.days_before_event):
            errors.append(("leave_too_early", {"days": rule.days_before_event, "label": rule.event_label}))
        if rule.days_after_event is not None and req.to_date > req.event_date + timedelta(days=rule.days_after_event):
            errors.append(("leave_too_late", {"days": rule.days_after_event, "label": rule.event_label}))
    return errors


def sick_cycle_usage(previous: list[tuple[date, float]], new_from: date) -> tuple[date, float]:
    """Find the sick-leave year that ``new_from`` falls in and the days already used in it.

    Art. 117 counts the 120 days within one year starting from the *first*
    sick day. ``previous`` is a list of (from_date, days) for earlier sick
    leave. Returns (cycle_start, days_used_in_cycle).
    """
    anchor = None
    used = 0.0
    for start, days in sorted(previous):
        if start >= new_from:
            break
        if anchor is None or start >= anchor + timedelta(days=365):
            anchor, used = start, 0.0
        used += float(days)
    if anchor is None or new_from >= anchor + timedelta(days=365):
        return new_from, 0.0
    return anchor, used
