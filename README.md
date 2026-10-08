<p align="center">
  <img width="150" height="150" src="frontend/assets/logo_white_bg.png" alt="Threecal logo">
</p>

<h1 align="center">Threecal</h1>

<p align="center">Paid appointment booking for people whose time and expertise carry value.</p>

<p align="center">
  <a href="https://threecal.com" align="center">
    <img src="https://img.shields.io/badge/Visit%20ThreeCal.com-8A2BE2" alt="Threecal.com Website Link">
  </a>
  <a href="https://opensource.org/license/agpl-v3" align="center">
    <img src="https://img.shields.io/badge/License-AGPL%203.0-blue.svg" alt="AGPL 3.0 License">
  </a>
</p>

Threecal lets a professional publish event-specific booking links, define weekly availability, collect invitee details, and collect payment through Razorpay with an automatic Route split between the platform commission and the host's bank account.

## Project Status

The repository contains working authentication (with email verification and password reset), profiles, weekly availability with date overrides, event types with booking rules and meeting locations, public booking, Razorpay Route payments with refunds, host and invitee booking management, email notifications with calendar invites and reminders, Google/Outlook calendar sync, and Google Meet/Zoom links.

The backend is the source of truth for available capabilities. The complete implementation state is recorded in [`MEMORY.md`](./MEMORY.md).

## Architecture

```text
threecal/
├── frontend/   Next.js App Router client and public booking experience
├── backend/    FastAPI API, domain services, SQLAlchemy models, migrations
└── MEMORY.md   Current feature inventory and missing-feature record
```

### Frontend

- Next.js 16 App Router and React 19
- TypeScript with strict checking
- TanStack Query for server state and mutations
- React Hook Form and Zod for form state and validation
- Framer Motion for marketing-page motion
- Feature-oriented modules under `frontend/features`
- Fetch API client with cookie credentials and structured API errors

### Backend

- Python and FastAPI
- SQLAlchemy with SQLite initially
- Alembic migrations
- Pydantic v2 request and response validation
- HTTP-only cookie authentication using JWT
- Domain modules for auth, users, availability, event types, bookings, payments, webhooks, email, notifications, calendars, conferencing, and backups
- Provider abstractions for email, the platform payment gateway (Razorpay Route), calendars, and conferencing
- In-process domain event bus (`app/core/events.py`) for booking notifications and integration sync
- In-process scheduler for expiring unpaid bookings, reminders, and daily database backups
- Sentry error monitoring, structured JSON logs with optional Grafana Loki shipping, and per-route rate limiting

## Local Development

### Backend

```bash
cd backend
cp .env.example .env
uv sync
alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

The default API is available at `http://localhost:8000`, with versioned routes under `http://localhost:8000/api/v1`.

### Frontend

```bash
cd frontend
pnpm install
cp .env.example .env.local
pnpm dev
```

The frontend is available at `http://localhost:3000`. Set `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1` for local API access.

Invitee checkout uses Razorpay Checkout with the key returned by the backend, so the frontend needs no payment keys. The backend needs `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` (for the platform webhook at `/api/v1/webhooks/razorpay`) and `PLATFORM_COMMISSION_BPS`.

The backend must allow the frontend origin through `CORS_ORIGINS`, and cookie settings must be compatible with the deployed frontend and API domains.

## Main Frontend Routes

- `/` marketing landing page with role ticker and sign-up links
- `/register` account creation
- `/login` password login
- `/onboarding` required profile setup for accounts without a username
- `/forgot-password`, `/reset-password`, `/verify-email` account recovery and verification
- `/dashboard` workspace overview, public links, statistics, payout status, and next bookings
- `/dashboard/profile` public name, username, timezone, bio, and avatar URL editor
- `/dashboard/event-types` event type creation and full update editor
- `/dashboard/availability` weekly working hours, breaks, and date overrides
- `/dashboard/payments` host bank account and Razorpay Route payout onboarding
- `/dashboard/bookings` upcoming, past, and cancelled bookings with cancel and reschedule
- `/dashboard/integrations` Google Calendar, Outlook, and Zoom connections
- `/dashboard/settings` email verification, password change, and account deletion
- `/bookings/manage/:bookingId` invitee self-service cancel and reschedule (token link from email)
- `/:username/:eventSlug` public event page, slot picker, invitee form, and checkout

## Verification

```bash
cd frontend
pnpm exec tsc --noEmit
pnpm lint
pnpm test
pnpm build
```

```bash
cd backend
uv run pytest -q
uv run ruff check app tests alembic
uv run mypy app
```

CI runs the same checks in `.github/workflows/ci.yml`.

## Operations

- The backend Docker image applies `alembic upgrade head` on start; see `backend/README.md` for the Railway volume, scheduler, and environment setup.
- Set `SCHEDULER_ENABLED=true` on the single Railway API instance to expire unpaid bookings, send reminders, and back up SQLite to R2 daily.
- Keep `CREDENTIALS_ENCRYPTION_KEY` stable and secret because host bank account numbers and PANs are encrypted at rest.
- Deploy the frontend to Vercel and the backend to Railway according to the project deployment target.
- SQLite is the initial database and is intended to use a Railway persistent volume with backups to Cloudflare R2; PostgreSQL is the planned later database.

## License

Threecal is licensed under AGPL-3.0.
