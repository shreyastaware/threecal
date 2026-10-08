import { describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest, getErrorMessage } from "@/lib/api/client";

function mockFetch(response: Response) {
  const fetchMock = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

describe("apiRequest", () => {
  it("returns parsed JSON and sends credentials with a JSON content type", async () => {
    const fetchMock = mockFetch(jsonResponse({ id: "booking-1" }));

    const result = await apiRequest<{ id: string }>("/bookings", {
      method: "POST",
      body: JSON.stringify({ name: "Asha" }),
    });

    expect(result).toEqual({ id: "booking-1" });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/bookings$/);
    expect(init.credentials).toBe("include");
    expect(new Headers(init.headers).get("Content-Type")).toBe(
      "application/json",
    );
  });

  it("does not force a JSON content type for FormData uploads", async () => {
    const fetchMock = mockFetch(jsonResponse({ ok: true }));
    const body = new FormData();
    body.append("file", new Blob(["avatar"]), "avatar.png");

    await apiRequest("/users/me/avatar", { method: "POST", body });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new Headers(init.headers).has("Content-Type")).toBe(false);
  });

  it("returns undefined for 204 responses", async () => {
    mockFetch(new Response(null, { status: 204 }));

    await expect(apiRequest("/bookings/1", { method: "DELETE" })).resolves.toBe(
      undefined,
    );
  });

  it("maps AppError payloads to ApiError with status, code and message", async () => {
    mockFetch(
      jsonResponse(
        { detail: "This slot is no longer available.", code: "slot_unavailable" },
        { status: 409 },
      ),
    );

    const error = await apiRequest("/bookings").catch((caught) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 409,
      code: "slot_unavailable",
      message: "This slot is no longer available.",
    });
  });

  it("joins FastAPI validation error messages", async () => {
    mockFetch(
      jsonResponse(
        {
          detail: [
            { loc: ["body", "email"], msg: "Invalid email." },
            { loc: ["body", "name"], msg: "Name is required." },
          ],
        },
        { status: 422 },
      ),
    );

    const error = await apiRequest("/bookings").catch((caught) => caught);

    expect(error).toMatchObject({
      status: 422,
      code: "request_failed",
      message: "Invalid email. Name is required.",
    });
  });

  it("falls back to a generic message when the body is not JSON", async () => {
    mockFetch(new Response("Bad gateway", { status: 502 }));

    const error = await apiRequest("/bookings").catch((caught) => caught);

    expect(error).toMatchObject({
      status: 502,
      code: "request_failed",
      message: "Something went wrong. Please try again.",
    });
  });
});

describe("getErrorMessage", () => {
  it("prefers ApiError and Error messages", () => {
    expect(getErrorMessage(new ApiError(400, "bad", "Bad input"))).toBe(
      "Bad input",
    );
    expect(getErrorMessage(new Error("Network down"))).toBe("Network down");
  });

  it("uses the fallback for unknown values", () => {
    expect(getErrorMessage("oops")).toBe(
      "Something went wrong. Please try again.",
    );
    expect(getErrorMessage(null, "Custom fallback")).toBe("Custom fallback");
  });
});
