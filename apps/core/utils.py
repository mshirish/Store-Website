"""
Pickup-window logic.

Public API:
    get_pickup_window(pickup_date, today=None) -> tuple[time, time] | None
    get_next_open_day(from_date=None)          -> date | None
    is_open_on_date(date)                      -> bool
"""
from __future__ import annotations

import datetime

READINESS_FLOOR = datetime.time(10, 0)  # 10:00 AM — applies when pickup is the very next open day
_MAX_SEARCH_DAYS = 60                   # safety limit when scanning for the next open day


def _get_base_hours(
    date: datetime.date,
) -> tuple[datetime.time, datetime.time] | None:
    """
    Returns (open_time, close_time) for a given date by:
      1. Checking StoreClosure (full closure → None; special times → use those).
      2. Falling back to the weekday row in StoreHours.
    Returns None if the store is closed that day.
    Imports are local to avoid circular-import issues during app startup.
    """
    from apps.core.models import StoreClosure, StoreHours

    try:
        closure = StoreClosure.objects.get(date=date)
        if closure.is_full_closure:
            return None
        return closure.special_open_time, closure.special_close_time
    except StoreClosure.DoesNotExist:
        pass

    weekday = date.weekday()  # 0 = Monday … 6 = Sunday
    try:
        hours = StoreHours.objects.get(weekday=weekday)
    except StoreHours.DoesNotExist:
        return None

    if hours.is_closed:
        return None
    return hours.open_time, hours.close_time


def get_next_open_day(
    from_date: datetime.date | None = None,
) -> datetime.date | None:
    """
    Returns the first open business day strictly after from_date
    (defaults to today). Searches up to _MAX_SEARCH_DAYS days ahead.
    Returns None if no open day is found within that window.
    """
    if from_date is None:
        from_date = datetime.date.today()

    candidate = from_date + datetime.timedelta(days=1)
    for _ in range(_MAX_SEARCH_DAYS):
        if _get_base_hours(candidate) is not None:
            return candidate
        candidate += datetime.timedelta(days=1)
    return None


def get_pickup_window(
    pickup_date: datetime.date,
    today: datetime.date | None = None,
) -> tuple[datetime.time, datetime.time] | None:
    """
    Returns the (window_open, window_close) for pickup_date, or None if the
    store is closed that day.

    Readiness rule: when pickup_date is the very next open day after today,
    the window cannot open earlier than READINESS_FLOOR (10:00 AM).

    Use this for both form validation (live) and snapshotting onto Order at
    placement time.
    """
    base = _get_base_hours(pickup_date)
    if base is None:
        return None

    open_time, close_time = base

    if today is None:
        today = datetime.date.today()

    next_open = get_next_open_day(today)
    if next_open == pickup_date:
        open_time = max(open_time, READINESS_FLOOR)

    return open_time, close_time


def is_open_on_date(date: datetime.date) -> bool:
    """Returns True if the store is open on the given date (any hours)."""
    return _get_base_hours(date) is not None
