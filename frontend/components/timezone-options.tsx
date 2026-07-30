import {
  getTimezoneOptionLabel,
  TIMEZONE_OPTIONS,
} from "@/lib/timezones";
import { SelectItem } from "@/components/ui/select";

function hasTimezoneOption(timezone: string) {
  return TIMEZONE_OPTIONS.some(({ value }) => value === timezone);
}

export function TimezoneOptions({
  currentTimezone,
}: {
  currentTimezone: string;
}) {
  return (
    <>
      {!hasTimezoneOption(currentTimezone) && (
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

export function TimezoneSelectItems({
  currentTimezone,
}: {
  currentTimezone: string;
}) {
  return (
    <>
      {!hasTimezoneOption(currentTimezone) && (
        <SelectItem value={currentTimezone}>
          {getTimezoneOptionLabel(currentTimezone)}
        </SelectItem>
      )}
      {TIMEZONE_OPTIONS.map(({ label, value }) => (
        <SelectItem key={value} value={value}>
          {label}
        </SelectItem>
      ))}
    </>
  );
}
