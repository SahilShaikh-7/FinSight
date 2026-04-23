"""Backend API tests for PaisaIQ Personal Finance AI.

Covers: auth, expenses (CRUD + CSV + summary), insights, portfolio (with live
prices), MF search, affiliates, subscription plans/order (Razorpay 503).
"""
import io
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("BACKEND_BASE_URL") or "https://rupee-optimizer.preview.emergentagent.com"
BASE_URL = BASE_URL.rstrip("/")

# -------- Fixtures --------
@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def qa_user(api):
    """Register (or login) the QA user and return token + profile."""
    email = "qa_tester@paisaiq.app"
    password = "qatest1234"
    name = "QA Tester"

    # Try register; may already exist
    r = api.post(f"{BASE_URL}/api/auth/register", json={
        "email": email, "password": password, "name": name
    })
    assert r.status_code in (200, 400), f"register unexpected {r.status_code}: {r.text}"

    # Login
    r = api.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed: {r.text}"
    data = r.json()
    assert "token" in data and "user" in data
    assert data["user"]["email"] == email
    return {"token": data["token"], "user": data["user"]}


@pytest.fixture(scope="session")
def auth_headers(qa_user):
    return {"Authorization": f"Bearer {qa_user['token']}", "Content-Type": "application/json"}


# -------- Auth --------
class TestAuth:
    def test_register_duplicate_rejected(self, api):
        r = api.post(f"{BASE_URL}/api/auth/register", json={
            "email": "qa_tester@paisaiq.app", "password": "qatest1234", "name": "QA Tester"
        })
        assert r.status_code == 400

    def test_login_wrong_password(self, api):
        r = api.post(f"{BASE_URL}/api/auth/login", json={
            "email": "qa_tester@paisaiq.app", "password": "wrongpass"
        })
        assert r.status_code == 401

    def test_me_requires_token(self, api):
        r = api.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code in (401, 403)

    def test_me_returns_user(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/auth/me", headers=auth_headers)
        assert r.status_code == 200
        u = r.json()
        assert u["email"] == "qa_tester@paisaiq.app"
        assert "id" in u and "plan" in u
        assert "_id" not in u

    def test_profile_update(self, api, auth_headers):
        r = api.patch(f"{BASE_URL}/api/auth/profile",
                      headers=auth_headers,
                      json={"name": "QA Tester Updated", "monthly_income": 85000})
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "QA Tester Updated"
        assert data["monthly_income"] == 85000
        # GET verifies persistence
        r2 = api.get(f"{BASE_URL}/api/auth/me", headers=auth_headers)
        assert r2.json()["monthly_income"] == 85000


# -------- Expenses --------
class TestExpenses:
    created_ids = []

    def test_create_expense_auto_categorized_swiggy(self, api, auth_headers):
        r = api.post(f"{BASE_URL}/api/expenses", headers=auth_headers, json={
            "amount": 450.75, "merchant": "Swiggy", "notes": "dinner"
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["merchant"] == "Swiggy"
        assert d["category"] == "Food & Dining", f"expected Food & Dining got {d['category']}"
        assert d["amount"] == 450.75
        assert "_id" not in d
        assert "user_id" not in d
        TestExpenses.created_ids.append(d["id"])

    def test_create_expense_uber(self, api, auth_headers):
        r = api.post(f"{BASE_URL}/api/expenses", headers=auth_headers, json={
            "amount": 220, "merchant": "Uber", "notes": "ride to office"
        })
        assert r.status_code == 200
        d = r.json()
        # Transport-like category expected
        assert d["category"] in ("Transport", "Travel", "Transportation"), d["category"]
        TestExpenses.created_ids.append(d["id"])

    def test_list_expenses(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/expenses", headers=auth_headers)
        assert r.status_code == 200
        lst = r.json()
        assert isinstance(lst, list)
        assert len(lst) >= 2
        for e in lst:
            assert "_id" not in e
            assert "user_id" not in e

    def test_list_expenses_category_filter(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/expenses?category=Food %26 Dining", headers=auth_headers)
        # URL-encoded & — use params dict to be safe
        r = api.get(f"{BASE_URL}/api/expenses", headers=auth_headers,
                    params={"category": "Food & Dining"})
        assert r.status_code == 200
        for e in r.json():
            assert e["category"] == "Food & Dining"

    def test_expenses_summary(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/expenses/summary", headers=auth_headers)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "health" in d
        assert "top_categories" in d
        assert "daily_trend" in d
        assert isinstance(d["daily_trend"], list)
        assert len(d["daily_trend"]) == 30
        score = d["health"].get("score") if isinstance(d["health"], dict) else None
        assert score is None or (0 <= score <= 100)

    def test_csv_upload(self, api, qa_user):
        csv_text = (
            "date,amount,merchant,notes\n"
            "01/01/2026,1200,Zomato,lunch\n"
            "02/01/2026,3500,Amazon,shopping\n"
            "03/01/2026,450,Ola,cab\n"
            "bad,row,skip,me\n"
        )
        files = {"file": ("test.csv", io.StringIO(csv_text).read().encode(), "text/csv")}
        headers = {"Authorization": f"Bearer {qa_user['token']}"}
        r = requests.post(f"{BASE_URL}/api/expenses/csv", headers=headers, files=files)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["inserted"] == 3
        assert d["skipped"] >= 1

    def test_delete_expense(self, api, auth_headers):
        assert TestExpenses.created_ids, "need an expense id"
        exp_id = TestExpenses.created_ids[0]
        r = api.delete(f"{BASE_URL}/api/expenses/{exp_id}", headers=auth_headers)
        assert r.status_code == 200
        # verify gone via list
        r2 = api.get(f"{BASE_URL}/api/expenses", headers=auth_headers)
        ids = {e["id"] for e in r2.json()}
        assert exp_id not in ids

    def test_delete_nonexistent(self, api, auth_headers):
        r = api.delete(f"{BASE_URL}/api/expenses/{uuid.uuid4()}", headers=auth_headers)
        assert r.status_code == 404


# -------- Insights --------
class TestInsights:
    def test_insights(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/insights", headers=auth_headers, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        for key in ["health", "trend", "anomalies", "behavioral_patterns",
                    "category_overspends", "savings_opportunities"]:
            assert key in d, f"missing key {key}"
        # ai_summary may be string or None/empty depending on LLM call
        assert "ai_summary" in d


# -------- Portfolio --------
class TestPortfolio:
    stock_id = None
    stock2_id = None

    def test_add_stock_holding(self, api, auth_headers):
        r = api.post(f"{BASE_URL}/api/portfolio", headers=auth_headers, json={
            "asset_type": "stock", "symbol": "RELIANCE", "name": "Reliance Industries",
            "quantity": 10, "avg_buy_price": 2500, "sector": "Energy"
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["symbol"] == "RELIANCE"
        assert "_id" not in d
        assert "user_id" not in d
        TestPortfolio.stock_id = d["id"]

    def test_add_second_stock(self, api, auth_headers):
        r = api.post(f"{BASE_URL}/api/portfolio", headers=auth_headers, json={
            "asset_type": "stock", "symbol": "INFY", "name": "Infosys",
            "quantity": 5, "avg_buy_price": 1500, "sector": "IT"
        })
        assert r.status_code == 200
        TestPortfolio.stock2_id = r.json()["id"]

    def test_invalid_asset_type(self, api, auth_headers):
        r = api.post(f"{BASE_URL}/api/portfolio", headers=auth_headers, json={
            "asset_type": "crypto", "symbol": "BTC",
            "quantity": 1, "avg_buy_price": 100
        })
        assert r.status_code == 400

    def test_list_portfolio(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/portfolio", headers=auth_headers, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "holdings" in d and "summary" in d
        assert "allocation_by_sector" in d and "allocation_by_type" in d
        assert "risk_signals" in d
        assert d["summary"]["holding_count"] >= 1
        for h in d["holdings"]:
            assert "_id" not in h
            assert "user_id" not in h
            assert "current_price" in h
            assert "pnl" in h

    def test_refresh_prices(self, api, auth_headers):
        r = api.post(f"{BASE_URL}/api/portfolio/refresh-prices", headers=auth_headers, timeout=90)
        assert r.status_code == 200
        d = r.json()
        assert "updated" in d and "total" in d
        assert d["total"] >= 1

    def test_delete_holding(self, api, auth_headers):
        if not TestPortfolio.stock_id:
            pytest.skip("no holding id")
        r = api.delete(f"{BASE_URL}/api/portfolio/{TestPortfolio.stock_id}",
                       headers=auth_headers)
        assert r.status_code == 200
        # non-existent delete
        r2 = api.delete(f"{BASE_URL}/api/portfolio/{uuid.uuid4()}", headers=auth_headers)
        assert r2.status_code == 404


# -------- Prices / MF --------
class TestPricesMF:
    def test_mf_search_parag(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/prices/mf/search",
                    headers=auth_headers, params={"q": "parag"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "results" in d
        assert isinstance(d["results"], list)
        # AMFI cache should have loaded; at least one Parag Parikh scheme expected
        # (if empty, flag as flaky - cache may not have loaded yet)
        if not d["results"]:
            pytest.fail("MF search returned empty results for 'parag' - AMFI cache may not be loaded")
        first = d["results"][0]
        assert "scheme_code" in first or "code" in first or "scheme_name" in first or "name" in first


# -------- Affiliates --------
class TestAffiliates:
    def test_recommendations(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/affiliates/recommendations", headers=auth_headers)
        assert r.status_code == 200
        d = r.json()
        assert "recommendations" in d
        assert isinstance(d["recommendations"], list)


# -------- Subscription --------
class TestSubscription:
    def test_plans(self, api):
        r = api.get(f"{BASE_URL}/api/subscription/plans")
        assert r.status_code == 200
        d = r.json()
        plan_ids = {p["id"] for p in d["plans"]}
        assert {"basic", "pro"}.issubset(plan_ids)

    def test_create_order_real_razorpay_basic(self, api, auth_headers):
        """With real Razorpay test keys set, non-admin should get a real order."""
        r = api.post(f"{BASE_URL}/api/subscription/create-order",
                     headers=auth_headers, json={"plan": "basic"})
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        d = r.json()
        assert "order_id" in d and d["order_id"].startswith("order_"), d
        assert d["amount"] == 9900  # 99 INR in paise
        assert d["currency"] == "INR"
        assert "key_id" in d and d["key_id"].startswith("rzp_")
        assert d["plan"] == "basic"

    def test_create_order_invalid_plan(self, api, auth_headers):
        r = api.post(f"{BASE_URL}/api/subscription/create-order",
                     headers=auth_headers, json={"plan": "enterprise"})
        assert r.status_code == 400


# -------- Iteration 2: Quick insights, Challenge, Admin, Insights cache --------
class TestQuickInsights:
    """GET /api/insights/quick — fast, no LLM, no ai_summary."""

    def test_quick_insights_shape_and_speed(self, api, auth_headers):
        t0 = time.time()
        r = api.get(f"{BASE_URL}/api/insights/quick", headers=auth_headers, timeout=15)
        elapsed = time.time() - t0
        assert r.status_code == 200, r.text
        d = r.json()
        for key in ["health", "trend", "anomalies", "behavioral_patterns",
                    "category_overspends", "savings_opportunities"]:
            assert key in d, f"missing key {key}"
        assert "ai_summary" not in d, "ai_summary must NOT be in /insights/quick"
        # Should be fast (no LLM). Allow generous 10s for cold cache.
        assert elapsed < 10, f"/insights/quick too slow: {elapsed:.1f}s"
        assert '"_id"' not in r.text


class TestInsightsCache:
    def test_insights_cached_second_call_fast(self, api, auth_headers):
        # First call may populate cache
        r1 = api.get(f"{BASE_URL}/api/insights", headers=auth_headers, timeout=90)
        assert r1.status_code == 200
        t0 = time.time()
        r2 = api.get(f"{BASE_URL}/api/insights", headers=auth_headers, timeout=30)
        elapsed = time.time() - t0
        assert r2.status_code == 200
        # Cached call should be noticeably fast
        assert elapsed < 5, f"Cached /insights too slow: {elapsed:.1f}s"
        # force=true should still 200 (re-runs LLM; may be slower)
        r3 = api.get(f"{BASE_URL}/api/insights?force=true", headers=auth_headers, timeout=90)
        assert r3.status_code == 200


class TestChallenge:
    def test_challenge_shape(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/challenge", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ["income_set", "monthly_income", "days_active",
                  "expected_income_to_date", "total_spent_since_signup",
                  "saved", "milestones", "achieved_milestones",
                  "next_milestone", "progress_pct", "is_completed",
                  "new_milestones"]:
            assert k in d, f"missing key {k}"
        assert d["milestones"] == [1000, 5000, 10000]
        assert isinstance(d["achieved_milestones"], list)
        assert d["saved"] >= 0
        assert '"_id"' not in r.text

    def test_challenge_reflects_income_bump(self, api, auth_headers):
        # Bump monthly_income high enough to trigger milestones
        rp = api.patch(f"{BASE_URL}/api/auth/profile",
                       headers=auth_headers,
                       json={"monthly_income": 50000})
        assert rp.status_code == 200
        r = api.get(f"{BASE_URL}/api/challenge", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["income_set"] is True
        assert d["monthly_income"] == 50000
        # saved == max(0, expected - spent)
        expected = d["expected_income_to_date"] - d["total_spent_since_signup"]
        assert d["saved"] == round(max(0.0, expected), 2) or abs(d["saved"] - max(0.0, expected)) < 1.0
        # With 50k/mo and short signup, saved should easily be >= 1000
        if d["saved"] >= 1000:
            assert 1000 in d["achieved_milestones"], d
        # progress_pct bounded
        assert 0 <= d["progress_pct"] <= 100


# -------- Admin --------
@pytest.fixture(scope="session")
def admin_user(api):
    email = "sahil68shaikh68@gmail.com"
    password = "admin1234"
    # Try register (may already exist)
    api.post(f"{BASE_URL}/api/auth/register", json={
        "email": email, "password": password, "name": "Sahil Admin"
    })
    r = api.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"admin login failed: {r.text}"
    data = r.json()
    return {"token": data["token"], "user": data["user"]}


@pytest.fixture(scope="session")
def admin_headers(admin_user):
    return {"Authorization": f"Bearer {admin_user['token']}", "Content-Type": "application/json"}


class TestAdmin:
    def test_admin_me_is_admin_and_pro(self, api, admin_headers):
        r = api.get(f"{BASE_URL}/api/auth/me", headers=admin_headers)
        assert r.status_code == 200, r.text
        u = r.json()
        assert u["is_admin"] is True, u
        assert u["plan"] == "pro", u
        assert "_id" not in u

    def test_admin_create_order_basic_returns_admin_grant(self, api, admin_headers):
        r = api.post(f"{BASE_URL}/api/subscription/create-order",
                     headers=admin_headers, json={"plan": "basic"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("admin_grant") is True, d
        assert d.get("plan") == "basic"
        assert "order_id" not in d  # must NOT be a razorpay order

    def test_admin_create_order_pro_returns_admin_grant(self, api, admin_headers):
        r = api.post(f"{BASE_URL}/api/subscription/create-order",
                     headers=admin_headers, json={"plan": "pro"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("admin_grant") is True
        assert d.get("plan") == "pro"


# -------- No _id leak cross-check --------
class TestNoIdLeak:
    def test_no_mongo_id_in_common_responses(self, api, auth_headers):
        for ep in ["/api/auth/me", "/api/expenses", "/api/expenses/summary",
                   "/api/portfolio", "/api/affiliates/recommendations",
                   "/api/subscription/plans", "/api/insights/quick",
                   "/api/challenge"]:
            r = api.get(f"{BASE_URL}{ep}", headers=auth_headers, timeout=60)
            assert r.status_code == 200, f"{ep} -> {r.status_code}"
            text = r.text
            assert '"_id"' not in text, f"{ep} leaked _id"
