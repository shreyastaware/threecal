// Sentry initialisation for the Edge runtime (proxy, edge routes), loaded from instrumentation.ts.
import * as Sentry from "@sentry/nextjs";

import { getSentryOptions, isSentryEnabled } from "@/lib/observability/sentry";

if (isSentryEnabled) {
  Sentry.init(getSentryOptions());
}
