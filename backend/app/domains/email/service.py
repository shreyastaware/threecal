from collections.abc import Sequence

from app.core.config import settings
from app.domains.email.providers import ConsoleEmailProvider, EmailAttachment, EmailProvider, SMTPEmailProvider
from app.domains.email.templates import EmailContent, RenderedEmail, render_email
from app.domains.users.models import User


def get_email_provider() -> EmailProvider:
    return SMTPEmailProvider() if settings.email_provider == "smtp" else ConsoleEmailProvider()


class EmailService:
    def __init__(self, provider: EmailProvider) -> None:
        self.provider = provider

    def send_rendered(self, recipient: str, email: RenderedEmail, attachments: Sequence[EmailAttachment] = ()) -> None:
        self.provider.send(
            recipient=recipient,
            subject=email.subject,
            text=email.text,
            html=email.html,
            attachments=attachments,
        )

    def send_email_verification(self, user: User, link: str) -> None:
        self.send_rendered(
            user.email,
            render_email(
                EmailContent(
                    subject="Confirm your email for threecal",
                    heading="Confirm your email",
                    preheader="Finish setting up your threecal account.",
                    paragraphs=[
                        f"Hi {user.full_name},",
                        "Confirm your email address to finish setting up your threecal account:",
                    ],
                    action=("Confirm email address", link),
                    links=[("Or open this link", link)],
                    footer="This link expires in 48 hours. If you did not create an account, you can ignore this email.",
                )
            ),
        )

    def send_password_reset(self, user: User, link: str) -> None:
        self.send_rendered(
            user.email,
            render_email(
                EmailContent(
                    subject="Reset your threecal password",
                    heading="Reset your password",
                    preheader="Choose a new password for threecal.",
                    paragraphs=[
                        f"Hi {user.full_name},",
                        "We received a request to reset your password. Choose a new one here:",
                    ],
                    action=("Choose a new password", link),
                    links=[("Or open this link", link)],
                    footer=(
                        "This link expires in 1 hour and can only be used once. "
                        "If you did not ask for this, you can ignore this email and your password will stay the same."
                    ),
                )
            ),
        )
