"""Calendar provider registry."""

from app.domains.calendars.models import CalendarProviderName
from app.domains.calendars.providers.base import CalendarProvider
from app.domains.calendars.providers.google import GoogleCalendarProvider
from app.domains.calendars.providers.microsoft import MicrosoftCalendarProvider


_PROVIDERS: dict[str, type[CalendarProvider]] = {
    CalendarProviderName.GOOGLE.value: GoogleCalendarProvider,
    CalendarProviderName.MICROSOFT.value: MicrosoftCalendarProvider,
}


def get_calendar_provider(name: str) -> CalendarProvider | None:
    provider_class = _PROVIDERS.get(name)
    return provider_class() if provider_class else None


def calendar_provider_names() -> list[str]:
    return list(_PROVIDERS)
