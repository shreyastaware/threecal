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

Threecal lets a professional publish event-specific booking links, define weekly availability, collect invitee details, and route paid bookings through a connected payment provider.

## Project Status

The repository contains a working first version of the authentication, profile, scheduling, event type, public booking, provider payment, and platform billing flows.

The backend is the source of truth for available capabilities. Calendar synchronization, host booking management, booking status lookup, payment status lookup, and account recovery are not implemented because the current API does not expose those operations. The complete implementation state is recorded in [`MEMORY.md`](./MEMORY.md).

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
- Domain modules for auth, users, availability, event types, bookings, payments, billing, webhooks, and email
- Provider abstractions for email and doctor payment gateways
- BackgroundTasks for booking confirmation email delivery

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

Frontend browser checkout integrations may also require:

- `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` for Stripe Payment Element checkout
- `NEXT_PUBLIC_RAZORPAY_KEY_ID` for Razorpay checkout
- `NEXT_PUBLIC_CASHFREE_MODE=sandbox` or `production` for Cashfree checkout

The backend must allow the frontend origin through `CORS_ORIGINS`, and cookie settings must be compatible with the deployed frontend and API domains.

## Main Frontend Routes

- `/` marketing landing page with role ticker and sign-up links
- `/register` account creation
- `/login` password login
- `/onboarding` required profile setup for accounts without a username
- `/dashboard` workspace overview, public links, statistics, and platform billing
- `/dashboard/profile` public name, username, timezone, bio, and avatar URL editor
- `/dashboard/event-types` event type creation and full update editor
- `/dashboard/availability` weekly working hours and break editor
- `/dashboard/payments` doctor payment-provider onboarding and platform billing
- `/dashboard/billing` Dodo mandate checkout return destination and verification form
- `/dashboard/bookings` capability notice for the missing host booking-list API
- `/:username/:eventSlug` public event page, slot picker, invitee form, and checkout

## Verification

```bash
cd frontend
pnpm exec tsc --noEmit
pnpm lint
pnpm build
```

```bash
cd backend
uv run pytest -q
```

## Operations

- Apply migrations before deployment with `alembic upgrade head`.
- Run the idempotent monthly billing reconciler daily through Railway Cron with `python -m app.jobs.run_billing_cycle`.
- Keep `CREDENTIALS_ENCRYPTION_KEY` stable and secret because doctor payment credentials are encrypted at rest.
- Deploy the frontend to Vercel and the backend to Railway according to the project deployment target.
- SQLite is the initial database and is intended to use a Railway persistent volume with backups to Cloudflare R2; PostgreSQL is the planned later database.

## License

Threecal is licensed under AGPL-3.0.
