from app.core.database import SessionLocal
from app.domains.bookings.service import BookingExpiryService
from app.jobs.runner import run_job


def expire_pending_bookings() -> int:
    with SessionLocal() as db:
        return BookingExpiryService(db).expire_stale()


def main() -> None:
    run_job("expire_pending_bookings", expire_pending_bookings)


if __name__ == "__main__":
    main()
