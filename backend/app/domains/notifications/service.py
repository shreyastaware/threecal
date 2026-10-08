import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.domains.bookings.manage_token import manage_url
from app.domains.bookings.models import Booking, BookingStatus
from app.domains.bookings.repository import BookingRepository, as_utc, utc_now
from app.domains.email.providers import EmailAttachment
from app.domains.email.service import EmailService
from app.domains.email.templates import EmailContent, render_email
from app.domains.event_types.models import EventType
from app.domains.notifications import templates
from app.domains.notifications.ics import CalendarEvent, CalendarMethod, booking_uid, ics_attachment
from app.domains.notifications.repository import BookingReminderRepository
from app.domains.notifications.templates import BookingContext
from app.domains.users.models import User

logger = logging.getLogger(__name__)


class BookingNotificationService:
    """Builds and sends booking emails to the invitee and the host.

    Each recipient is sent independently, so one failing address does not stop the other.
    """

    def __init__(self, db: Session, email: EmailService) -> None:
        self.db = db
        self.email = email

    def load(self, booking_id: uuid.UUID) -> BookingContext | None:
        booking = self.db.get(Booking, booking_id)
        if booking is None:
            return None
        event_type = self.db.get(EventType, booking.event_type_id)
        host = self.db.get(User, booking.host_id)
        if event_type is None or host is None:
            return None
        return BookingContext(booking=booking, event_type=event_type, host=host, manage_url=manage_url(booking))

    # Event entry points ------------------------------------------------------

    def booking_confirmed(self, booking_id: uuid.UUID) -> None:
        ctx = self.load(booking_id)
        if ctx is None or ctx.booking.status != BookingStatus.CONFIRMED:
            return
        self._send_invitee(ctx, templates.invitee_confirmation(ctx), CalendarMethod.REQUEST)
        self._send_host(ctx, templates.host_new_booking(ctx), CalendarMethod.REQUEST)

    def booking_cancelled(self, booking_id: uuid.UUID) -> None:
        ctx = self.load(booking_id)
        if ctx is None or ctx.booking.status != BookingStatus.CANCELLED:
            return
        self._send_invitee(ctx, templates.cancellation(ctx, for_host=False), CalendarMethod.CANCEL)
        self._send_host(ctx, templates.cancellation(ctx, for_host=True), CalendarMethod.CANCEL)

    def booking_rescheduled(
        self,
        booking_id: uuid.UUID,
        previous_starts_at: datetime,
        previous_ends_at: datetime,
        rescheduled_by: str | None,
    ) -> None:
        ctx = self.load(booking_id)
        if ctx is None or ctx.booking.status != BookingStatus.CONFIRMED:
            return
        self._send_invitee(
            ctx,
            templates.reschedule(ctx, previous_starts_at, previous_ends_at, for_host=False, rescheduled_by=rescheduled_by),
            CalendarMethod.REQUEST,
        )
        self._send_host(
            ctx,
            templates.reschedule(ctx, previous_starts_at, previous_ends_at, for_host=True, rescheduled_by=rescheduled_by),
            CalendarMethod.REQUEST,
        )

    def send_reminder(self, ctx: BookingContext, offset_minutes: int) -> None:
        """Send both reminders; raises if neither could be delivered."""
        delivered = self._send_invitee(ctx, templates.reminder(ctx, offset_minutes, for_host=False), None)
        delivered = self._send_host(ctx, templates.reminder(ctx, offset_minutes, for_host=True), None) or delivered
        if not delivered:
            raise RuntimeError("reminder delivery failed")

    # Delivery ---------------------------------------------------------------

    def _send_invitee(self, ctx: BookingContext, content: EmailContent, method: CalendarMethod | None) -> bool:
        booking = ctx.booking
        event = self._calendar_event(ctx, summary=f"{ctx.event_type.title} with {ctx.host.full_name}", include_manage_link=True)
        return self._deliver(booking.invitee_email, content, event, method, "invitee")

    def _send_host(self, ctx: BookingContext, content: EmailContent, method: CalendarMethod | None) -> bool:
        event = self._calendar_event(ctx, summary=f"{ctx.event_type.title} with {ctx.booking.invitee_name}", include_manage_link=False)
        return self._deliver(ctx.host.email, content, event, method, "host")

    def _deliver(
        self,
        recipient: str,
        content: EmailContent,
        event: CalendarEvent,
        method: CalendarMethod | None,
        role: str,
    ) -> bool:
        attachments: list[EmailAttachment] = [ics_attachment(event, method)] if method else []
        try:
            self.email.send_rendered(recipient, render_email(content), attachments)
        except Exception:
            # Recipient address is PII; log the role and subject only.
            logger.exception("booking email failed", extra={"recipient_role": role, "subject": content.subject})
            return False
        return True

    @staticmethod
    def _calendar_event(ctx: BookingContext, *, summary: str, include_manage_link: bool) -> CalendarEvent:
        booking = ctx.booking
        lines = [f"{ctx.event_type.title} between {ctx.host.full_name} and {booking.invitee_name}."]
        if booking.meeting_url:
            lines.append(f"Join: {booking.meeting_url}")
        if booking.notes:
            lines.append(f"Notes: {booking.notes}")
        if include_manage_link and ctx.manage_url:
            lines.append(f"Reschedule or cancel: {ctx.manage_url}")
        return CalendarEvent(
            uid=booking_uid(booking.id),
            sequence=booking.sequence or 0,
            starts_at=ctx.starts_at,
            ends_at=ctx.ends_at,
            summary=summary,
            description="\n".join(lines),
            organizer_name=ctx.host.full_name,
            organizer_email=ctx.host.email,
            attendee_name=booking.invitee_name,
            attendee_email=booking.invitee_email,
            location=booking.meeting_url,
            url=booking.meeting_url,
        )


