# FinSight — Production Deployment Guide

FinSight has **three separately deployable pieces**. Vercel hosts the React frontend beautifully but is NOT a great fit for the FastAPI backend (we have APScheduler cron jobs, long-running AMFI fetches, and MongoDB). The recommended production topology:

```
        ┌──────────────────────────┐
        │  Vercel (Frontend only)  │   https://app.finsight.in
        │   React build, PWA,      │   ───────────┐
        │   CDN + edge caching     │              │
        └───────────┬──────────────┘              │ API calls
                    │                             ▼
                    │                  ┌──────────────────────┐
                    │                  │ Railway / Render /   │
                    └─────────────────▶│ Fly.io (FastAPI)     │
                                       │ uvicorn :8001        │
                                       │ APScheduler cron     │
                                       └─────────┬────────────┘
                                                 │
                                                 ▼
                                       ┌──────────────────────┐
                                       │   MongoDB Atlas      │
                                       │   M0 free / M10 prod │
                                       └──────────────────────┘
```

> TL;DR: **Vercel for frontend, Railway for backend, Atlas for DB.**

---

## 1. MongoDB Atlas (database)

1. Sign up at https://cloud.mongodb.com (free M0 tier is fine to start).
2. Create a cluster in a region close to your backend (e.g. **Mumbai / Singapore**).
3. **Database Access** → Add a database user with `readWrite` role. Save username/password.
4. **Network Access** → temporarily add `0.0.0.0/0` (allow all). Later restrict to Railway egress IPs.
5. **Connect** → **Drivers** → copy the SRV connection string, e.g.:
   ```
   mongodb+srv://<user>:<pwd>@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority
   ```

---

## 2. Backend on Railway (recommended)

Railway lets you deploy the FastAPI app with one click and keeps the APScheduler alive.

### Step-by-step
1. Push your code to a GitHub repo.
2. Go to https://railway.app → **New Project → Deploy from GitHub**.
3. Select this repo, pick **Root directory = `backend/`**.
4. Railway auto-detects Python. Add a `Procfile` (already provided in the repo deployment kit):
   ```
   web: uvicorn server:app --host 0.0.0.0 --port $PORT
   ```
5. **Variables** tab → add:
   | Key | Value |
   |---|---|
   | `MONGO_URL` | your Atlas SRV string |
   | `DB_NAME` | `finsight_prod` |
   | `CORS_ORIGINS` | `https://app.finsight.in,https://finsight.vercel.app` |
   | `JWT_SECRET` | long random string (`openssl rand -hex 32`) |
   | `JWT_ALGORITHM` | `HS256` |
   | `JWT_EXPIRE_MINUTES` | `43200` |
   | `EMERGENT_LLM_KEY` | your key (or OpenAI/Anthropic key directly) |
   | `RAZORPAY_KEY_ID` | live or test key |
   | `RAZORPAY_KEY_SECRET` | matching secret |
   | `RESEND_API_KEY` | `re_...` |
   | `SENDER_EMAIL` | `noreply@yourdomain.com` (verified in Resend) |
   | `ADMIN_EMAIL` | `sahil68shaikh68@gmail.com` |
6. Click **Deploy**. Railway gives you a URL like `https://finsight-backend.up.railway.app`.
7. **Test** it:
   ```bash
   curl https://finsight-backend.up.railway.app/api/
   # → {"ok":true,"app":"FinSight",...}
   ```

### Alternative: Render / Fly.io
Exact same env vars. Render command: `uvicorn server:app --host 0.0.0.0 --port $PORT`. Fly needs `fly.toml` + Dockerfile (ask if you want one).

---

## 3. Frontend on Vercel

### Step-by-step
1. Go to https://vercel.com → **New Project → Import from GitHub** → pick your repo.
2. **Configure Project**
   - Framework Preset: **Create React App**
   - Root Directory: **`frontend`**
   - Build Command: `yarn build`
   - Output Directory: `build`
   - Install Command: `yarn install`
3. **Environment Variables** — add these *before first deploy*:
   | Key | Value |
   |---|---|
   | `REACT_APP_BACKEND_URL` | `https://finsight-backend.up.railway.app` (your Railway URL, **no trailing slash**) |
   | `CI` | `false` (CRA warnings-as-errors fix) |
   | `GENERATE_SOURCEMAP` | `false` (smaller production bundle) |
4. Click **Deploy**. Takes ~3 minutes.
5. After deploy, go back to **Railway → Variables → `CORS_ORIGINS`** and add the Vercel URL (e.g. `https://finsight.vercel.app`). Redeploy backend so CORS picks it up.

