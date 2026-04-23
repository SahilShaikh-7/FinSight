"""Affiliate recommendation engine — rule-based.
Maps user spending patterns to relevant financial products.
"""
from collections import defaultdict
from typing import List, Dict, Any

# Curated product catalog (no real affiliate links; users integrate later)
PRODUCTS = [
    {
        "id": "cc_cashback_shopping",
        "type": "credit_card",
        "name": "Amazon Pay ICICI Credit Card",
        "tagline": "5% cashback on Amazon, 2% on partners",
        "best_for": "Heavy online shoppers",
        "tags": ["Shopping"],
        "cta": "Apply Now",
        "link": "#",
        "bank": "ICICI Bank",
    },
    {
        "id": "cc_dining",
        "type": "credit_card",
        "name": "Swiggy HDFC Credit Card",
        "tagline": "10% cashback on Swiggy, dining & entertainment",
        "best_for": "Foodies who order often",
        "tags": ["Food & Dining", "Entertainment"],
        "cta": "Apply Now",
        "link": "#",
        "bank": "HDFC Bank",
    },
    {
        "id": "cc_fuel",
        "type": "credit_card",
        "name": "BPCL SBI Octane Card",
        "tagline": "7.25% valueback on fuel",
        "best_for": "Daily commuters",
        "tags": ["Transport"],
        "cta": "Apply Now",
        "link": "#",
        "bank": "SBI Card",
    },
    {
        "id": "cc_travel",
        "type": "credit_card",
        "name": "Axis Atlas Credit Card",
        "tagline": "5X miles on travel, lounge access",
        "best_for": "Frequent travellers",
        "tags": ["Travel"],
        "cta": "Apply Now",
        "link": "#",
        "bank": "Axis Bank",
    },
    {
        "id": "sa_high_yield",
        "type": "savings_account",
        "name": "IDFC FIRST Savings Account",
        "tagline": "Up to 7% interest, zero balance",
        "best_for": "Students & first earners",
        "tags": ["always"],
        "cta": "Open Account",
        "link": "#",
        "bank": "IDFC FIRST Bank",
    },
    {
        "id": "sa_neobank",
        "type": "savings_account",
        "name": "Jupiter Money Account",
        "tagline": "0 forex markup, auto-savings pots",
        "best_for": "Digital-first users",
        "tags": ["always"],
        "cta": "Get Jupiter",
        "link": "#",
        "bank": "Federal Bank (Jupiter)",
    },
    {
        "id": "inv_mf_sip",
        "type": "investment",
        "name": "Groww — Start a SIP",
        "tagline": "Direct mutual funds, 0 commission",
        "best_for": "First-time investors",
        "tags": ["Investments"],
        "cta": "Start SIP",
        "link": "#",
        "bank": "Groww",
    },
    {
        "id": "inv_stocks",
        "type": "investment",
        "name": "Zerodha Kite",
        "tagline": "Free equity delivery, ₹20 F&O",
        "best_for": "Active traders",
        "tags": ["Investments"],
        "cta": "Open Demat",
        "link": "#",
        "bank": "Zerodha",
    },
]


def recommend(expenses: List[Dict[str, Any]], top_n: int = 6) -> List[Dict[str, Any]]:
    if not expenses:
        # Show safe defaults
        return [p for p in PRODUCTS if "always" in p["tags"]][:top_n]

    cat_spend = defaultdict(float)
    for e in expenses:
        cat_spend[e.get("category", "Other")] += float(e["amount"])
    # Rank categories
    top_cats = sorted(cat_spend.items(), key=lambda x: -x[1])
    matched_ids = set()
    recs = []
    for cat, _ in top_cats:
        for p in PRODUCTS:
            if cat in p["tags"] and p["id"] not in matched_ids:
                recs.append({**p, "match_reason": f"You spend heavily on {cat}"})
                matched_ids.add(p["id"])
                if len(recs) >= top_n:
                    return recs
    # Fill with "always" products
    for p in PRODUCTS:
        if "always" in p["tags"] and p["id"] not in matched_ids:
            recs.append({**p, "match_reason": "Great for first earners"})
            matched_ids.add(p["id"])
            if len(recs) >= top_n:
                break
    return recs
