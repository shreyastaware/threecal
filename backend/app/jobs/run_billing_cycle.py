from app.core.database import SessionLocal
from app.domains.billing.service import BillingCycleService


def main() -> None:
    with SessionLocal() as db:
        result = BillingCycleService(db).run()
        print(f"billing cycles: processed={result.processed} pending={result.pending} failed={result.failed}")


if __name__ == "__main__":
    main()
