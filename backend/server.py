"""Main FastAPI server for Personal Finance AI."""
import os
import io
import csv
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import resend

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from auth_utils import hash_password, verify_password, create_access_token, get_current_user
from categorizer import categorize, is_essential
from insight_engine import generate_all_insights, compute_financial_health_score
from price_service import (
    get_cached_price,
    refresh_all_portfolio_prices,
    refresh_amfi_cache,
    search_mf,
    get_mf_nav,
)
from affiliates import recommend as recommend_affiliates

# ---------------- Setup ----------------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="FinSight")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").lower().strip()
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


async def send_email_async(to: str, subject: str, html: str) -> None:
    """Fire-and-forget Resend email."""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY missing — skipping email")
        return
    try:
        await asyncio.to_thread(resend.Emails.send, {
            "from": SENDER_EMAIL,
            "to": [to],
            "subject": subject,
            "html": html,
        })
        logger.info(f"Email sent to {to}: {subject}")
    except Exception as e:
        logger.exception(f"Email send failed to {to}: {e}")


def is_admin_email(email: str) -> bool:
    return ADMIN_EMAIL and email.lower().strip() == ADMIN_EMAIL


def admin_user_overrides(email: str) -> dict:
    """Returns extra fields if this is the admin email."""
    if is_admin_email(email):
        return {"is_admin": True, "plan": "pro"}
    return {"is_admin": False}

# ---------------- Models ----------------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    name: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: str
    email: str
    name: str
    monthly_income: float = 0
    plan: str = "free"
    is_admin: bool = False
    created_at: str

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    monthly_income: Optional[float] = None

class ExpenseIn(BaseModel):
    amount: float
    merchant: str = ""
    category: Optional[str] = None
    date: Optional[str] = None  # ISO
    notes: Optional[str] = ""

class ExpenseOut(BaseModel):
    id: str
    amount: float
    merchant: str
    category: str
    date: str
    notes: str
    essential: bool
    created_at: str

class HoldingIn(BaseModel):
    asset_type: str  # "stock" | "mf"
    symbol: str
    name: Optional[str] = ""
    quantity: float
    avg_buy_price: float
    sector: Optional[str] = "Other"
    is_sip: bool = False
    sip_amount: Optional[float] = 0

class HoldingUpdate(BaseModel):
    quantity: Optional[float] = None
    avg_buy_price: Optional[float] = None
    is_sip: Optional[bool] = None
    sip_amount: Optional[float] = None
    sector: Optional[str] = None
    name: Optional[str] = None

class RazorpayOrderIn(BaseModel):
    plan: str  # "basic" | "pro"

# ---------------- Helpers ----------------
def now_iso():
    return datetime.now(timezone.utc).isoformat()

async def _user_doc(user_id: str):
    u = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not u:
        raise HTTPException(404, "User not found")
    return u

# ---------------- Auth ----------------
@api.post("/auth/register", response_model=UserOut)
async def register(data: RegisterIn):
    existing = await db.users.find_one({"email": data.email.lower()})
    if existing:
        raise HTTPException(400, "Email already registered")
    uid = str(uuid.uuid4())
    overrides = admin_user_overrides(data.email)
    doc = {
        "id": uid,
        "email": data.email.lower(),
        "name": data.name,
        "password_hash": hash_password(data.password),
        "monthly_income": 0,
        "plan": overrides.get("plan", "free"),
        "is_admin": overrides.get("is_admin", False),
        "created_at": now_iso(),
    }
    await db.users.insert_one(doc)
    return UserOut(**{k: v for k, v in doc.items() if k != "password_hash"})

