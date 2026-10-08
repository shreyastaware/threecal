import { describe, expect, it } from "vitest";

import { getTimezoneOptionLabel, TIMEZONE_OPTIONS } from "@/lib/timezones";

describe("timezones", () => {
  it("builds labelled options with unique IANA values", () => {
    const values = TIMEZONE_OPTIONS.map((option) => option.value);

    expect(new Set(values).size).toBe(values.length);
    expect(TIMEZONE_OPTIONS[0]).toEqual({ label: "UTC GMT+0:00", value: "UTC" });
  });

  it("only lists timezones the runtime can format", () => {
    for (const { value } of TIMEZONE_OPTIONS) {
      expect(() =>
        new Intl.DateTimeFormat("en-US", { timeZone: value }).format(),
      ).not.toThrow();
    }
  });

  it("labels known timezones and falls back to the raw value", () => {
    expect(getTimezoneOptionLabel("Asia/Kolkata")).toBe("Asia/Kolkata GMT+5:30");
    expect(getTimezoneOptionLabel("Mars/Olympus_Mons")).toBe("Mars/Olympus_Mons");
  });
});
