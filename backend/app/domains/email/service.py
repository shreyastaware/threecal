from app.core.config import settings
from app.domains.bookings.models import Booking
from app.domains.email.providers import ConsoleEmailProvider, EmailProvider, SMTPEmailProvider
from app.domains.event_types.models import EventType
from app.domains.users.models import User


def get_email_provider() -> EmailProvider:
    return SMTPEmailProvider() if settings.email_provider == "smtp" else ConsoleEmailProvider()


class EmailService:
    def __init__(self, provider: EmailProvider) -> None:
        self.provider = provider

    def send_booking_confirmation(self, booking: Booking, event: EventType, host: User) -> None:
        self.provider.send(
            recipient=booking.invitee_email,
            subject=f"Booking confirmed: {event.title}",
            text=f"Your appointment with {host.full_name} starts at {booking.starts_at.isoformat()}.",
        )

    def send_cancellation(self, booking: Booking, event: EventType, host: User) -> None:
        self.provider.send(
            recipient=booking.invitee_email,
            subject=f"Booking cancelled: {event.title}",
            text=f"Your appointment with {host.full_name} has been cancelled.",
        )
