import { describe, expect, it } from "vitest";

import { bookingSchema } from "@/features/booking/schemas";

const valid = {
  invitee_name: "Ravi Kumar",
  invitee_email: "ravi@example.com",
  invitee_timezone: "Asia/Kolkata",
};

describe("bookingSchema", () => {
  it("accepts a booking without notes and trims text fields", () => {
    const result = bookingSchema.parse({
      ...valid,
      invitee_name: "  Ravi Kumar  ",
      invitee_email: " ravi@example.com ",
    });

    expect(result.invitee_name).toBe("Ravi Kumar");
    expect(result.invitee_email).toBe("ravi@example.com");
    expect(result.notes).toBeUndefined();
  });

  it("requires a timezone", () => {
    const result = bookingSchema.safeParse({ ...valid, invitee_timezone: "" });

    expect(result.success).toBe(false);
    expect(result.error?.issues[0]?.message).toBe("Choose a timezone");
  });

  it("rejects invalid emails and overly long notes", () => {
    expect(
      bookingSchema.safeParse({ ...valid, invitee_email: "ravi" }).success,
    ).toBe(false);
    const result = bookingSchema.safeParse({
      ...valid,
      notes: "x".repeat(2001),
    });
    expect(result.success).toBe(false);
    expect(result.error?.issues[0]?.message).toBe(
      "Notes must be 2000 characters or fewer",
    );
  });
});
