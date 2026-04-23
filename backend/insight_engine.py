"""AI Insight Engine — rule-based + statistical + LLM summaries.
Generates actionable insights like overspending, anomalies, trends, behavioral patterns.
"""
import os
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from statistics import mean, pstdev
from typing import List, Dict, Any
import logging

from categorizer import is_essential, ESSENTIAL_CATEGORIES

logger = logging.getLogger(__name__)


def _parse_date(d):
    if isinstance(d, datetime):
        return d
    try:
        return datetime.fromisoformat(str(d).replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


def compute_financial_health_score(expenses: List[Dict[str, Any]], monthly_income: float = 0) -> Dict[str, Any]:
    """Score 0-100 based on:
      - savings rate (40 pts)
      - spending stability (30 pts) — inverse of coefficient of variation
      - essential vs non-essential ratio (30 pts)
    """
    if not expenses:
        return {"score": 50, "savings_rate": 0, "stability": 0, "essential_ratio": 0, "breakdown": {}}

    now = datetime.now(timezone.utc)
    # Current month expenses
    this_month = [e for e in expenses if _parse_date(e["date"]).month == now.month and _parse_date(e["date"]).year == now.year]
    total_spend = sum(float(e["amount"]) for e in this_month)

    # Savings rate
    savings_rate = 0.0
    if monthly_income > 0:
        savings_rate = max(0.0, min(1.0, (monthly_income - total_spend) / monthly_income))
    savings_pts = savings_rate * 40

    # Stability — stdev of daily spends (last 30 days)
    daily = defaultdict(float)
    cutoff = now - timedelta(days=30)
    for e in expenses:
        d = _parse_date(e["date"])
        if d >= cutoff:
            daily[d.strftime("%Y-%m-%d")] += float(e["amount"])
    vals = list(daily.values())
    if len(vals) >= 2 and mean(vals) > 0:
        cv = pstdev(vals) / mean(vals)
        stability_pts = max(0.0, (1 - min(cv, 1.5) / 1.5)) * 30
    else:
        stability_pts = 15.0

    # Essential ratio
    essential_amt = sum(float(e["amount"]) for e in this_month if is_essential(e.get("category", "")))
    essential_ratio = essential_amt / total_spend if total_spend > 0 else 0
    # Ideal 50-70% essential
    if 0.5 <= essential_ratio <= 0.7:
        essential_pts = 30
    elif 0.4 <= essential_ratio < 0.5 or 0.7 < essential_ratio <= 0.8:
        essential_pts = 22
    elif essential_ratio < 0.4:
        essential_pts = 10  # lots of wants
    else:
        essential_pts = 15  # too skewed to essentials (low savings headroom)

    score = round(savings_pts + stability_pts + essential_pts)
    return {
        "score": max(0, min(100, score)),
        "savings_rate": round(savings_rate * 100, 1),
        "stability": round(stability_pts / 30 * 100, 1),
        "essential_ratio": round(essential_ratio * 100, 1),
        "breakdown": {
            "savings_pts": round(savings_pts, 1),
            "stability_pts": round(stability_pts, 1),
            "essential_pts": round(essential_pts, 1),
        },
        "total_spend_this_month": round(total_spend, 2),
    }


def detect_anomalies(expenses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Z-score anomaly detection per category."""
    by_cat = defaultdict(list)
    for e in expenses:
        by_cat[e.get("category", "Other")].append(e)

    anomalies = []
    for cat, items in by_cat.items():
        if len(items) < 5:
            continue
        amounts = [float(i["amount"]) for i in items]
        mu = mean(amounts)
        sd = pstdev(amounts) or 1
        for it in items[-20:]:
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
    return anomalies[:10]


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
    by_month_cat = defaultdict(lambda: defaultdict(float))
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
    for cat, amt in this_mo.items():
        prev_amts = [by_month_cat.get(pm, {}).get(cat, 0) for pm in prev_months]
        prev_avg = mean(prev_amts) if prev_amts else 0
        if prev_avg > 0 and amt > prev_avg * 1.3:
            diff = amt - prev_avg
            insights.append({
                "type": "overspend",
                "severity": "high" if amt > prev_avg * 1.6 else "medium",
                "category": cat,
                "this_month": round(amt, 2),
                "prev_avg": round(prev_avg, 2),
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
    by_month = defaultdict(float)
    for e in expenses:
        d = _parse_date(e["date"])
        by_month[(d.year, d.month)] += float(e["amount"])
    cur = by_month.get((now.year, now.month), 0)
    prev_m, prev_y = (now.month - 1, now.year) if now.month > 1 else (12, now.year - 1)
    prev = by_month.get((prev_y, prev_m), 0)
    pct = ((cur - prev) / prev * 100) if prev > 0 else 0
    return {
        "current_month_spend": round(cur, 2),
        "previous_month_spend": round(prev, 2),
        "change_pct": round(pct, 1),
        "trend": "up" if pct > 5 else "down" if pct < -5 else "steady",
    }


async def generate_llm_summary(insights_data: Dict[str, Any]) -> str:
    """Use Claude Sonnet 4.5 via emergentintegrations to produce a friendly summary."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import uuid as _uuid
        key = os.environ.get("EMERGENT_LLM_KEY")
        if not key:
            return "Set EMERGENT_LLM_KEY to get AI-powered summaries."
        chat = LlmChat(
            api_key=key,
            session_id=f"insight-{_uuid.uuid4()}",
            system_message=(
                "You are a personal finance coach for young Indians (students, freshers). "
                "You give actionable, friendly, specific advice in INR. "
                "Keep responses under 120 words, use ₹ symbol, avoid jargon, sound warm but honest."
            ),
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        prompt = (
            "Based on this user's finance data, write a short motivating summary + 2 concrete next-step "
            "recommendations. Do NOT use markdown bullets or headers, just flowing text.\n\n"
            f"Data: {insights_data}"
        )
        response = await chat.send_message(UserMessage(text=prompt))
        return response.strip()
    except Exception as e:
        logger.exception("LLM summary failed")
        return f"(AI summary unavailable: {str(e)[:60]}) Based on your data, focus on reducing your top non-essential category this month."


async def generate_all_insights(expenses: List[Dict[str, Any]], monthly_income: float = 0) -> Dict[str, Any]:
    health = compute_financial_health_score(expenses, monthly_income)
    anomalies = detect_anomalies(expenses)
    patterns = detect_behavioral_patterns(expenses)
    overspends = category_overspend(expenses)
    savings = savings_opportunities(expenses)
    trend = trend_analysis(expenses)

    summary_ctx = {
        "health_score": health["score"],
        "savings_rate_pct": health["savings_rate"],
        "total_spend_this_month": health.get("total_spend_this_month", 0),
        "trend": trend,
        "top_overspend_categories": [o["category"] for o in overspends[:3]],
        "behavioral_flags": [p["type"] for p in patterns],
        "anomaly_count": len(anomalies),
    }
    llm_summary = await generate_llm_summary(summary_ctx)

    return {
        "health": health,
        "trend": trend,
        "anomalies": anomalies,
        "behavioral_patterns": patterns,
        "category_overspends": overspends,
        "savings_opportunities": savings,
        "ai_summary": llm_summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
