"""Human-readable dates, durations and amounts for notification emails."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}


def _zone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _clock(value: datetime) -> str:
    hour = value.hour % 12 or 12
    return f"{hour}:{value.minute:02d} {'AM' if value.hour < 12 else 'PM'}"


def _gmt_offset(value: datetime) -> str:
    offset = value.utcoffset()
    if not offset:
        return "GMT"
    minutes = int(offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    hours, remainder = divmod(abs(minutes), 60)
    return f"GMT{sign}{hours}" + (f":{remainder:02d}" if remainder else "")


def format_date(value: datetime, timezone_name: str) -> str:
    local = _aware(value).astimezone(_zone(timezone_name))
    return f"{local:%A}, {local.day} {local:%B} {local.year}"


def format_short_date(value: datetime, timezone_name: str) -> str:
    local = _aware(value).astimezone(_zone(timezone_name))
    return f"{local:%a} {local.day} {local:%b}, {_clock(local)}"


def format_when(starts_at: datetime, ends_at: datetime, timezone_name: str) -> str:
    """e.g. "Tuesday, 14 October 2026, 3:30 PM – 4:00 PM (Asia/Kolkata, GMT+5:30)"."""
    zone = _zone(timezone_name)
    start = _aware(starts_at).astimezone(zone)
    end = _aware(ends_at).astimezone(zone)
    return f"{format_date(start, timezone_name)}, {_clock(start)} – {_clock(end)} ({zone.key}, {_gmt_offset(start)})"


def format_duration(minutes: int) -> str:
    hours, remainder = divmod(minutes, 60)
    if not hours:
        return f"{minutes} minutes"
    hour_label = f"{hours} hour" + ("" if hours == 1 else "s")
    return hour_label if not remainder else f"{hour_label} {remainder} minutes"


def format_amount(amount_minor: int, currency: str) -> str:
    code = currency.upper()
    symbol = CURRENCY_SYMBOLS.get(code)
    value = f"{amount_minor / 100:,.2f}"
    return f"{symbol}{value}" if symbol else f"{code} {value}"


def format_offset(minutes: int) -> str:
    """Relative lead time of a reminder, e.g. "in 24 hours" or "in 1 hour"."""
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"in {hours} hour" + ("" if hours == 1 else "s")
    return f"in {minutes} minutes"
