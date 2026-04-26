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
    """Detect late-night, weekend spikes, impulse (small frequent) spending."""
    patterns = []
    now = datetime.now(timezone.utc)
    last_30 = [e for e in expenses if _parse_date(e["date"]) >= now - timedelta(days=30)]
    if not last_30:
        return []

    total = sum(float(e["amount"]) for e in last_30)

    # Late night (10pm-4am)
    late_night = [e for e in last_30 if _parse_date(e["date"]).hour >= 22 or _parse_date(e["date"]).hour <= 4]
    ln_amt = sum(float(e["amount"]) for e in late_night)
    if total > 0 and ln_amt / total > 0.15:
        patterns.append({
            "type": "late_night",
            "severity": "medium",
            "message": f"You spent ₹{ln_amt:.0f} ({ln_amt/total*100:.0f}%) during late-night hours. Late-night spends are often impulse buys.",
            "count": len(late_night),
        })

    # Weekend spikes
    weekend = [e for e in last_30 if _parse_date(e["date"]).weekday() >= 5]
    we_amt = sum(float(e["amount"]) for e in weekend)
    weekday_amt = total - we_amt
    if weekday_amt > 0 and we_amt / max(weekday_amt, 1) > 0.6:
        patterns.append({
            "type": "weekend_spike",
            "severity": "medium",
            "message": f"Weekends account for ₹{we_amt:.0f} — {(we_amt/total)*100:.0f}% of your spend. Watch out for weekend splurges.",
        })

    # Impulse — many small non-essential spends
    impulse = [e for e in last_30 if float(e["amount"]) < 500 and not is_essential(e.get("category", ""))]
    if len(impulse) >= 15:
        imp_amt = sum(float(e["amount"]) for e in impulse)
        patterns.append({
            "type": "impulse",
            "severity": "low" if imp_amt < 3000 else "medium",
            "message": f"{len(impulse)} small non-essential buys (₹{imp_amt:.0f} total). These add up — try a 24-hour cooling-off rule.",
        })
    return patterns


def category_overspend(expenses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compare this month vs avg of previous 3 months per category."""
    now = datetime.now(timezone.utc)
    this_mo_key = (now.year, now.month)
    by_month_cat: DefaultDict[Tuple[int, int], DefaultDict[str, float]] = defaultdict(lambda: defaultdict(float))  # type: ignore
    for e in expenses:
        d = _parse_date(e["date"])
        by_month_cat[(d.year, d.month)][e.get("category", "Other")] += float(e["amount"])

    this_mo = by_month_cat.get(this_mo_key, {})
    # Previous 3 months
    prev_months = []
    for i in range(1, 4):
        m = now.month - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1
        prev_months.append((y, m))
    insights = []
    for cat, amt in this_mo.items():  # type: ignore
        prev_amts = [by_month_cat.get(pm, {}).get(cat, 0) for pm in prev_months]
        prev_avg = mean(prev_amts) if prev_amts else 0
        if prev_avg > 0 and amt > prev_avg * 1.3:
            diff = amt - prev_avg
            insights.append({
                "type": "overspend",
                "severity": "high" if amt > prev_avg * 1.6 else "medium",
                "category": cat,
                "this_month": round(amt, 2),  # type: ignore
                "prev_avg": round(prev_avg, 2),  # type: ignore
                "message": f"{cat} spend of ₹{amt:.0f} is {((amt/prev_avg-1)*100):.0f}% higher than your 3-month average (₹{prev_avg:.0f}). You could save ₹{diff:.0f}.",
            })
    return insights


def savings_opportunities(expenses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Find specific, actionable savings ideas."""
    now = datetime.now(timezone.utc)
    last_30 = [e for e in expenses if _parse_date(e["date"]) >= now - timedelta(days=30)]
    ops = []

    # Food delivery suggestion
    food_delivery = [e for e in last_30 if e.get("category") == "Food & Dining"]
    fd_amt = sum(float(e["amount"]) for e in food_delivery)
    if fd_amt > 3000:
        potential = fd_amt * 0.4
        ops.append({
            "type": "saving",
            "severity": "high",
            "message": f"You spent ₹{fd_amt:.0f} on food delivery in 30 days. Cooking 3 meals/week at home could save ~₹{potential:.0f}.",
        })

    # Entertainment subscriptions duplicate
    ent = [e for e in last_30 if e.get("category") == "Entertainment"]
    if len(ent) >= 3:
        ent_amt = sum(float(e["amount"]) for e in ent)
        ops.append({
            "type": "saving",
            "severity": "medium",
            "message": f"You have {len(ent)} entertainment charges (₹{ent_amt:.0f}). Audit subscriptions — most users save ₹300-600/month by cutting duplicates.",
        })

    # Shopping
    shop = [e for e in last_30 if e.get("category") == "Shopping"]
    shop_amt = sum(float(e["amount"]) for e in shop)
    if shop_amt > 5000:
        ops.append({
            "type": "saving",
            "severity": "medium",
            "message": f"Shopping of ₹{shop_amt:.0f} this month. Try a 1-week no-shopping challenge to save ~₹{shop_amt*0.3:.0f}.",
        })
    return ops


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

