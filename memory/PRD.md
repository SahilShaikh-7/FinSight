# PaisaIQ — Personal Finance AI (India)

## Original Problem Statement
Production-ready "Money Decision Engine" for Indian students, freshers, and first-salary users. Answers: *Why is the user overspending? Where can they save? What should they do next?*

## User Choices (confirmed)
- LLM: **Claude Sonnet 4.5** via Emergent Universal LLM key
- Auth: **JWT email/password (custom)**
- Payments: **Razorpay** (user will provide RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET)
- Investment prices: **AMFI NAV (daily file) + Yahoo Finance (yfinance)** with MongoDB-backed 6h cache and APScheduler daily refresh
- Stack: **FastAPI + React + MongoDB** (confirmed by user as acceptable in place of Next.js / PostgreSQL)
- Scope: **Everything** — expenses, AI insights, investments, subscriptions, affiliates

## Architecture
```
┌──────────────────────┐   HTTPS    ┌─────────────────────────┐
│ React (CRA + Tailwind│ ──────────▶│ FastAPI (uvicorn :8001) │
│ shadcn + recharts)   │            │  /api/* routes           │
└──────────────────────┘            └──┬──────────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        ▼                              ▼                              ▼
  MongoDB (motor)                APScheduler cron           External services
  - users                        - daily AMFI refresh       - emergentintegrations (Claude)
  - expenses                     - daily portfolio prices   - yfinance (NSE/BSE)
  - portfolio                                               - AMFI NAVAll.txt
  - price_cache                                             - Razorpay
  - payment_transactions
  - insights_cache
```

## What's Implemented (2026-02-23)
### Backend (`/app/backend/`)
- `server.py` — all API routes, CORS, APScheduler startup, MongoDB indexes
- `auth_utils.py` — bcrypt + JWT (HS256, 30-day)
- `categorizer.py` — 14-category keyword engine (Swiggy→Food, Uber→Transport, etc.)
- `insight_engine.py` — Financial Health Score (0-100), z-score anomaly detection, category overspending vs 3-month avg, behavioral patterns (late-night/weekend/impulse), savings opportunities, Claude-powered summary
- `price_service.py` — AMFI NAV parser + yfinance fetcher + 6h cache, NaN-guarded
- `affiliates.py` — rule-based product recommender (credit cards, savings, investments)
- APScheduler — daily AMFI refresh @ 20:30 UTC, portfolio price refresh @ 21:00 UTC

### Frontend (`/app/frontend/src/`)
- Cabinet Grotesk + Manrope typography; dark obsidian + Electric Orange theme
- Pages: Landing, Login, Register, Dashboard, Expenses, Insights, Portfolio, Offers, Subscription, Settings
- Dashboard: animated Health Score ring, 30-day trend line (recharts), top-categories donut, AI summary card, overspend/behavioral cards
- Expenses: quick-add form, CSV upload (bank statement friendly), category filter, delete
- Insights: AI coach summary, trend, anomalies table, overspending, savings ops, behavioral patterns
- Portfolio: holdings table with live P&L, allocation donut, risk signals, add-holding modal with AMFI MF search, SIP support
- Subscription: Razorpay checkout (loads checkout.js) with plan verification + HMAC signature
- Offers: curated credit cards / savings accounts / investment apps matched to spending
- Settings: profile, monthly income (drives savings rate in Health Score)
- JWT axios interceptor, 401 → /login redirect, sonner toasts, data-testid on all interactive elements

### API Endpoints
```
POST   /api/auth/register               POST   /api/expenses
POST   /api/auth/login                  GET    /api/expenses
GET    /api/auth/me                     DELETE /api/expenses/{id}
PATCH  /api/auth/profile                POST   /api/expenses/csv
                                        GET    /api/expenses/summary
POST   /api/portfolio                   GET    /api/insights
GET    /api/portfolio                   GET    /api/affiliates/recommendations
PATCH  /api/portfolio/{id}
DELETE /api/portfolio/{id}              GET    /api/subscription/plans
POST   /api/portfolio/refresh-prices    POST   /api/subscription/create-order
GET    /api/prices/mf/search?q=         POST   /api/subscription/verify
GET    /api/prices/mf/{scheme_code}     POST   /api/webhook/razorpay
```

### MongoDB Collections & Indexes
- `users(id unique, email unique)`
- `expenses(user_id+date desc, user_id+category)`
- `portfolio(user_id+symbol)`
- `price_cache(_id="asset_type:symbol", last_updated)`
- `payment_transactions`, `insights_cache`

### Testing Results (iteration_1.json)
- **Backend: 26/26 tests pass (100%)**
- One critical bug fixed by testing agent: yfinance NaN guard in `price_service.py`
- No _id leaks in any endpoint
- Auth, expenses, insights, portfolio, CSV, affiliates, subscription all verified

## Prioritized Backlog / Known Gaps
### P0 (blocker for payments live)
- User to provide **RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET** in `/app/backend/.env`
- Razorpay webhook secret (optional but recommended)

### P1 (nice to have)
- Alternate stock price source fallback (NSE public API) — yfinance unreliable in some sandbox environments
- Email alerts for anomalies & overspending (SendGrid/Resend)
- Predictive spend forecasting (premium feature)
- Push notifications / in-app alerts feed
- Multi-currency support (NRIs)

### P2 (future)
- Bank statement PDF parser (beyond CSV)
- Budget setting per category with progress rings
- Goal-based savings (trip, emergency fund)
- Shared/family finance spaces
- Mobile app wrapper (Capacitor)

## Frontend Test IDs (sample)
All interactive elements have `data-testid` — e.g. `hero-cta-signup`, `login-submit-btn`, `expense-add-form`, `csv-upload-btn`, `portfolio-add-btn`, `mf-search-input`, `plan-pro-cta`, `logout-btn`.
