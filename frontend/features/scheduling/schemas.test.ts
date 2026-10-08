import { describe, expect, it } from "vitest";

import { profileSchema } from "@/features/scheduling/schemas";

const valid = { full_name: "Avery Stone", username: "avery", timezone: "UTC", bio: "", avatar_url: "" };

describe("profileSchema username", () => {
  it("rejects usernames that would shadow app routes", () => {
    for (const username of ["bookings", "dashboard", "login", "verify-email"]) {
      expect(profileSchema.safeParse({ ...valid, username }).success).toBe(false);
    }
  });

  it("accepts regular usernames", () => {
    expect(profileSchema.safeParse({ ...valid, username: "bookings-by-avery" }).success).toBe(true);
    expect(profileSchema.safeParse({ ...valid, username: "" }).success).toBe(true);
  });
});
