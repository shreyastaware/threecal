import logging
import smtplib
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailAttachment:
    """A provider-agnostic attachment (API providers such as Brevo, SES or Resend take the same fields)."""

    filename: str
    content: bytes
    # MIME type without parameters, e.g. "text/calendar".
    mime_type: str
    # Extra Content-Type parameters, e.g. {"method": "REQUEST"} for calendar invites.
    params: dict[str, str] = field(default_factory=dict)

    @property
    def content_type(self) -> str:
        extras = "".join(f"; {key}={value}" for key, value in self.params.items())
        return f"{self.mime_type}{extras}"


class EmailProvider(ABC):
    @abstractmethod
    def send(
        self,
        *,
        recipient: str,
        subject: str,
        text: str,
        html: str | None = None,
        attachments: Sequence[EmailAttachment] = (),
    ) -> None:
        """Send one email. ``text`` is always present; ``html`` is the rich alternative."""
        raise NotImplementedError


class ConsoleEmailProvider(EmailProvider):
    def send(
        self,
        *,
        recipient: str,
        subject: str,
        text: str,
        html: str | None = None,
        attachments: Sequence[EmailAttachment] = (),
    ) -> None:
        print(f"Email to {recipient}: {subject}\n{text}")
        if html:
            print(f"[html alternative: {len(html)} characters]")
        for attachment in attachments:
            print(f"[attachment: {attachment.filename} ({attachment.content_type}, {len(attachment.content)} bytes)]")


def build_mime_message(
    *,
    sender: str,
    recipient: str,
    subject: str,
    text: str,
    html: str | None = None,
    attachments: Sequence[EmailAttachment] = (),
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")
    for attachment in attachments:
        maintype, _, subtype = attachment.mime_type.partition("/")
        message.add_attachment(
            attachment.content,
            maintype=maintype,
            subtype=subtype or "octet-stream",
            filename=attachment.filename,
            params=attachment.params,
        )
    return message


class SMTPEmailProvider(EmailProvider):
    def send(
        self,
        *,
        recipient: str,
        subject: str,
        text: str,
        html: str | None = None,
        attachments: Sequence[EmailAttachment] = (),
    ) -> None:
        message = build_mime_message(
            sender=settings.smtp_from_email,
            recipient=recipient,
            subject=subject,
            text=text,
            html=html,
            attachments=attachments,
        )
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
                if settings.smtp_use_tls:
                    smtp.starttls()
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
        except (smtplib.SMTPException, OSError):
            # Recipient address is PII; log the subject and SMTP host only.
            logger.exception("email send failed", extra={"provider": "smtp", "smtp_host": settings.smtp_host, "subject": subject})
            raise
        logger.info("email sent", extra={"provider": "smtp", "subject": subject})
