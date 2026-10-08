from app.core import database
from app.domains.email.service import EmailService, get_email_provider
from app.domains.notifications.service import BookingReminderService
from app.jobs.runner import run_job


def send_booking_reminders() -> int:
    with database.SessionLocal() as db:
        return BookingReminderService(db, EmailService(get_email_provider())).send_due()


def main() -> None:
    run_job("send_booking_reminders", send_booking_reminders)


if __name__ == "__main__":
    main()
