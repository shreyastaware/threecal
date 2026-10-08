# Threecal frontend

Threecal is a paid appointment booking workspace built with Next.js App Router, React, TypeScript, TanStack Query, React Hook Form, Zod, and Framer Motion.

## Local development

1. Copy `.env.example` to `.env.local` and set `NEXT_PUBLIC_API_URL`.
2. Start the FastAPI backend from `../backend`.
3. Run `pnpm dev` and open `http://localhost:3000`.

Authentication uses the backend's `threecal_access_token` HTTP-only cookie, so API requests include credentials automatically.

## Routes

- `/` marketing page
- `/register`, `/login`, `/forgot-password`, `/reset-password`, `/verify-email` authentication and recovery
- `/onboarding` profile setup for new accounts
- `/dashboard` workspace overview, payout status, and next bookings
- `/dashboard/event-types` event types with booking rules and meeting location
- `/dashboard/availability` weekly hours, breaks, and date overrides
- `/dashboard/bookings` host booking list with cancel and reschedule
- `/dashboard/payments` bank account and Razorpay Route payout onboarding
- `/dashboard/integrations` Google Calendar, Outlook, and Zoom connections
- `/dashboard/settings` email verification, password change, account deletion
- `/dashboard/profile` public profile and booking URL
- `/:username/:eventSlug` public booking, invitee details, and Razorpay checkout
- `/bookings/manage/:bookingId` invitee cancel/reschedule via emailed token link

Errors are reported to Sentry when `NEXT_PUBLIC_SENTRY_DSN` is set, and product analytics go to PostHog.

## Verification

```bash
pnpm exec tsc --noEmit
pnpm lint
pnpm test
pnpm build
```
