"""AI Insight Engine — rule-based + statistical + LLM summaries.
Generates actionable insights like overspending, anomalies, trends, behavioral patterns.
"""
import os
import asyncio
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from statistics import mean, pstdev
from typing import List, Dict, Any, Tuple, DefaultDict
import logging
import groq  # type: ignore

from categorizer import is_essential, ESSENTIAL_CATEGORIES  # type: ignore

logger = logging.getLogger(__name__)


def _parse_date(d):
    if isinstance(d, datetime):
        return d
    try:
        return datetime.fromisoformat(str(d).replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


def compute_financial_health_score(expenses: List[Dict[str, Any]], monthly_income: float = 0) -> Dict[str, Any]:
    """Score 0-100 based on 3 pillars:
      1. Savings rate vs income      — 40 pts  (requires monthly_income to be set)
      2. Spending stability           — 30 pts  (stdev of daily spend last 30 days)
      3. Essential vs wants ratio     — 30 pts  (50-70% essential = ideal)

    Uses a ROLLING 30-day window so bank statement uploads are always meaningful,
    regardless of what calendar month the data is from.
    """
    if not expenses:
        return {
            "score": 50, "savings_rate": 0, "stability": 50, "essential_ratio": 0,
            "breakdown": {"savings_pts": 0, "stability_pts": 15, "essential_pts": 15},
            "total_spend_30d": 0, "monthly_income": monthly_income,
            "label": "No data yet",
        }

    now = datetime.now(timezone.utc)
    cutoff_30 = now - timedelta(days=30)

    # ── Rolling 30-day expenses ──────────────────────────────────────────────
    last_30 = [e for e in expenses if _parse_date(e["date"]) >= cutoff_30]

    # If no recent data (e.g. old CSV upload), use the most recent 30 entries
    if not last_30:
        sorted_exp = sorted(expenses, key=lambda e: _parse_date(e["date"]), reverse=True)
        last_30 = sorted_exp[:min(30, len(sorted_exp))]

    total_spend = sum(float(e["amount"]) for e in last_30)

    # ── Pillar 1: Savings Rate (40 pts) ─────────────────────────────────────
    if monthly_income > 0:
        savings_rate = max(0.0, min(1.0, (monthly_income - total_spend) / monthly_income))
        # Progressive scoring:
        # >40% saved = 40pts, 20-40% = 30pts, 10-20% = 20pts, 0-10% = 10pts, negative = 0
        if savings_rate >= 0.4:
            savings_pts = 40.0
        elif savings_rate >= 0.2:
            savings_pts = 30.0 + (savings_rate - 0.2) / 0.2 * 10
        elif savings_rate >= 0.1:
            savings_pts = 20.0 + (savings_rate - 0.1) / 0.1 * 10
        elif savings_rate > 0:
            savings_pts = savings_rate / 0.1 * 20
        else:
            savings_pts = 0.0  # spending more than income
    else:
        # No income set → neutral 20 pts (encourages user to set income)
        savings_rate = 0.0
        savings_pts = 20.0

    # ── Pillar 2: Spending Stability (30 pts) ────────────────────────────────
    daily: DefaultDict[str, float] = defaultdict(float)
    for e in last_30:
        d = _parse_date(e["date"])
        daily[d.strftime("%Y-%m-%d")] += float(e["amount"])  # type: ignore
    vals = list(daily.values())
    if len(vals) >= 3 and mean(vals) > 0:  # type: ignore
        cv = pstdev(vals) / mean(vals)  # type: ignore
        # cv=0 (perfectly flat) → 30 pts; cv≥1.5 (very erratic) → 0 pts
        stability_pts = max(0.0, (1 - min(cv, 1.5) / 1.5)) * 30
    else:
        stability_pts = 15.0  # not enough data — neutral

    # ── Pillar 3: Essential vs Wants Ratio (30 pts) ──────────────────────────
    essential_amt = sum(float(e["amount"]) for e in last_30 if is_essential(e.get("category", "")))
    essential_ratio = essential_amt / total_spend if total_spend > 0 else 0.5
    # Ideal: 50-70% essential (balanced spending)
    if 0.5 <= essential_ratio <= 0.7:
        essential_pts = 30.0          # perfect
    elif 0.4 <= essential_ratio < 0.5 or 0.7 < essential_ratio <= 0.8:
        essential_pts = 22.0          # slightly off
    elif 0.3 <= essential_ratio < 0.4:
        essential_pts = 12.0          # too many wants
    elif essential_ratio > 0.8:
        essential_pts = 15.0          # almost no wants (bare survival)
    else:
        essential_pts = 5.0           # almost all wants

    score = round(savings_pts + stability_pts + essential_pts)  # type: ignore
    score = max(0, min(100, score))

    # Human-readable label
    if score >= 80:
        label = "Excellent"
    elif score >= 65:
        label = "Good"
    elif score >= 50:
        label = "Fair"
    elif score >= 35:
        label = "Needs attention"
    else:
        label = "At risk"

    return {
        "score": score,
        "savings_rate": round(savings_rate * 100, 1),  # type: ignore
        "stability": round(stability_pts / 30 * 100, 1),  # type: ignore
        "essential_ratio": round(essential_ratio * 100, 1),  # type: ignore
        "breakdown": {
            "savings_pts": round(savings_pts, 1),  # type: ignore
            "stability_pts": round(stability_pts, 1),  # type: ignore
            "essential_pts": round(essential_pts, 1),  # type: ignore
        },
        "total_spend_30d": round(total_spend, 2),  # type: ignore
        "total_spend_this_month": round(total_spend, 2),  # type: ignore  # keep for compatibility
        "monthly_income": monthly_income,
        "label": label,
        "income_set": monthly_income > 0,
    }



def detect_anomalies(expenses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Z-score anomaly detection per category."""
    by_cat: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    for e in expenses:
        by_cat[e.get("category", "Other")].append(e)

    anomalies: List[Dict[str, Any]] = []
    for cat, items in by_cat.items():
        if len(items) < 5:
            continue
        amounts = [float(i["amount"]) for i in items]
        mu = mean(amounts)
        sd = pstdev(amounts) or 1
        for it in items[-20:]:  # type: ignore
            z = (float(it["amount"]) - mu) / sd
            if z >= 2.0:
                anomalies.append({
                    "type": "anomaly",
                    "severity": "high" if z >= 3 else "medium",
                    "category": cat,
                    "merchant": it.get("merchant", ""),
                    "amount": it["amount"],
                    "date": it["date"],
                    "message": f"Unusual spend of ₹{it['amount']:.0f} at {it.get('merchant','') or cat} — {z:.1f}σ above your usual {cat} spend.",
                })
    return anomalies[:10]  # type: ignore


def detect_behavioral_patterns(expenses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detect late-night, weekend spikes, impulse (small frequent) spending.
    
    NOTE: Bank CSV imports store dates without times (midnight UTC = 00:00:00).
    Time-based patterns (late night) are ONLY computed when >= 20% of transactions
    have a real time component (hour != 0 OR minute != 0 OR second != 0).
    """
    patterns = []
    now = datetime.now(timezone.utc)
    last_30 = [e for e in expenses if _parse_date(e["date"]) >= now - timedelta(days=30)]
    if not last_30:
        # Fall back to most recent transactions if no recent data
        sorted_exp = sorted(expenses, key=lambda e: _parse_date(e["date"]), reverse=True)
        last_30 = sorted_exp[:min(50, len(sorted_exp))]
    if not last_30:
        return []

    total = sum(float(e["amount"]) for e in last_30)

    # ── Detect if transactions have real time data ────────────────────────────
    # Bank CSV imports store dates at midnight (00:00:00 UTC) — no real time info.
    # We only trust time-based patterns if >= 20% txns have a non-midnight time.
    def _has_time(e: Dict[str, Any]) -> bool:
        d = _parse_date(e["date"])
        return not (d.hour == 0 and d.minute == 0 and d.second == 0)

    txns_with_time = [e for e in last_30 if _has_time(e)]
    time_data_available = len(txns_with_time) / len(last_30) >= 0.2

    # Late night (10pm–4am) — only when real time data exists
    if time_data_available:
        late_night = [e for e in txns_with_time
                      if _parse_date(e["date"]).hour >= 22 or _parse_date(e["date"]).hour <= 4]
        ln_amt = sum(float(e["amount"]) for e in late_night)
        if total > 0 and ln_amt / total > 0.15:
            patterns.append({
                "type": "late_night",
                "severity": "medium",
                "message": f"You spent ₹{ln_amt:.0f} ({ln_amt/total*100:.0f}%) during late-night hours. Late-night spends are often impulse buys.",
                "count": len(late_night),
            })

    # ── Weekend spikes ────────────────────────────────────────────────────────
    weekend = [e for e in last_30 if _parse_date(e["date"]).weekday() >= 5]
    we_amt = sum(float(e["amount"]) for e in weekend)
    weekday_amt = total - we_amt
    # Only flag if weekend spend is >60% MORE than weekday spend (per-day adjusted)
    weekday_days = max(1, 30 - 8)  # ~22 weekdays in a month
    weekend_days = max(1, 8)        # ~8 weekend days in a month
    we_per_day = we_amt / weekend_days
    wd_per_day = weekday_amt / weekday_days
    if wd_per_day > 0 and we_per_day > wd_per_day * 1.6:
        patterns.append({
            "type": "weekend_spike",
            "severity": "medium",
            "message": f"You spend ₹{we_per_day:.0f}/day on weekends vs ₹{wd_per_day:.0f}/day on weekdays — a {(we_per_day/wd_per_day-1)*100:.0f}% spike. Watch weekend splurges.",
        })

    # ── Impulse — many small non-essential spends ─────────────────────────────
    impulse = [e for e in last_30 if float(e["amount"]) < 500 and not is_essential(e.get("category", ""))]
    if len(impulse) >= 10:  # lowered from 15 to be more sensitive
        imp_amt = sum(float(e["amount"]) for e in impulse)
        patterns.append({
            "type": "impulse",
            "severity": "low" if imp_amt < 3000 else "medium",
            "message": f"{len(impulse)} small non-essential purchases (₹{imp_amt:.0f} total). These add up every month — try a 24-hour cooling-off rule.",
        })
    return patterns


def category_overspend(expenses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compare last 30 days vs the prior 30-60 and 60-90 day windows per category.
    
    Uses rolling windows instead of calendar months so it works correctly
    with bank CSV uploads that may cover historical periods.
    """
    now = datetime.now(timezone.utc)
    w0_start = now - timedelta(days=30)   # last 30 days
    w1_start = now - timedelta(days=60)   # prior 30-60 days
    w2_start = now - timedelta(days=90)   # prior 60-90 days

    by_cat_now:  DefaultDict[str, float] = defaultdict(float)
    by_cat_w1:   DefaultDict[str, float] = defaultdict(float)
    by_cat_w2:   DefaultDict[str, float] = defaultdict(float)

    for e in expenses:
        d = _parse_date(e["date"])
        cat = e.get("category", "Other")
        amt = float(e["amount"])
        if d >= w0_start:
            by_cat_now[cat] += amt
        elif d >= w1_start:
            by_cat_w1[cat] += amt
        elif d >= w2_start:
            by_cat_w2[cat] += amt

    # If current window is empty, shift all windows back by 30 days
    # (handles case where uploaded CSV is older than 30 days)
    if not by_cat_now:
        by_cat_now  = by_cat_w1
        by_cat_w1   = by_cat_w2
        by_cat_w2   = defaultdict(float)  # type: ignore

    insights = []
    for cat, amt in by_cat_now.items():  # type: ignore
        prev_amts = [v for v in [by_cat_w1.get(cat, 0), by_cat_w2.get(cat, 0)] if v > 0]
        if not prev_amts:
            continue
        prev_avg = mean(prev_amts)  # type: ignore
        if prev_avg > 0 and amt > prev_avg * 1.25:  # 25% over avg = flag
            diff = amt - prev_avg
            pct  = (amt / prev_avg - 1) * 100
            insights.append({
                "type": "overspend",
                "severity": "high" if pct > 60 else "medium",
                "category": cat,
                "this_period": round(amt, 2),  # type: ignore
                "prev_avg": round(prev_avg, 2),  # type: ignore
                "message": f"{cat}: ₹{amt:.0f} this period is {pct:.0f}% higher than your recent average (₹{prev_avg:.0f}). You're over by ₹{diff:.0f}.",
            })
    return sorted(insights, key=lambda x: -x.get("this_period", 0))[:5]  # top 5


def savings_opportunities(expenses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Find specific, actionable savings ideas based on the user's actual top spend categories."""
    now = datetime.now(timezone.utc)
    last_30 = [e for e in expenses if _parse_date(e["date"]) >= now - timedelta(days=30)]

    # Use most recent data if no recent expenses (e.g. old CSV)
    if not last_30:
        sorted_exp = sorted(expenses, key=lambda e: _parse_date(e["date"]), reverse=True)
        last_30 = sorted_exp[:min(50, len(sorted_exp))]

    ops = []
    if not last_30:
        return ops

    # Build category totals
    cat_totals: DefaultDict[str, float] = defaultdict(float)
    for e in last_30:
        cat_totals[e.get("category", "Other")] += float(e["amount"])

    total_spend = sum(cat_totals.values())

    # ── Food & Dining ─────────────────────────────────────────────────────────
    food_amt = cat_totals.get("Food & Dining", 0)
    if food_amt > 2000:  # lowered threshold
        potential = food_amt * 0.35
        ops.append({
            "type": "saving",
            "severity": "high" if food_amt > 5000 else "medium",
            "category": "Food & Dining",
            "message": f"₹{food_amt:.0f} on Food & Dining in 30 days. Cooking at home 3x/week could save ~₹{potential:.0f}/month.",
        })

    # ── Entertainment / Subscriptions ─────────────────────────────────────────
    ent_amt = cat_totals.get("Entertainment", 0)
    ent_count = sum(1 for e in last_30 if e.get("category") == "Entertainment")
    if ent_count >= 2 or ent_amt > 500:
        ops.append({
            "type": "saving",
            "severity": "medium",
            "category": "Entertainment",
            "message": f"₹{ent_amt:.0f} on Entertainment ({ent_count} transactions). Audit subscriptions — cancelling 1-2 unused ones saves ₹300-600/month.",
        })

    # ── Shopping ──────────────────────────────────────────────────────────────
    shop_amt = cat_totals.get("Shopping", 0)
    if shop_amt > 3000:  # lowered from 5000
        ops.append({
            "type": "saving",
            "severity": "medium" if shop_amt < 8000 else "high",
            "category": "Shopping",
            "message": f"₹{shop_amt:.0f} on Shopping this period. A 1-week no-shopping challenge could save ~₹{shop_amt*0.3:.0f}.",
        })

    # ── Transport ─────────────────────────────────────────────────────────────
    transport_amt = cat_totals.get("Transport", 0)
    if transport_amt > 2000:
        ops.append({
            "type": "saving",
            "severity": "low",
            "category": "Transport",
            "message": f"₹{transport_amt:.0f} on Transport. Carpooling or monthly passes could cut this by 20-30%.",
        })

    # ── Generic top-category tip (always show something useful) ───────────────
    if not ops and cat_totals:
        top_cat = max(cat_totals, key=lambda c: cat_totals[c])  # type: ignore
        top_amt = cat_totals[top_cat]
        pct = top_amt / total_spend * 100 if total_spend > 0 else 0
        if pct > 30:  # top category is >30% of spend
            ops.append({
                "type": "saving",
                "severity": "low",
                "category": top_cat,
                "message": f"{top_cat} is your biggest expense at ₹{top_amt:.0f} ({pct:.0f}% of total). Even a 10% reduction saves ₹{top_amt*0.1:.0f}/month.",
            })

    return ops[:4]  # max 4 suggestions


def trend_analysis(expenses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compare total spend month-over-month."""
    now = datetime.now(timezone.utc)
    by_month: DefaultDict[Tuple[int, int], float] = defaultdict(float)  # type: ignore
    for e in expenses:
        d = _parse_date(e["date"])
        by_month[(d.year, d.month)] += float(e["amount"])
    cur = by_month.get((now.year, now.month), 0)
    prev_m, prev_y = (now.month - 1, now.year) if now.month > 1 else (12, now.year - 1)
    prev = by_month.get((prev_y, prev_m), 0)
    pct = ((cur - prev) / prev * 100) if prev > 0 else 0
    return {
        "current_month_spend": round(cur, 2),  # type: ignore
        "previous_month_spend": round(prev, 2),  # type: ignore
        "change_pct": round(pct, 1),  # type: ignore
        "trend": "up" if pct > 5 else "down" if pct < -5 else "steady",
    }


# Global state for Groq model (lazy initialization)
_groq_api_key = None
_client = None
_initialized = False

def _initialize_groq():
    """Initialize Groq client on first use (lazy initialization)."""
    global _groq_api_key, _client, _initialized
    
    if _initialized:
        return  # Already tried initialization
    
    _initialized = True
    _groq_api_key = os.getenv("GROQ_API_KEY")
    
    if not _groq_api_key:
        logger.warning("GROQ_API_KEY not set — LLM summaries disabled")
        return
    
    try:
        _client = groq.AsyncGroq(api_key=_groq_api_key)
        logger.info("✅ Groq client initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Groq client: {e}")


async def generate_llm_summary(insights_data: dict) -> str:
    """Generate AI summary using Groq with proper async handling and error logging.
    
    Args:
        insights_data: Dictionary of financial insights to summarize
        
    Returns:
        String summary or graceful fallback message
    """
    # Lazy initialization: ensure Groq is initialized before first use
    _initialize_groq()
    
    if not _client:
        logger.warning("Groq client not initialized — skipping LLM summary")
        return "AI insights unavailable (API not configured)"
    
    try:
        prompt = f"""You are a personal finance coach for Indian users.

Based on this financial data:
{insights_data}

Provide:
1. A 2–3 line summary of their financial health
2. One practical, actionable suggestion

Keep it simple, direct, and focused on Indian financial context."""

        logger.debug(f"Calling Groq with prompt summary context: {list(insights_data.keys())}")
        
        response = await asyncio.wait_for(
            _client.chat.completions.create(
                messages=[
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile",
            ),
            timeout=10.0  # 10 second timeout for Groq call
        )
        
        summary = response.choices[0].message.content.strip() if response.choices and response.choices[0].message.content else "No response from AI"
        logger.info(f"Successfully generated AI summary ({len(summary)} chars)")
        return summary
        
    except asyncio.TimeoutError:
        error_msg = "AI summary generation timed out (>10s)"
        logger.error(error_msg)
        return f"{error_msg} — please try again"
    except Exception as e:
        error_type = type(e).__name__
        error_str = str(e)
        if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
            logger.error(f"Groq quota/rate limit exhausted: {error_str[:100]}")  # type: ignore
            return "AI summary unavailable: API quota exceeded. Please upgrade your plan."
        else:
            logger.exception(f"AI summary generation failed: {error_type}: {error_str}")
            return f"AI summary unavailable: {error_type}"

async def generate_all_insights(expenses: List[Dict[str, Any]], monthly_income: float = 0, tier: str = "standard") -> Dict[str, Any]:
    """Generate comprehensive financial insights with AI summary.
    
    Computes all insights (health, anomalies, patterns, trends, savings) and calls
    Groq for natural language summary. Ensures response always includes ai_summary
    with graceful degradation.
    
    Args:
        expenses: List of expense dictionaries with keys: amount, category, date, merchant
        monthly_income: User's monthly income for scoring
        
    Returns:
        Dictionary with health, trend, anomalies, patterns, overspends, savings, ai_summary
    """
    logger.info(f"Generating insights for {len(expenses)} expenses, income=₹{monthly_income}, tier={tier}")
    
    try:
        # Compute all statistical insights (synchronous, fast)
        health = compute_financial_health_score(expenses, monthly_income)
        anomalies = detect_anomalies(expenses)
        patterns = detect_behavioral_patterns(expenses)
        overspends = category_overspend(expenses)
        savings = savings_opportunities(expenses)
        trend = trend_analysis(expenses)
        
        logger.debug(f"Statistical insights computed: health={health['score']}, anomalies={len(anomalies)}, patterns={len(patterns)}")
        
        # Build context for LLM
        summary_ctx = {
            "health_score": health["score"],
            "savings_rate_pct": health["savings_rate"],
            "total_spend_this_month": health.get("total_spend_this_month", 0),
            "trend": trend.get("trend", "steady"),
            "top_overspend_categories": [o["category"] for o in overspends[:3]],  # type: ignore
            "behavioral_flags": [p["type"] for p in patterns],
            "anomaly_count": len(anomalies),
        }
        
        # Generate LLM summary (with paywall gate)
        # DB plan values: "free" = free tier, "basic" = Basic Premium, "pro" = Pro
        # Both "basic" and "pro" paid plans get full AI insights
        PAID_PLANS = {"basic", "pro"}
        if tier not in PAID_PLANS:
            llm_summary = "Upgrade to Premium or Pro to unlock personalized Groq AI financial coaching and insights."
        else:
            llm_summary = await generate_llm_summary(summary_ctx)
        
        result = {
            "health": health,
            "trend": trend,
            "anomalies": anomalies,
            "behavioral_patterns": patterns,
            "category_overspends": overspends,
            "savings_opportunities": savings,
            "ai_summary": llm_summary,  # Always present
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        logger.info("Insights generation completed successfully")
        return result
        
    except Exception as e:
        # Fallback: return partial insights without LLM
        logger.exception(f"Error generating insights: {type(e).__name__}: {str(e)}")
        
        # Ensure response structure is always consistent
        return {
            "health": {"score": 50, "savings_rate": 0, "stability": 0, "essential_ratio": 0},
            "trend": {"current_month_spend": 0, "previous_month_spend": 0, "change_pct": 0, "trend": "unknown"},
            "anomalies": [],
            "behavioral_patterns": [],
            "category_overspends": [],
            "savings_opportunities": [],
            "ai_summary": f"Insights generation encountered an error: {type(e).__name__}. Please refresh or contact support.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "_error": True,  # Flag for frontend debugging
        }