### Custom domain
- In Vercel → **Settings → Domains** → add `app.finsight.in`.
- Point the DNS record (CNAME `app` → `cname.vercel-dns.com`) at your registrar.
- Vercel auto-provisions SSL.
- Update backend `CORS_ORIGINS` to include the custom domain.

---

## 4. Resend domain verification (production emails)

In test mode (`onboarding@resend.dev`) Resend only delivers to addresses verified in your account. For real users you must verify your own domain:

1. https://resend.com/domains → **Add Domain** → `finsight.in`.
2. Add the DKIM / SPF / MX records Resend shows into your DNS.
3. Wait ~15 min for verification.
4. Update Railway env `SENDER_EMAIL=hello@finsight.in` → redeploy.

---

## 5. Razorpay — go from test to live

1. Complete KYC in Razorpay Dashboard (PAN, bank, business docs).
2. **Settings → API Keys → Generate Live Key**.
3. Update Railway env: `RAZORPAY_KEY_ID` + `RAZORPAY_KEY_SECRET` to the new live pair.
4. **Settings → Webhooks** → add `https://<your-backend>/api/webhook/razorpay` with a secret. Add `RAZORPAY_WEBHOOK_SECRET` env on Railway.

---

## 6. Admin security

- The admin is *whoever registers first with* `sahil68shaikh68@gmail.com`. They pick their own password on `/register`.
- Backend auto-promotes that email to `is_admin=true` + `plan=pro` on register, login, and startup.
- No other email can become admin unless you change `ADMIN_EMAIL` env var.
- **Delete any seeded admin user with a default password before going live.** We already cleared the staging admin.

---

## 7. Post-deploy checklist

- [ ] Atlas cluster created, connection string stored
- [ ] Backend deployed on Railway, `/api/` returns 200
- [ ] Frontend deployed on Vercel, loads Landing page
- [ ] Register → Login → Dashboard works
- [ ] CSV upload parses a real bank statement
- [ ] `/insights/quick` returns under 1 s
- [ ] Razorpay checkout opens (test or live)
- [ ] Resend: payment confirmation email received
- [ ] PWA: "Add to Home Screen" works on Chrome Android + Safari iOS
- [ ] CORS_ORIGINS restricted (no `*` in prod)
- [ ] Atlas IP allow-list restricted
- [ ] `JWT_SECRET` is at least 32 random chars
- [ ] Admin account registered with *your* strong password

---

## 8. Complete env-var reference

### Backend (Railway)
```env
MONGO_URL=mongodb+srv://user:pwd@cluster.xxxxx.mongodb.net/?retryWrites=true&w=majority
DB_NAME=finsight_prod
CORS_ORIGINS=https://app.finsight.in,https://finsight.vercel.app
JWT_SECRET=<openssl rand -hex 32>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=43200
EMERGENT_LLM_KEY=sk-emergent-xxxxxxxxxxxxxxxxxxxxxxxx
RAZORPAY_KEY_ID=rzp_live_xxxxxxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
RAZORPAY_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxxxxxxxxxxxxx
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxxxxx
SENDER_EMAIL=hello@finsight.in
ADMIN_EMAIL=sahil68shaikh68@gmail.com
```

### Frontend (Vercel)
```env
REACT_APP_BACKEND_URL=https://finsight-backend.up.railway.app
CI=false
GENERATE_SOURCEMAP=false
```

---

## 9. Why not full Vercel?

Vercel serverless functions have:
- **10 s execution limit** (free) — our AMFI NAV fetch can take 15–20 s the first time
- **No background workers** — APScheduler cron (daily NAV refresh, portfolio price refresh) would not run
- **No long-lived TCP** — MongoDB connections get dropped between invocations, adding latency
- **Cold starts** — every first request after ~10 min idle is slow

If you absolutely must single-platform Vercel, you can split the backend into:
- Vercel serverless functions for CRUD routes
- A separate cron job runner on Cron-job.org / GitHub Actions calling `/api/portfolio/refresh-prices`

But for a fintech product where reliability = trust, Railway/Render for the API is worth the ~$5/month.

---

## 10. Rollback plan

- Railway: every deploy is versioned. Click any previous deploy → **Redeploy**.
- Vercel: `Deployments` tab → three-dot → **Promote to Production**.
- Atlas: **Backups** (paid tier) → point-in-time restore.

Happy shipping. — FinSight
