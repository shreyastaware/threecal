import type { LocationType } from "@/features/event-types/api";

export const LOCATION_LABELS: Record<LocationType, string> = {
  none: "No location",
  in_person: "In person",
  phone: "Phone call",
  custom_link: "Custom meeting link",
  google_meet: "Google Meet",
  zoom: "Zoom",
  microsoft_teams: "Microsoft Teams",
};

/** What invitees see before booking; meeting links are only shared once a booking is confirmed. */
export function publicLocationLabel(locationType: LocationType | null | undefined, locationValue: string | null | undefined): string | null {
  switch (locationType) {
    case "in_person":
      return locationValue ? `In person: ${locationValue}` : LOCATION_LABELS.in_person;
    case "phone":
      return LOCATION_LABELS.phone;
    case "custom_link":
      return "Online meeting";
    case "google_meet":
    case "zoom":
    case "microsoft_teams":
      return LOCATION_LABELS[locationType];
    default:
      return null;
  }
}
