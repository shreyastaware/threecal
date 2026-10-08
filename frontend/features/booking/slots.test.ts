import { describe, expect, it } from "vitest";

import { addDays, groupSlots, slotWindow } from "@/features/booking/slots";

describe("slotWindow", () => {
  it("clips the range to the event type's booking window", () => {
    expect(slotWindow("2026-10-08", 0, 5)).toEqual({ start: "2026-10-08", end: "2026-10-13", hasPrevious: false, hasNext: false });
  });

  it("pages through a longer booking window", () => {
    const first = slotWindow("2026-10-08", 0, 20);
    const second = slotWindow("2026-10-08", 1, 20);
    expect(first).toEqual({ start: "2026-10-08", end: "2026-10-21", hasPrevious: false, hasNext: true });
    expect(second).toEqual({ start: "2026-10-22", end: "2026-10-28", hasPrevious: true, hasNext: false });
    // Out-of-range pages snap to the last page.
    expect(slotWindow("2026-10-08", 9, 20)).toEqual(second);
  });

  it("allows paging far ahead when the window is unlimited", () => {
    expect(slotWindow("2026-10-08", 3, null).hasNext).toBe(true);
  });
});

describe("slot helpers", () => {
  it("adds days across month boundaries", () => {
    expect(addDays("2026-10-30", 3)).toBe("2026-11-02");
  });

  it("groups slots by day in the viewer timezone", () => {
    const grouped = groupSlots(
      [
        { starts_at: "2026-10-08T20:00:00Z", ends_at: "2026-10-08T20:30:00Z" },
        { starts_at: "2026-10-08T03:00:00Z", ends_at: "2026-10-08T03:30:00Z" },
      ],
      "Asia/Kolkata",
    );
    expect(Object.keys(grouped).sort()).toEqual(["2026-10-08", "2026-10-09"]);
  });
});