@api.post("/auth/login")
async def login(data: LoginIn):
    u = await db.users.find_one({"email": data.email.lower()})
    if not u or not verify_password(data.password, u["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    # Idempotent admin promotion
    if is_admin_email(u["email"]) and (not u.get("is_admin") or u.get("plan") != "pro"):
        await db.users.update_one({"id": u["id"]}, {"$set": {"is_admin": True, "plan": "pro"}})
        u["is_admin"] = True
        u["plan"] = "pro"
    token = create_access_token(u["id"], u["email"])
    return {
        "token": token,
        "user": {
            "id": u["id"], "email": u["email"], "name": u["name"],
            "monthly_income": u.get("monthly_income", 0), "plan": u.get("plan", "free"),
            "is_admin": u.get("is_admin", False),
            "created_at": u["created_at"],
        },
    }

@api.get("/auth/me", response_model=UserOut)
async def me(user=Depends(get_current_user)):
    u = await _user_doc(user["id"])
    return UserOut(**u)

@api.patch("/auth/profile", response_model=UserOut)
async def update_profile(data: ProfileUpdate, user=Depends(get_current_user)):
    upd = {k: v for k, v in data.model_dump().items() if v is not None}
    if upd:
        await db.users.update_one({"id": user["id"]}, {"$set": upd})
    u = await _user_doc(user["id"])
    return UserOut(**u)

# ---------------- Expenses ----------------
@api.post("/expenses", response_model=ExpenseOut)
async def create_expense(data: ExpenseIn, user=Depends(get_current_user)):
    category = data.category or categorize(data.merchant, data.notes or "")
    date = data.date or now_iso()
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "amount": float(data.amount),
        "merchant": data.merchant or "",
        "category": category,
        "date": date,
        "notes": data.notes or "",
        "essential": is_essential(category),
        "created_at": now_iso(),
    }
    await db.expenses.insert_one(doc.copy())
    doc.pop("user_id", None)
    return ExpenseOut(**doc)

@api.get("/expenses", response_model=List[ExpenseOut])
async def list_expenses(
    user=Depends(get_current_user),
    limit: int = 500,
    category: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    q: Dict[str, Any] = {"user_id": user["id"]}
    if category:
        q["category"] = category
    if start or end:
        dq: Dict[str, Any] = {}
        if start: dq["$gte"] = start
        if end: dq["$lte"] = end
        q["date"] = dq
    docs = await db.expenses.find(q, {"_id": 0, "user_id": 0}).sort("date", -1).to_list(limit)
    return [ExpenseOut(**d) for d in docs]

@api.delete("/expenses/{exp_id}")
async def delete_expense(exp_id: str, user=Depends(get_current_user)):
    r = await db.expenses.delete_one({"id": exp_id, "user_id": user["id"]})
    if r.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"ok": True}

@api.post("/expenses/csv")
async def upload_csv(file: UploadFile = File(...), user=Depends(get_current_user)):
    """Accept CSV with columns: date, amount, merchant (or description), notes (optional), category (optional).
    Handles common bank CSVs — any column containing 'amount' or 'debit' is used."""
    content = await file.read()
    try:
        text = content.decode("utf-8", errors="ignore")
    except Exception:
        raise HTTPException(400, "Unable to read file")
    reader = csv.DictReader(io.StringIO(text))
    inserted = 0
    skipped = 0
    docs = []
    for row in reader:
        # Lowercase keys
        r = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        amt_str = r.get("amount") or r.get("debit") or r.get("withdrawal") or r.get("debit amount") or ""
        amt_str = amt_str.replace(",", "").replace("₹", "").replace("INR", "").strip()
        try:
            amt = float(amt_str)
            if amt <= 0:
                skipped += 1
                continue
        except Exception:
            skipped += 1
            continue
        merchant = r.get("merchant") or r.get("description") or r.get("narration") or r.get("particulars") or ""
        notes = r.get("notes") or ""
        date_str = r.get("date") or r.get("txn date") or r.get("transaction date") or now_iso()
        # Try to normalize date
        try:
            if "/" in date_str:
                # dd/mm/yyyy
                dt = datetime.strptime(date_str.split(" ")[0], "%d/%m/%Y")
            elif "-" in date_str and len(date_str.split("-")[0]) == 4:
                dt = datetime.fromisoformat(date_str[:19])
            elif "-" in date_str:
                dt = datetime.strptime(date_str.split(" ")[0], "%d-%m-%Y")
            else:
                dt = datetime.now(timezone.utc)
            dt = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
            date_iso = dt.isoformat()
        except Exception:
            date_iso = now_iso()
        category = r.get("category") or categorize(merchant, notes)
        docs.append({
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "amount": amt,
            "merchant": merchant,
            "category": category,
            "date": date_iso,
            "notes": notes,
            "essential": is_essential(category),
            "created_at": now_iso(),
        })
    if docs:
        await db.expenses.insert_many(docs)
        inserted = len(docs)
    return {"inserted": inserted, "skipped": skipped}

@api.get("/expenses/summary")
async def expense_summary(user=Depends(get_current_user)):
    exps = await db.expenses.find({"user_id": user["id"]}, {"_id": 0, "user_id": 0}).to_list(5000)
    u = await _user_doc(user["id"])
    health = compute_financial_health_score(exps, u.get("monthly_income", 0))
    # By category
    from collections import defaultdict
    now = datetime.now(timezone.utc)
    cat_totals = defaultdict(float)
    for e in exps:
        try:
            dt = datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
        except Exception:
            continue
        if dt.year == now.year and dt.month == now.month:
            cat_totals[e.get("category", "Other")] += float(e["amount"])
    top = sorted([{"category": k, "amount": round(v, 2)} for k, v in cat_totals.items()], key=lambda x: -x["amount"])
    # Daily trend (last 30 days)
    day_totals = defaultdict(float)
    from datetime import timedelta
    cutoff = now - timedelta(days=30)
    for e in exps:
        try:
            dt = datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
        except Exception:
            continue
        if dt >= cutoff:
            day_totals[dt.strftime("%Y-%m-%d")] += float(e["amount"])
    # Generate last 30 days even if zero
    trend = []
    for i in range(29, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        trend.append({"date": d, "amount": round(day_totals.get(d, 0), 2)})
    return {
        "health": health,
        "top_categories": top[:8],
        "daily_trend": trend,
        "total_expenses": len(exps),
    }

# ---------------- Insights ----------------
@api.get("/insights")
async def get_insights(force: bool = False, user=Depends(get_current_user)):
    # Use cache if fresh (< 60 minutes) unless force=true
    if not force:
        cached = await db.insights_cache.find_one({"user_id": user["id"]}, {"_id": 0})
        if cached and cached.get("updated_at"):
            try:
                upd = datetime.fromisoformat(cached["updated_at"])
                if datetime.now(timezone.utc) - upd < timedelta(minutes=60):
                    return cached["data"]
            except Exception:
                pass
    exps = await db.expenses.find({"user_id": user["id"]}, {"_id": 0, "user_id": 0}).to_list(5000)
    u = await _user_doc(user["id"])
    result = await generate_all_insights(exps, u.get("monthly_income", 0))
    await db.insights_cache.update_one(
        {"user_id": user["id"]},
        {"$set": {"user_id": user["id"], "data": result, "updated_at": now_iso()}},
        upsert=True,
    )
    return result


@api.get("/insights/quick")
async def quick_insights(user=Depends(get_current_user)):
    """Fast endpoint for dashboard — no LLM call. Pure rule-based + statistical."""
    from insight_engine import (
        compute_financial_health_score, detect_anomalies, detect_behavioral_patterns,
        category_overspend, savings_opportunities, trend_analysis,
    )
    exps = await db.expenses.find({"user_id": user["id"]}, {"_id": 0, "user_id": 0}).to_list(5000)
    u = await _user_doc(user["id"])
    return {
        "health": compute_financial_health_score(exps, u.get("monthly_income", 0)),
        "trend": trend_analysis(exps),
        "anomalies": detect_anomalies(exps),
        "behavioral_patterns": detect_behavioral_patterns(exps),
        "category_overspends": category_overspend(exps),
        "savings_opportunities": savings_opportunities(exps),
    }


# ---------------- Challenge: First ₹10k Challenge ----------------
@api.get("/challenge")
async def get_challenge(user=Depends(get_current_user)):
    """Gamified savings challenge for first earners.
    Tracks total saved since signup based on (monthly_income * months_active) - total_expenses.
    Milestones: ₹1k, ₹5k, ₹10k.
    """
    u = await _user_doc(user["id"])
    income = float(u.get("monthly_income", 0))
    created = u.get("created_at")
    try:
        created_dt = datetime.fromisoformat(created)
    except Exception:
        created_dt = datetime.now(timezone.utc)
    now = datetime.now(timezone.utc)
    days = max(1, (now - created_dt).days + 1)
    months_active = max(1.0, days / 30.0)
    expected_income = income * months_active

    exps = await db.expenses.find({"user_id": user["id"]}, {"_id": 0, "amount": 1, "date": 1}).to_list(10000)
    total_spent = 0.0
    for e in exps:
        try:
            d = datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
            if d >= created_dt:
                total_spent += float(e["amount"])
        except Exception:
            continue

    saved = max(0.0, expected_income - total_spent) if income > 0 else 0.0

    milestones = [1000, 5000, 10000]
    achieved = [m for m in milestones if saved >= m]
    next_m = next((m for m in milestones if saved < m), milestones[-1])
    progress_pct = round(min(100, (saved / next_m) * 100), 1) if next_m else 100
    is_completed = saved >= milestones[-1]

    # Persist achievements (idempotent) + send email on new milestone
    prev = await db.challenges.find_one({"user_id": user["id"]}, {"_id": 0})
    prev_achieved = set(prev.get("achieved_milestones", [])) if prev else set()
    new_milestones = [m for m in achieved if m not in prev_achieved]
    if achieved != list(prev_achieved):
        await db.challenges.update_one(
            {"user_id": user["id"]},
            {"$set": {"user_id": user["id"], "achieved_milestones": achieved, "saved": round(saved, 2), "updated_at": now_iso()}},
            upsert=True,
        )
    # Background email per new milestone
    for m in new_milestones:
        asyncio.create_task(send_email_async(
            u["email"],
            f"🎉 You hit ₹{m:,} on FinSight!",
            f"""<div style="font-family: Arial, sans-serif; max-width:560px; margin:0 auto;">
                <h2 style="color:#FF5500;">Milestone unlocked: ₹{m:,} saved</h2>
                <p>Hey {u.get('name','there')}, you just crossed <strong>₹{m:,}</strong> in lifetime savings on FinSight. Keep going!</p>
                <p>Next stop: ₹{milestones[-1]:,}.</p>
                <p style="margin-top:24px;color:#71717A;font-size:12px;">— FinSight · Money decisions, intelligent.</p>
            </div>""",
        ))

    return {
        "income_set": income > 0,
        "monthly_income": income,
        "days_active": days,
        "expected_income_to_date": round(expected_income, 2),
        "total_spent_since_signup": round(total_spent, 2),
        "saved": round(saved, 2),
        "milestones": milestones,
        "achieved_milestones": achieved,
        "next_milestone": next_m,
        "progress_pct": progress_pct,
        "is_completed": is_completed,
        "new_milestones": new_milestones,
    }

# ---------------- Portfolio ----------------
@api.post("/portfolio")
async def add_holding(data: HoldingIn, user=Depends(get_current_user)):
    if data.asset_type not in ("stock", "mf"):
        raise HTTPException(400, "asset_type must be stock or mf")
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "asset_type": data.asset_type,
        "symbol": data.symbol.strip().upper() if data.asset_type == "stock" else data.symbol.strip(),
        "name": data.name or "",
        "quantity": float(data.quantity),
        "avg_buy_price": float(data.avg_buy_price),
        "sector": data.sector or "Other",
        "is_sip": data.is_sip,
        "sip_amount": float(data.sip_amount or 0),
        "created_at": now_iso(),
    }
    await db.portfolio.insert_one(doc.copy())
    # Prefetch price
    await get_cached_price(db, doc["asset_type"], doc["symbol"])
    doc.pop("user_id", None)
    return doc

@api.patch("/portfolio/{hid}")
async def update_holding(hid: str, data: HoldingUpdate, user=Depends(get_current_user)):
    upd = {k: v for k, v in data.model_dump().items() if v is not None}
    if upd:
        await db.portfolio.update_one({"id": hid, "user_id": user["id"]}, {"$set": upd})
    return {"ok": True}

@api.delete("/portfolio/{hid}")
async def delete_holding(hid: str, user=Depends(get_current_user)):
    r = await db.portfolio.delete_one({"id": hid, "user_id": user["id"]})
    if r.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"ok": True}

