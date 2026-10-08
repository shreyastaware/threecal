"""Human-readable event type locations, shared by calendar sync, conferencing and emails."""

from app.domains.event_types.models import LocationType


LOCATION_LABELS: dict[str, str] = {
    LocationType.NONE.value: "",
    LocationType.IN_PERSON.value: "In person",
    LocationType.PHONE.value: "Phone call",
    LocationType.CUSTOM_LINK.value: "Online meeting",
    LocationType.GOOGLE_MEET.value: "Google Meet",
    LocationType.ZOOM.value: "Zoom",
    LocationType.MICROSOFT_TEAMS.value: "Microsoft Teams",
}


def location_text(location_type: str | None, location_value: str | None, meeting_url: str | None = None) -> str | None:
    """Where the meeting happens: an address, a phone number or a join link."""
    kind = location_type or LocationType.NONE.value
    if kind == LocationType.NONE.value:
        return None
    if kind == LocationType.IN_PERSON.value:
        return location_value or LOCATION_LABELS[kind]
    if kind == LocationType.PHONE.value:
        return f"Phone: {location_value}" if location_value else LOCATION_LABELS[kind]
    if meeting_url:
        return meeting_url
    if kind == LocationType.CUSTOM_LINK.value and location_value:
        return location_value
    return LOCATION_LABELS.get(kind) or None
