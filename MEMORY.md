# Threecal Current State

## Product

- Threecal is a paid appointment booking application for advisors, coaches, consultants, doctors, and other professionals.
- A host configures a profile, public username, event types (with booking rules and meeting location), weekly availability with date overrides, a payout bank account, and optional calendar/conferencing integrations.
- An invitee opens an event-specific public URL, selects an available slot, enters contact details, and either confirms a free booking or pays through Razorpay Checkout for a paid booking.
- Paid bookings are collected into the platform's Razorpay account; Razorpay Route automatically transfers the host share to the host's linked account and the platform keeps `PLATFORM_COMMISSION_BPS` (rounded half-up). Route transfers are INR only.
- Usage-based platform billing (Dodo) and per-host payment gateways (Stripe, PayPal, Cashfree, BTCPay, host-owned Razorpay) were removed.
- The frontend and backend are separated into `frontend/` and `backend/`; the backend API is the source of truth. Targets: Vercel (frontend), Railway with SQLite on a persistent volume (backend).

## Frontend

- Next.js 16 App Router, React 19, TypeScript, TanStack Query, React Hook Form, Zod, Framer Motion, Tailwind CSS, shadcn/ui, Lucide.
- Feature modules under `frontend/features`: auth, booking (public), bookings (host/invitee management), dashboard, event-types, integrations, marketing, payments, scheduling.
- Shared fetch client `frontend/lib/api/client.ts` sends cookies, parses `{detail, code}` errors and FastAPI validation errors, and turns 429 into a "try again in N" message using `Retry-After`.
- Auth: `/register`, `/login` (with "Forgot password?"), `/forgot-password`, `/reset-password?token=`, `/verify-email?token=`. New users go to `/onboarding`; workspace routes are protected client-side by the dashboard shell.
- Dashboard shell: Dashboard, Event types, Bookings, Availability, Payments, Integrations, Settings, profile, sign-out; persistent email-verification banner with resend until verified.
- `/dashboard`: stats including paid-bookings enabled/paused, payout warning when an active paid event exists without active payouts, public links, next bookings.
- `/dashboard/event-types`: create/edit/delete; booking rules (buffers, minimum notice, booking window, daily limit); location (none, in person, phone, custom link, Google Meet, Zoom, Microsoft Teams).
- `/dashboard/availability`: weekly hours with breaks; date overrides (unavailable all day or custom hours).
- `/dashboard/bookings`: Upcoming / Past / Cancelled tabs, event filter, pagination, detail dialog, host cancel (with refund note) and reschedule (slot picker).
- `/dashboard/payments`: bank account + KYC form (phone, category/subcategory, PAN, address) for the Razorpay Route linked account, activation status, outstanding requirements, refresh status.
- `/dashboard/integrations`: connect/reconnect/disconnect Google Calendar, Outlook, Zoom; choose conflict calendars and destination calendar.
- `/dashboard/settings`: email verification status/resend, change password, delete account.
- `/dashboard/profile`: name, username (reserved route names rejected), timezone, bio, avatar upload to R2.
- `/:username` and `/:username/:eventSlug`: public profile and booking page; slot browsing pages two weeks at a time within `max_days_in_advance`; shows the location label (custom links are hidden until booking); Razorpay Checkout then `/verify` for immediate confirmation.
- `/bookings/manage/:bookingId?token=`: invitee self-service cancel/reschedule until the cutoff.
- Sentry (`@sentry/nextjs`) is active only when `NEXT_PUBLIC_SENTRY_DSN` is set; PostHog analytics and exception capture remain.
- Vitest + Testing Library tests (`pnpm test`).

## Backend

