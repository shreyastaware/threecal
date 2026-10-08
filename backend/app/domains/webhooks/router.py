import json

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.domains.webhooks.service import WebhookService


router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/razorpay", status_code=status.HTTP_202_ACCEPTED)
async def receive_razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Platform-level Razorpay webhook (payments, refunds and Route account activation)."""
    body = await request.body()
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise AppError(400, "invalid_webhook_payload", "Webhook payload must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise AppError(400, "invalid_webhook_payload", "Webhook payload must be a JSON object.")
    headers = {key.lower(): value for key, value in request.headers.items()}
    return WebhookService(db).process(body, headers, payload)
