// Shared Sentry options for the browser, Node.js and Edge runtimes.
// Sentry stays fully inert unless NEXT_PUBLIC_SENTRY_DSN is set at build time.

export const sentryDsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

export const isSentryEnabled = Boolean(sentryDsn);

function parseSampleRate(value: string | undefined): number {
  const rate = Number(value);
  return Number.isFinite(rate) && rate >= 0 && rate <= 1 ? rate : 0;
}

export function getSentryOptions() {
  return {
    dsn: sentryDsn,
    environment:
      process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ??
      process.env.NEXT_PUBLIC_VERCEL_ENV ??
      process.env.NODE_ENV,
    tracesSampleRate: parseSampleRate(
      process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE,
    ),
    // Booking data (names, emails, notes) must not be attached to events by default.
    sendDefaultPii: false,
  };
}
