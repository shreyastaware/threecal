# Threecal frontend

Threecal is a paid appointment booking workspace built with Next.js App Router, React, TypeScript, TanStack Query, React Hook Form, Zod, and Framer Motion.

## Local development

1. Copy `.env.example` to `.env.local` and set `NEXT_PUBLIC_API_URL`.
2. Start the FastAPI backend from `../backend`.
3. Run `pnpm dev` and open `http://localhost:3000`.

Authentication uses the backend's `threecal_access_token` HTTP-only cookie, so API requests include credentials automatically.

## Routes

- `/` marketing page
- `/register` and `/login` authentication
- `/onboarding` profile setup for new accounts
- `/dashboard` workspace overview and public booking links
- `/dashboard/event-types` event type create/edit
- `/dashboard/availability` weekly hours and breaks
- `/dashboard/profile` public profile and booking URL
- `/dashboard/bookings` API capability notice; the backend does not currently expose a host booking-list endpoint
- `/:username/:eventSlug` public booking, invitee details, and provider checkout

The current backend does not expose calendar integration, booking management, password reset, email verification, or payment status lookup endpoints. The UI does not pretend those operations are available.

## Verification

```bash
pnpm exec tsc --noEmit
pnpm lint
pnpm build
```
