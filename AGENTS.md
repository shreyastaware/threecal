We are making a paid appointment booking web app called threecal.com

The frontend and backend have been separated in two folders.

Here's the technology Stack Frontend - Next.js (App Router), React, TypeScript, TailwindCSS, ShadCN UI, TanStack Query, React Hook Form, Zod, Framer Motion Backend - Python, FastAPI, SQLAlchemy, Alembic, SQLite initially, Pydantic, JWT Authentication, BackgroundTasks

Deployment

Frontend - Vercel Backend - Railway

Database

SQLite on Railway Persistent Volume initially and automatically daily backups of the database will be taken to cloudflare r2 PostgreSQL later

Storage - Cloudflare R2

Emails

SMTP abstraction Initially Brevo Easily switchable to Amazon SES, Resend, Postmark, etc.

Analytics - PostHog

Monitoring - Sentry

Logging - Grafana

# Strict Coding Rules
1. **Never delete existing comments** when editing or providing updated versions of code.
2. **Domain-Driven Design:** Follow Clean Architecture principles. Separate concerns into API (routers), Services (business logic), and Repositories (database operations).
3. **Typing & Validation:** Strictly use TypeScript for the frontend and Python type hints with Pydantic v2 for backend validation. Use Zod for frontend form validation.
4. **Modularity:** Ensure seamless pluggability for future integrations (e.g., abstracting email providers, payment gateways, and calendar syncing).
5. **Concise Output:** Provide direct, to-the-point code blocks and explanations. Avoid unnecessary conversational filler.

Important Philosophy
- The project should be modular from Day 1.
- Do NOT build everything inside one file.
- Every business domain should have its own service.
- Follow Clean Architecture principles where practical.
- Avoid overengineering while ensuring future scalability.
- Every business domain (Auth, Users, Bookings, Availability, Payments, etc.) must have its own isolated module containing its specific routers, services, repositories, schemas, and models.

Ignore reading session_transcripts/ folder and its files