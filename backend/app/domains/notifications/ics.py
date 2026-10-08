"""Minimal RFC 5545 iCalendar writer for booking invites.

Every booking keeps one stable UID; ``Booking.sequence`` increases on each change
so calendar clients replace (REQUEST) or remove (CANCEL) the event they already have.
"""

import enum
from dataclasses import dataclass
from datetime import datetime, timezone

from app.domains.email.providers import EmailAttachment

CRLF = "\r\n"
MAX_LINE_OCTETS = 75
UID_DOMAIN = "threecal.com"


class CalendarMethod(str, enum.Enum):
    REQUEST = "REQUEST"
    CANCEL = "CANCEL"


@dataclass(frozen=True)
class CalendarEvent:
    uid: str
    sequence: int
    starts_at: datetime
    ends_at: datetime
    summary: str
    description: str
    organizer_name: str
    organizer_email: str
    attendee_name: str
    attendee_email: str
    location: str | None = None
    url: str | None = None


def booking_uid(booking_id: object) -> str:
    return f"{booking_id}@{UID_DOMAIN}"


def escape_text(value: str) -> str:
    """Escape a TEXT value (RFC 5545 section 3.3.11)."""
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def _param_value(value: str) -> str:
    # Quoted parameter values cannot contain DQUOTE or control characters.
    cleaned = "".join(char for char in value if char >= " " and char != '"')
    return f'"{cleaned}"'


def fold_line(line: str) -> str:
    """Fold a content line at 75 octets without splitting UTF-8 characters."""
    encoded = line.encode()
    if len(encoded) <= MAX_LINE_OCTETS:
        return line
    parts: list[str] = []
    current = ""
    current_octets = 0
    limit = MAX_LINE_OCTETS
    for char in line:
        size = len(char.encode())
        if current_octets + size > limit:
            parts.append(current)
            current = char
            current_octets = size
            # Continuation lines start with a space, which counts toward the limit.
            limit = MAX_LINE_OCTETS - 1
        else:
            current += char
            current_octets += size
    parts.append(current)
    return (CRLF + " ").join(parts)


def _format_utc(value: datetime) -> str:
    aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return aware.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_ics(event: CalendarEvent, method: CalendarMethod, *, now: datetime | None = None) -> str:
    cancelled = method == CalendarMethod.CANCEL
    lines = [
        "BEGIN:VCALENDAR",
        "PRODID:-//threecal//threecal.com//EN",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        f"METHOD:{method.value}",
        "BEGIN:VEVENT",
        f"UID:{event.uid}",
        f"SEQUENCE:{event.sequence}",
        f"DTSTAMP:{_format_utc(now or datetime.now(timezone.utc))}",
        f"DTSTART:{_format_utc(event.starts_at)}",
        f"DTEND:{_format_utc(event.ends_at)}",
        f"SUMMARY:{escape_text(event.summary)}",
        f"DESCRIPTION:{escape_text(event.description)}",
        f"ORGANIZER;CN={_param_value(event.organizer_name)}:mailto:{event.organizer_email}",
        (
            f"ATTENDEE;CN={_param_value(event.attendee_name)};ROLE=REQ-PARTICIPANT;"
            f"PARTSTAT={'DECLINED' if cancelled else 'ACCEPTED'};RSVP=FALSE:mailto:{event.attendee_email}"
        ),
        f"STATUS:{'CANCELLED' if cancelled else 'CONFIRMED'}",
        "TRANSP:OPAQUE",
    ]
    if event.location:
        lines.append(f"LOCATION:{escape_text(event.location)}")
    if event.url:
        lines.append(f"URL:{event.url}")
    lines.extend(["END:VEVENT", "END:VCALENDAR"])
    return CRLF.join(fold_line(line) for line in lines) + CRLF


def ics_attachment(event: CalendarEvent, method: CalendarMethod) -> EmailAttachment:
    return EmailAttachment(
        filename="invite.ics" if method == CalendarMethod.REQUEST else "cancel.ics",
        content=build_ics(event, method).encode(),
        mime_type="text/calendar",
        params={"method": method.value, "charset": "UTF-8"},
    )