@api.get("/portfolio")
async def list_portfolio(user=Depends(get_current_user), refresh: bool = False):
    holdings = await db.portfolio.find({"user_id": user["id"]}, {"_id": 0, "user_id": 0}).to_list(500)
    from collections import defaultdict
    enriched = []
    total_invested = 0.0
    total_current = 0.0
    sector_alloc = defaultdict(float)
    type_alloc = defaultdict(float)
    for h in holdings:
        price_data = await get_cached_price(db, h["asset_type"], h["symbol"], force=refresh)
        cur_price = float(price_data["price"]) if price_data else float(h["avg_buy_price"])
        invested = h["quantity"] * h["avg_buy_price"]
        current = h["quantity"] * cur_price
        pnl = current - invested
        pnl_pct = (pnl / invested * 100) if invested else 0
        item = {
            **h,
            "current_price": round(cur_price, 2),
            "invested": round(invested, 2),
            "current_value": round(current, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "last_updated": price_data.get("last_updated") if price_data else None,
            "name": h.get("name") or (price_data.get("scheme_name") if price_data and h["asset_type"] == "mf" else h["symbol"]),
        }
        enriched.append(item)
        total_invested += invested
        total_current += current
        sector_alloc[h.get("sector", "Other")] += current
        type_alloc[h["asset_type"]] += current

    alloc_by_sector = [{"sector": k, "value": round(v, 2), "pct": round(v / total_current * 100, 1) if total_current else 0} for k, v in sector_alloc.items()]
    alloc_by_type = [{"type": k, "value": round(v, 2), "pct": round(v / total_current * 100, 1) if total_current else 0} for k, v in type_alloc.items()]

    # Risk signals
    risks = []
    for s in alloc_by_sector:
        if s["pct"] > 40:
            risks.append({"severity": "high", "message": f"Overexposed to {s['sector']} ({s['pct']}%). Consider diversifying."})
    if len(holdings) and len(holdings) < 3:
        risks.append({"severity": "medium", "message": "Low diversification — fewer than 3 holdings. Consider adding more assets across sectors."})

    return {
        "holdings": enriched,
        "summary": {
            "total_invested": round(total_invested, 2),
            "total_current": round(total_current, 2),
            "total_pnl": round(total_current - total_invested, 2),
            "total_pnl_pct": round((total_current - total_invested) / total_invested * 100, 2) if total_invested else 0,
            "holding_count": len(holdings),
        },
        "allocation_by_sector": alloc_by_sector,
        "allocation_by_type": alloc_by_type,
        "risk_signals": risks,
    }

@api.post("/portfolio/refresh-prices")
async def manual_refresh(user=Depends(get_current_user)):
    holdings = await db.portfolio.find({"user_id": user["id"]}, {"_id": 0, "asset_type": 1, "symbol": 1}).to_list(500)
    unique = {(h["asset_type"], h["symbol"]) for h in holdings}
    updated = 0
    for at, sym in unique:
        r = await get_cached_price(db, at, sym, force=True)
        if r:
            updated += 1
    return {"updated": updated, "total": len(unique)}

@api.get("/prices/mf/search")
async def mf_search(q: str, user=Depends(get_current_user)):
    results = search_mf(q, limit=15)
    return {"results": results}

@api.get("/prices/mf/{scheme_code}")
async def mf_get(scheme_code: str):
    data = get_mf_nav(scheme_code)
    if not data:
        raise HTTPException(404, "Scheme not found")
    return data

# ---------------- Affiliates ----------------
@api.get("/affiliates/recommendations")
async def affiliate_recs(user=Depends(get_current_user)):
    exps = await db.expenses.find({"user_id": user["id"]}, {"_id": 0, "user_id": 0}).to_list(2000)
    return {"recommendations": recommend_affiliates(exps)}

# ---------------- Subscription (Razorpay) ----------------
PLANS = {
    "basic": {"name": "Basic Premium", "amount_inr": 99.0, "features": ["Advanced AI insights", "Unlimited CSV uploads", "Email alerts"]},
    "pro": {"name": "Pro", "amount_inr": 299.0, "features": ["Everything in Basic", "Investment analytics", "Predictive insights", "Priority support"]},
}

@api.get("/subscription/plans")
async def sub_plans():
    return {"plans": [{"id": k, **v} for k, v in PLANS.items()]}

@api.post("/subscription/create-order")
async def create_rzp_order(data: RazorpayOrderIn, user=Depends(get_current_user)):
    if data.plan not in PLANS:
        raise HTTPException(400, "Invalid plan")
    # Admin gets all plans free
    u = await _user_doc(user["id"])
    if u.get("is_admin"):
        await db.users.update_one({"id": user["id"]}, {"$set": {"plan": data.plan, "plan_activated_at": now_iso()}})
        return {"admin_grant": True, "plan": data.plan}
    key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    if not key_id or not key_secret:
        raise HTTPException(503, "Razorpay not configured. Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in backend .env")
    try:
        import razorpay
        rzp = razorpay.Client(auth=(key_id, key_secret))
        amount_paise = int(PLANS[data.plan]["amount_inr"] * 100)
        order = rzp.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": f"rcpt_{uuid.uuid4().hex[:16]}",
            "notes": {"user_id": user["id"], "plan": data.plan},
        })
        await db.payment_transactions.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "plan": data.plan,
            "order_id": order["id"],
            "amount": PLANS[data.plan]["amount_inr"],
            "currency": "INR",
            "status": "created",
            "payment_status": "pending",
            "created_at": now_iso(),
        })
        return {"order_id": order["id"], "amount": amount_paise, "currency": "INR", "key_id": key_id, "plan": data.plan}
    except Exception as e:
        logger.exception("RZP order failed")
        raise HTTPException(500, f"Order creation failed: {str(e)[:120]}")

