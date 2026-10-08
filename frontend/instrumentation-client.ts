import * as Sentry from "@sentry/nextjs";
import posthog from "posthog-js";

import { getSentryOptions, isSentryEnabled } from "@/lib/observability/sentry";

// Sentry error monitoring (inert unless NEXT_PUBLIC_SENTRY_DSN is set).
if (isSentryEnabled) {
  Sentry.init(getSentryOptions());
}

// Navigation tracing for Sentry; a no-op when Sentry is not initialised.
export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;

const projectToken = process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN;
const host = process.env.NEXT_PUBLIC_POSTHOG_HOST;

if (projectToken && host) {
  posthog.init(projectToken, {
    api_host: host,
    defaults: "2026-01-30",
    capture_exceptions: true,
    debug: process.env.NODE_ENV === "development",
  });
} else if (process.env.NODE_ENV === "development") {
  if (!projectToken) {
    throw new Error(
      "NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN variable required by PostHog is missing or un-configured, this causes events to be silently missed. This error stops appearing once NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN is configured",
    );
  }

  throw new Error(
    "NEXT_PUBLIC_POSTHOG_HOST variable required by PostHog is missing or un-configured, this causes events to be silently missed. This error stops appearing once NEXT_PUBLIC_POSTHOG_HOST is configured",
  );
}