- Python, FastAPI, SQLAlchemy, Alembic, SQLite, Pydantic v2, JWT cookie auth. Routes under `/api/v1`; `GET /health`.
- Domains under `backend/app/domains`: auth, users, availability, event_types, bookings, payments, webhooks, email, notifications, calendars, conferencing, backups.
- Core: `config`, `database`, `security`, `encryption`, `errors` (AppError `{detail, code}` with optional headers, JSON 500 handler), `rate_limit` (pluggable backend, in-memory default), `events` (in-process event bus), `oauth` (signed OAuth state), `logging` (JSON logs, request IDs, optional Loki), `observability` (Sentry).
- Auth: register (sends verification email), login, logout, verify-email, resend-verification, forgot-password (always 202), reset-password. Single-use hashed tokens in `auth_tokens`. `users.token_version` is embedded in the JWT so password change/reset revokes other sessions.
- Users: `GET/PATCH /users/me`, avatar upload, `POST /users/me/password`, `DELETE /users/me` (blocked by upcoming confirmed bookings; revokes integration tokens; deletes dependents explicitly because SQLite does not enforce cascades).
- Availability: weekly hours with breaks; `GET/PUT/DELETE /availability/overrides`. `AvailabilityService.slots` applies overrides, breaks, buffers, minimum notice, booking window, daily limit, active bookings, and external calendar busy times (cached, fail-open).
- Bookings: public profile/page/slots/create; host `GET /bookings`, `GET /bookings/{id}`, cancel, reschedule, reschedule slots; invitee `GET /public/bookings/{id}`, slots, cancel, reschedule using an HMAC manage token (derived from `JWT_SECRET_KEY`; only its hash is stored). Invitee changes allowed until `INVITEE_CHANGE_CUTOFF_HOURS`.
- Booking times are stored in UTC. Only PENDING/CONFIRMED bookings hold a slot (partial unique index `uq_booking_host_start_active`); pending bookings stop holding their slot when the 10-minute payment window closes and are marked EXPIRED by the scheduler or on the next booking at that time.
- Payments: `GET/POST/PATCH /payments/account`, `POST /payments/account/sync`, `POST /payments/bookings/{id}/checkout` (Razorpay order with Route transfer), `POST /payments/bookings/{id}/verify`. `RefundService.refund_booking` issues a full refund with transfer reversal. Paid bookings require an activated linked account (`host_payments_not_ready`).
- Webhooks: `POST /webhooks/razorpay` (signature-verified, idempotent) handles payment captured/order paid, refunds, and Route product activation. Payments arriving after expiry confirm the booking if the slot is still free, otherwise they are refunded automatically.
- Events: `booking.confirmed`, `booking.cancelled`, `booking.rescheduled` published after commit. Subscribers: conferencing (priority 10, sets `bookings.meeting_url`), calendar sync (20), email notifications (100).
- Notifications: HTML + text emails with `.ics` (REQUEST/CANCEL, stable UID, SEQUENCE) for invitee confirmation, host new booking, cancellation, reschedule, and reminders at `REMINDER_OFFSETS_MINUTES`. Email providers: console and SMTP (Brevo), supporting HTML and attachments.
- Calendars: Google Calendar and Microsoft Graph OAuth connections, conflict calendars, destination calendar, event create/update/delete on booking events, token refresh, `reconnect_required` status.
- Conferencing: Zoom OAuth meetings; Google Meet and Teams via the calendar event; custom links.
- Jobs: in-process scheduler (`SCHEDULER_ENABLED=true`) runs expire-pending-bookings, booking reminders, and daily SQLite backup to R2 with retention. CLI equivalents under `python -m app.jobs.*`.
- Deployment: `backend/Dockerfile`, `railway.toml`, entrypoint runs migrations then uvicorn. CI in `.github/workflows/ci.yml`.

## Missing Or Needed Features

- Verify Razorpay Route against live test mode: stakeholder update path, linked-account PATCH fields, `product.route.*` webhook payload shape, `reverse_all` format.
- Verify Google, Microsoft, and Zoom integrations against real OAuth apps; Google Meet links returned as "pending" are not re-fetched.
- Verify real SMTP delivery and calendar-client rendering of `.ics` invites.
- Apple/iCloud calendar (CalDAV) is not supported.
- Social login is not exposed (OAuthAccount model exists but no login flow).
- Route protection is client-side only; a Next.js 16 `proxy.ts` redirect could be added.
- The rate limiter, busy-time cache, event bus, and scheduler are per process; move to Redis/a queue and Railway cron when moving to PostgreSQL and multiple replicas.
- Bookings created before migration `20260803_0012` have no invitee manage token; bookings created before `20260801_0007` may have non-UTC start times stored.
- Multi-currency paid events cannot use Route (INR only); the UI should restrict paid event currency accordingly.
- Configure production secrets: JWT, credentials encryption, cookies, CORS, Razorpay keys and webhook secret, SMTP, R2, Sentry, Loki, Google/Microsoft/Zoom OAuth.
