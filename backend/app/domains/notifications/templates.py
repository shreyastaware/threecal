"""Booking email content. Each builder returns ``EmailContent`` rendered by the shared layout."""

from dataclasses import dataclass
from datetime import datetime

from app.core.config import settings
from app.domains.bookings.models import Booking, CancelledBy
from app.domains.bookings.repository import as_utc
from app.domains.email.templates import EmailContent
from app.domains.event_types.models import EventType
from app.domains.notifications.formatting import (
    format_amount,
    format_duration,
    format_offset,
    format_short_date,
    format_when,
)
from app.domains.users.models import User


@dataclass(frozen=True)
class BookingContext:
    booking: Booking
    event_type: EventType
    host: User
    # Invitee's self-service link; None when self-service is disabled.
    manage_url: str | None

    @property
    def starts_at(self) -> datetime:
        return as_utc(self.booking.starts_at)

    @property
    def ends_at(self) -> datetime:
        return as_utc(self.booking.ends_at)

    @property
    def duration_minutes(self) -> int:
        return int((self.ends_at - self.starts_at).total_seconds() // 60)

    @property
    def is_paid(self) -> bool:
        return bool(self.booking.provider_payment_id) and self.booking.booking_amount > 0

    @property
    def amount(self) -> str:
        return format_amount(self.booking.booking_amount, self.event_type.currency)

    @property
    def dashboard_url(self) -> str:
        return f"{settings.frontend_url.rstrip('/')}/dashboard/bookings"

    @property
    def rebook_url(self) -> str | None:
        if not self.host.username:
            return None
        return f"{settings.frontend_url.rstrip('/')}/{self.host.username}/{self.event_type.slug}"


def _policy_line() -> str:
    hours = settings.invitee_change_cutoff_hours
    return f"You can reschedule or cancel online until {hours} hours before the start."


def _invitee_details(ctx: BookingContext, when_label: str = "When") -> list[tuple[str, str]]:
    booking = ctx.booking
    details = [
        (when_label, format_when(ctx.starts_at, ctx.ends_at, booking.invitee_timezone)),
        ("Event", ctx.event_type.title),
        ("Duration", format_duration(ctx.duration_minutes)),
        ("Host", ctx.host.full_name),
    ]
    if booking.meeting_url:
        details.append(("Meeting link", booking.meeting_url))
    if booking.notes:
        details.append(("Your notes", booking.notes))
    if ctx.is_paid:
        details.append(("Amount paid", ctx.amount))
    return details


def _host_details(ctx: BookingContext, when_label: str = "When") -> list[tuple[str, str]]:
    booking = ctx.booking
    details = [
        (when_label, format_when(ctx.starts_at, ctx.ends_at, ctx.host.timezone)),
        ("Event", ctx.event_type.title),
        ("Duration", format_duration(ctx.duration_minutes)),
        ("Invitee", booking.invitee_name),
        ("Invitee email", booking.invitee_email),
        ("Invitee timezone", booking.invitee_timezone),
    ]
    if booking.meeting_url:
        details.append(("Meeting link", booking.meeting_url))
    if booking.notes:
        details.append(("Notes", booking.notes))
    if ctx.is_paid:
        details.append(("Amount paid", ctx.amount))
    return details


def _invitee_links(ctx: BookingContext) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    if ctx.booking.meeting_url:
        links.append(("Join meeting", ctx.booking.meeting_url))
    if ctx.manage_url:
        links.append(("Reschedule or cancel", ctx.manage_url))
    return links


def invitee_confirmation(ctx: BookingContext) -> EmailContent:
    booking = ctx.booking
    paragraphs = [
        f"Hi {booking.invitee_name},",
        f"Your {ctx.event_type.title} with {ctx.host.full_name} is booked. A calendar invite is attached.",
    ]
    if ctx.manage_url:
        paragraphs.append(_policy_line())
    return EmailContent(
        subject=f"Confirmed: {ctx.event_type.title} with {ctx.host.full_name} on {format_short_date(ctx.starts_at, booking.invitee_timezone)}",
        heading="Your booking is confirmed",
        preheader=format_when(ctx.starts_at, ctx.ends_at, booking.invitee_timezone),
        paragraphs=paragraphs,
        details=_invitee_details(ctx),
        action=("Manage booking", ctx.manage_url) if ctx.manage_url else None,
        links=_invitee_links(ctx),
    )


def host_new_booking(ctx: BookingContext) -> EmailContent:
    booking = ctx.booking
    return EmailContent(
        subject=f"New booking: {booking.invitee_name} – {ctx.event_type.title} on {format_short_date(ctx.starts_at, ctx.host.timezone)}",
        heading="You have a new booking",
        preheader=format_when(ctx.starts_at, ctx.ends_at, ctx.host.timezone),
        paragraphs=[f"{booking.invitee_name} booked {ctx.event_type.title} with you."],
        details=_host_details(ctx),
        action=("View in dashboard", ctx.dashboard_url),
        links=[("Join meeting", booking.meeting_url)] if booking.meeting_url else [],
    )


def _canceller(ctx: BookingContext, *, for_host: bool) -> str:
    cancelled_by = ctx.booking.cancelled_by
    if cancelled_by == CancelledBy.HOST.value:
        return "You" if for_host else ctx.host.full_name
    if cancelled_by == CancelledBy.INVITEE.value:
        return ctx.booking.invitee_name if for_host else "You"
    return "The booking"


def _refund_line(ctx: BookingContext, *, for_host: bool) -> str | None:
    booking = ctx.booking
    if booking.booking_amount <= 0 or not booking.provider_payment_id:
        return None
    if booking.refund_id:
        if for_host:
            return f"{booking.invitee_name} has been refunded {ctx.amount} in full."
        return f"A full refund of {ctx.amount} has been issued to your original payment method. It usually arrives within 5–7 business days."
    return None


def cancellation(ctx: BookingContext, *, for_host: bool) -> EmailContent:
    booking = ctx.booking
    who = _canceller(ctx, for_host=for_host)
    timezone_name = ctx.host.timezone if for_host else booking.invitee_timezone
    other = booking.invitee_name if for_host else ctx.host.full_name
    paragraphs = [f"{who} cancelled this booking." if who != "The booking" else "This booking was cancelled."]
    refund = _refund_line(ctx, for_host=for_host)
    if refund:
        paragraphs.append(refund)
    details = [
        ("Was scheduled for", format_when(ctx.starts_at, ctx.ends_at, timezone_name)),
        ("Event", ctx.event_type.title),
        ("Invitee" if for_host else "Host", other),
    ]
    if booking.cancellation_reason:
        details.append(("Reason", booking.cancellation_reason))
    if refund:
        details.append(("Refund", ctx.amount))
    rebook = None if for_host else ctx.rebook_url
    return EmailContent(
        subject=f"Cancelled: {ctx.event_type.title} with {other} on {format_short_date(ctx.starts_at, timezone_name)}",
        heading="Booking cancelled",
        paragraphs=paragraphs,
        details=details,
        action=("Book another time", rebook) if rebook else (("View bookings", ctx.dashboard_url) if for_host else None),
    )


def reschedule(ctx: BookingContext, previous_starts_at: datetime, previous_ends_at: datetime, *, for_host: bool, rescheduled_by: str | None) -> EmailContent:
    booking = ctx.booking
    timezone_name = ctx.host.timezone if for_host else booking.invitee_timezone
    other = booking.invitee_name if for_host else ctx.host.full_name
    if rescheduled_by == CancelledBy.HOST.value:
        who = "You" if for_host else ctx.host.full_name
    elif rescheduled_by == CancelledBy.INVITEE.value:
        who = booking.invitee_name if for_host else "You"
    else:
        who = "Your booking"
    paragraphs = [f"{who} moved this booking to a new time." if who != "Your booking" else "This booking was moved to a new time."]
    if not for_host and ctx.manage_url:
        paragraphs.append(_policy_line())
    details = _host_details(ctx, "New time") if for_host else _invitee_details(ctx, "New time")
    details.insert(1, ("Previous time", format_when(previous_starts_at, previous_ends_at, timezone_name)))
    return EmailContent(
        subject=f"Rescheduled: {ctx.event_type.title} with {other} – now {format_short_date(ctx.starts_at, timezone_name)}",
        heading="Booking rescheduled",
        preheader=format_when(ctx.starts_at, ctx.ends_at, timezone_name),
        paragraphs=paragraphs,
        details=details,
        action=("View in dashboard", ctx.dashboard_url) if for_host else (("Manage booking", ctx.manage_url) if ctx.manage_url else None),
        links=([("Join meeting", booking.meeting_url)] if booking.meeting_url else []) if for_host else _invitee_links(ctx),
    )


def reminder(ctx: BookingContext, offset_minutes: int, *, for_host: bool) -> EmailContent:
    booking = ctx.booking
    timezone_name = ctx.host.timezone if for_host else booking.invitee_timezone
    other = booking.invitee_name if for_host else ctx.host.full_name
    lead = format_offset(offset_minutes)
    return EmailContent(
        subject=f"Reminder: {ctx.event_type.title} with {other} {lead}",
        heading=f"Your booking starts {lead}",
        preheader=format_when(ctx.starts_at, ctx.ends_at, timezone_name),
        paragraphs=[f"This is a reminder of your {ctx.event_type.title} with {other}."],
        details=_host_details(ctx) if for_host else _invitee_details(ctx),
        action=(("Join meeting", booking.meeting_url) if booking.meeting_url else ("View in dashboard", ctx.dashboard_url))
        if for_host
        else (("Join meeting", booking.meeting_url) if booking.meeting_url else (("Manage booking", ctx.manage_url) if ctx.manage_url else None)),
        links=[] if for_host else ([("Reschedule or cancel", ctx.manage_url)] if ctx.manage_url else []),
    )
