const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type ApiErrorPayload = {
  code?: string;
  detail?: string;
};

type ValidationError = {
  loc?: (string | number)[];
  msg?: string;
};

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function getErrorMessage(
  error: unknown,
  fallback = "Something went wrong. Please try again.",
): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return fallback;
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  const isFormData =
    typeof FormData !== "undefined" && init.body instanceof FormData;
  if (init.body && !isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as
      | ApiErrorPayload
      | { detail?: ValidationError[] };
    const detail = Array.isArray(payload.detail)
      ? payload.detail
          .map((item) => item.msg)
          .filter((message): message is string => Boolean(message))
          .join(" ")
      : payload.detail;
    throw new ApiError(
      response.status,
      "code" in payload && payload.code ? payload.code : "request_failed",
      detail ?? "Something went wrong. Please try again.",
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
