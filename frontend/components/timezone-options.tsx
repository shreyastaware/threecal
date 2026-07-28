import {
  getTimezoneOptionLabel,
  TIMEZONE_OPTIONS,
} from "@/lib/timezones";

export function TimezoneOptions({
  currentTimezone,
}: {
  currentTimezone: string;
}) {
  const hasCurrentTimezone = TIMEZONE_OPTIONS.some(
    ({ value }) => value === currentTimezone,
  );

  return (
    <>
      {!hasCurrentTimezone && (
        <option value={currentTimezone}>
          {getTimezoneOptionLabel(currentTimezone)}
        </option>
      )}
      {TIMEZONE_OPTIONS.map(({ label, value }) => (
        <option key={value} value={value}>
          {label}
        </option>
      ))}
    </>
  );
}
