import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  images: {
    remotePatterns: [
      {
        hostname: "assets.threecal.com",
        pathname: "/payment-providers/**",
        port: "",
        protocol: "https",
        search: "",
      },
    ],
  },
};

// Sentry is only wired into the build when a DSN is configured, so it stays fully inert otherwise.
const isSentryEnabled = Boolean(process.env.NEXT_PUBLIC_SENTRY_DSN);
// Source maps are uploaded only when Sentry credentials are available (e.g. on Vercel).
const canUploadSourceMaps = Boolean(
  process.env.SENTRY_AUTH_TOKEN &&
    process.env.SENTRY_ORG &&
    process.env.SENTRY_PROJECT,
);

export default async function config(): Promise<NextConfig> {
  if (!isSentryEnabled) {
    return nextConfig;
  }
  // Loaded lazily: importing the Sentry config wrapper at module scope breaks
  // Turbopack's next/font handling in development even when Sentry is unused.
  const { withSentryConfig } = await import("@sentry/nextjs/config");
  return withSentryConfig(nextConfig, {
    org: process.env.SENTRY_ORG,
    project: process.env.SENTRY_PROJECT,
    authToken: process.env.SENTRY_AUTH_TOKEN,
    silent: !process.env.CI,
    telemetry: false,
    widenClientFileUpload: true,
    sourcemaps: {
      disable: !canUploadSourceMaps,
      deleteSourcemapsAfterUpload: true,
    },
  });
}
