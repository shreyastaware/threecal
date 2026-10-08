import { describe, expect, it } from "vitest";

import { loginSchema, registerSchema } from "@/features/auth/schemas/auth";

describe("loginSchema", () => {
  it("trims the email and accepts a valid login", () => {
    const result = loginSchema.parse({
      email: "  host@threecal.com ",
      password: "secret",
    });

    expect(result.email).toBe("host@threecal.com");
  });

  it("rejects an invalid email and an empty password", () => {
    const result = loginSchema.safeParse({ email: "not-an-email", password: "" });

    expect(result.success).toBe(false);
    const messages = result.error?.issues.map((issue) => issue.message);
    expect(messages).toContain("Enter a valid email address");
    expect(messages).toContain("Enter your password");
  });
});

describe("registerSchema", () => {
  const valid = {
    full_name: "Dr. Asha Rao",
    email: "asha@threecal.com",
    password: "correct-horse",
  };

  it("accepts a valid registration", () => {
    expect(registerSchema.safeParse(valid).success).toBe(true);
  });

  it("enforces the password length policy", () => {
    expect(
      registerSchema.safeParse({ ...valid, password: "short" }).success,
    ).toBe(false);
    expect(
      registerSchema.safeParse({ ...valid, password: "x".repeat(129) }).success,
    ).toBe(false);
  });

  it("requires a name of at least two characters after trimming", () => {
    const result = registerSchema.safeParse({ ...valid, full_name: " A " });

    expect(result.success).toBe(false);
    expect(result.error?.issues[0]?.path).toEqual(["full_name"]);
  });
});