@api.post("/subscription/verify")
async def verify_payment(payload: Dict[str, Any], user=Depends(get_current_user)):
    """Verify Razorpay payment and activate plan."""
    order_id = payload.get("razorpay_order_id")
    payment_id = payload.get("razorpay_payment_id")
    signature = payload.get("razorpay_signature")
    if not all([order_id, payment_id, signature]):
        raise HTTPException(400, "Missing fields")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    if not key_secret:
        raise HTTPException(503, "Razorpay not configured")
    import hmac, hashlib
    expected = hmac.new(key_secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        await db.payment_transactions.update_one({"order_id": order_id}, {"$set": {"payment_status": "failed", "status": "failed"}})
        raise HTTPException(400, "Invalid signature")
    # Idempotency: only activate once
    tx = await db.payment_transactions.find_one({"order_id": order_id})
    if tx and tx.get("payment_status") == "paid":
        return {"ok": True, "already_processed": True}
    await db.payment_transactions.update_one(
        {"order_id": order_id},
        {"$set": {"payment_status": "paid", "status": "completed", "payment_id": payment_id, "updated_at": now_iso()}},
    )
    plan = (tx or {}).get("plan", "basic")
    await db.users.update_one({"id": user["id"]}, {"$set": {"plan": plan, "plan_activated_at": now_iso()}})

    # Send confirmation email (background)
    u = await _user_doc(user["id"])
    plan_meta = PLANS.get(plan, {"name": plan, "amount_inr": 0})
    asyncio.create_task(send_email_async(
        u["email"],
        f"FinSight · {plan_meta['name']} activated ✅",
        f"""<div style="font-family: Arial, sans-serif; max-width:560px; margin:0 auto;">
            <h2 style="color:#FF5500;">Payment received — you're now {plan_meta['name']}</h2>
            <p>Hi {u.get('name','there')},</p>
            <p>We've received your payment of <strong>₹{plan_meta['amount_inr']:.0f}</strong>. Your premium features are live.</p>
            <table style="border-collapse:collapse;margin-top:12px;">
              <tr><td style="padding:6px 12px;color:#71717A;">Order ID</td><td style="padding:6px 12px;"><code>{order_id}</code></td></tr>
              <tr><td style="padding:6px 12px;color:#71717A;">Payment ID</td><td style="padding:6px 12px;"><code>{payment_id}</code></td></tr>
              <tr><td style="padding:6px 12px;color:#71717A;">Plan</td><td style="padding:6px 12px;">{plan_meta['name']}</td></tr>
            </table>
            <p style="margin-top:20px;">Open FinSight to explore your new analytics →</p>
            <p style="margin-top:24px;color:#71717A;font-size:12px;">— FinSight · Money decisions, intelligent.</p>
        </div>""",
    ))

    return {"ok": True, "plan": plan}

@api.post("/webhook/razorpay")
async def rzp_webhook(request: Request):
    body = await request.body()
    sig = request.headers.get("X-Razorpay-Signature", "")
    secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
    if secret:
        import hmac, hashlib
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise HTTPException(400, "Invalid webhook signature")
    # Just log
    import json as _json
    try:
        evt = _json.loads(body.decode("utf-8"))
        logger.info(f"RZP webhook: {evt.get('event')}")
    except Exception:
        pass
    return {"ok": True}

# ---------------- Health ----------------
@api.get("/")
async def root():
    return {"ok": True, "app": "Finance AI", "time": now_iso()}

@api.get("/health")
async def health():
    return {"ok": True}

# ---------------- Scheduler ----------------
scheduler: Optional[AsyncIOScheduler] = None

@app.on_event("startup")
async def on_startup():
    global scheduler
    # Indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.expenses.create_index([("user_id", 1), ("date", -1)])
    await db.expenses.create_index([("user_id", 1), ("category", 1)])
    await db.portfolio.create_index([("user_id", 1), ("symbol", 1)])
    await db.price_cache.create_index("last_updated")
    await db.payment_transactions.create_index("order_id", unique=False)
    # Initial AMFI load (non-blocking best-effort)
    try:
        refresh_amfi_cache()
    except Exception:
        logger.warning("Initial AMFI load failed — will retry on cron")
    # Auto-promote admin if exists
    if ADMIN_EMAIL:
        await db.users.update_one(
            {"email": ADMIN_EMAIL},
            {"$set": {"is_admin": True, "plan": "pro"}},
        )
    # Scheduler — daily 2 AM IST (20:30 UTC)
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(lambda: refresh_amfi_cache(), "cron", hour=20, minute=30, id="amfi_daily")
    scheduler.add_job(lambda: _run_async_refresh(), "cron", hour=21, minute=0, id="portfolio_daily")
    scheduler.start()
    logger.info("Scheduler started")

def _run_async_refresh():
    import asyncio
    asyncio.create_task(refresh_all_portfolio_prices(db))

@app.on_event("shutdown")
async def on_shutdown():
    if scheduler:
        scheduler.shutdown()
    client.close()

# ---------------- Mount ----------------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
