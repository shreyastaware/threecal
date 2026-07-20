import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError
from app.domains.webhooks.models import WebhookEvent


router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/{provider}", status_code=status.HTTP_202_ACCEPTED)
async def receive_webhook(
    provider: str,
    request: Request,
    x_webhook_id: str = Header(),
    x_webhook_signature: str = Header(),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    body = await request.body()
    expected = hmac.new(settings.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, x_webhook_signature):
        raise AppError(status.HTTP_401_UNAUTHORIZED, "invalid_signature", "Invalid webhook signature.")
    payload = json.loads(body)
    event = WebhookEvent(provider=provider, external_id=x_webhook_id, event_type=str(payload.get("type", "unknown")), payload=body.decode())
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"status": "duplicate"}
    return {"status": "accepted"}
