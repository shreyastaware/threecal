// Sentry initialisation for the Node.js runtime, loaded from instrumentation.ts.
import * as Sentry from "@sentry/nextjs";

import { getSentryOptions, isSentryEnabled } from "@/lib/observability/sentry";

if (isSentryEnabled) {
  Sentry.init(getSentryOptions());
}
