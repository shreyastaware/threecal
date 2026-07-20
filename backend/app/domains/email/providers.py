import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage

from app.core.config import settings


class EmailProvider(ABC):
    @abstractmethod
    def send(self, *, recipient: str, subject: str, text: str) -> None:
        raise NotImplementedError


class ConsoleEmailProvider(EmailProvider):
    def send(self, *, recipient: str, subject: str, text: str) -> None:
        print(f"Email to {recipient}: {subject}\n{text}")


class SMTPEmailProvider(EmailProvider):
    def send(self, *, recipient: str, subject: str, text: str) -> None:
        message = EmailMessage()
        message["From"] = settings.smtp_from_email
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(text)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