class BookingReminderService:
    """Sends reminders at each configured offset before a confirmed booking starts.

    A reminder is due once ``now >= starts_at - offset``. It is skipped when that moment
    passed more than the grace period ago (the job was down, or the booking was made or
    moved after it), so a 24-hour reminder is never sent two hours before the start.
    Each (booking, offset) is claimed in ``booking_reminders`` before sending, so
    overlapping runs send it once.
    """

    def __init__(
        self,
        db: Session,
        email: EmailService,
        *,
        offsets_minutes: list[int] | None = None,
        grace_minutes: int | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.db = db
        self.bookings = BookingRepository(db)
        self.reminders = BookingReminderRepository(db)
        self.notifications = BookingNotificationService(db, email)
        self.offsets = offsets_minutes if offsets_minutes is not None else settings.reminder_offsets_minutes
        self.grace_minutes = grace_minutes if grace_minutes is not None else settings.reminder_grace_minutes
        self.clock = clock

    def send_due(self) -> int:
        now = self.clock()
        sent = 0
        for offset in self.offsets:
            lead = timedelta(minutes=offset)
            grace = min(timedelta(minutes=self.grace_minutes), lead)
            # Due when starts_at - offset is within (now - grace, now].
            candidates = self.bookings.list_confirmed_starting_between(now + lead - grace, now + lead)
            already_sent = self.reminders.sent_booking_ids((booking.id for booking in candidates), offset)
            for booking in candidates:
                starts_at = as_utc(booking.starts_at)
                if booking.id in already_sent or starts_at <= now:
                    continue
                # Booked after this reminder's send time: the confirmation email already covers it.
                if as_utc(booking.created_at) > starts_at - lead:
                    continue
                ctx = self.notifications.load(booking.id)
                if ctx is None or not self.reminders.claim(booking.id, offset, now):
                    continue
                try:
                    self.notifications.send_reminder(ctx, offset)
                except Exception:
                    logger.exception("booking reminder failed", extra={"booking_id": str(booking.id), "offset_minutes": offset})
                    self.reminders.release(booking.id, offset)
                    continue
                sent += 1
        return sent
