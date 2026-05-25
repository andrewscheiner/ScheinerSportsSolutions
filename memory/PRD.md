# Scheiner Sports Solutions — PRD

## Original problem statement
> This app I have connected through GitHub is a sports dashboard I have created using Streamlit and Python which deploys via Streamlit and GitHub. My goal is to upscale this website so that it runs on its own server with my own custom URL. I would like the Python code to either be deployed via GitHub or a different Python modules and pages changed. Additionally, I want to connect a service like Stripe to this website so that users can pay for a subscription of my sports models. This will likely cause the need for an authentication service, so please keep that in mind, thank you.

## User choices
- Keep Streamlit (Python only) — no React rewrite.
- Authentication: Emergent-managed Google social login.
- Stripe: single-tier monthly subscription ($9.99/mo).
- Brand colors: dark green + gold (from existing logo); support both light & dark mode (default dark).
- Dashboard contains: NBA betting systems, MLB betting systems, MLB seasonal tools (Tango Tracker, Slump Detector, Reverse RYP), NRFI model, pitcher props, NFL power rankings, laddering tool, NBA daily.

## Architecture (2026-01)
- **Frontend (Streamlit)** runs on port 3000 (replaces the standard React frontend). Launched via `/app/frontend/package.json` whose `start` script `cd /app && streamlit run sports-dashboard.py`. Same supervisor-managed `frontend` block — no infrastructure change required.
- **Backend (FastAPI)** at `/app/backend/server.py` on port 8001 — all routes prefixed `/api`.
- **MongoDB** (`sss_db`): collections `users`, `user_sessions`, `subscriptions`, `payment_transactions`.
- Auth: Emergent OAuth (`auth.emergentagent.com`) → fragment `#session_id=...` exchanged via `/api/auth/session` for a 7-day `session_token` (stored both in DB and in `localStorage` on the client; mirrored in the URL as `?session_token=` so Streamlit can read it server-side).
- Stripe: emergentintegrations `StripeCheckout` (custom amount $9.99 USD). Webhook at `/api/webhook/stripe`. Idempotent activation extends `subscriptions.current_period_end` by 30 days.

## Implemented (2026-01-25)
- ✅ FastAPI backend (`/app/backend/server.py`): `/api/health`, `/api/auth/session`, `/api/auth/me`, `/api/auth/logout`, `/api/subscription/plan`, `/api/subscription/checkout`, `/api/subscription/status/{id}`, `/api/webhook/stripe`.
- ✅ Streamlit `auth_gate.py`: login screen, paywall, Stripe-return polling, account sidebar, `ensure_authenticated()` + `ensure_subscribed()` gates.
- ✅ Updated `/app/sports-dashboard.py` to apply gates + new dark-green/gold theme + tool grid (8 tools).
- ✅ `/app/.streamlit/config.toml` with brand colors.
- ✅ Auth & subscription tested end-to-end (13/13 backend tests passed; Streamlit login/paywall/dashboard/NRFI navigation verified).
- ✅ Auth testing playbook at `/app/auth_testing.md`; test credentials in `/app/memory/test_credentials.md`.
- ✅ All eight original tools (NRFI, NBA Daily, NBA Betting Systems, Laddering, Tango Tracker, NFL Power Rankings, Slump Detector, Reverse RYP) intact and reachable.

## Backlog (P1)
- Use a real Stripe recurring subscription (with a Stripe `price_id`) instead of monthly one-off charges that we extend by +30d.
- Add "Manage subscription" / cancel / billing portal link.
- Add email receipts via Resend or SendGrid.

## Backlog (P2)
- Light-mode toggle in the account sidebar (currently dark by default — Streamlit's user theme picker still works in the menu).
- Per-tool free-preview teaser to drive conversion (e.g., show NRFI table blurred for non-subscribers).
- Replace `?session_token=` URL param with HttpOnly cookie via a small auth-callback HTML page served by FastAPI to avoid exposing tokens in URLs.

## Files of record
- `/app/sports-dashboard.py` — Streamlit entry (auth-gated)
- `/app/auth_gate.py` — auth + paywall + sidebar
- `/app/backend/server.py` — FastAPI backend
- `/app/backend/.env` — Mongo + Stripe + plan env
- `/app/frontend/package.json` — Streamlit-as-frontend wrapper
- `/app/.streamlit/config.toml` — brand theme
- `/app/tools/*.py` — original tools (unchanged)
- `/app/data/*.csv` — model output files (unchanged)
- `/app/.github/workflows/*.yml` — nightly GitHub Actions (unchanged)
