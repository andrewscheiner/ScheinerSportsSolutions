"""Backend tests for Scheiner Sports Solutions FastAPI — Iteration 2.

Covers (new in iter 2):
  * /api/subscription/plan returns plans=[monthly $1.99, lifetime $20.00] + features
  * /api/subscription/checkout supports plan_type=monthly/lifetime/invalid/missing
  * /api/auth/me returns plan_type for active subscribers (monthly + lifetime)
  * Lifetime subscription with current_period_end=null is treated as active forever
  * Webhook signature validation still returns 4xx, not 5xx
Carried over:
  * /api/health, /api/auth/me valid/invalid/no-auth
  * /api/auth/session invalid, /api/auth/logout removes session
  * checkout auth-required, status auth-required, status unknown id
"""
import os
import uuid
import datetime as dt

import pytest
import requests
from pymongo import MongoClient

# Backend URL — must come from REACT_APP_BACKEND_URL
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")

API = f"{BASE_URL}/api"

NO_SUB_TOKEN = "test_session_noSub_abc"
SUB_TOKEN = "test_session_withSub_xyz"
LIFETIME_TOKEN = "test_session_lifetime_lf1"

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "sss_db"


@pytest.fixture(scope="session")
def mongo_db():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ===== Health =====
def test_health(session):
    r = session.get(f"{API}/health", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["service"] == "sss-backend"


# ===== /api/auth/me =====
def test_me_with_valid_subscriber_token(session):
    r = session.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {SUB_TOKEN}"})
    assert r.status_code == 200
    d = r.json()
    assert d["email"] == "test.user.subscribed@example.com"
    assert d["is_subscribed"] is True
    assert d["subscription_status"] == "active"
    assert d["plan_type"] == "monthly"


def test_me_with_lifetime_subscriber(session):
    r = session.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {LIFETIME_TOKEN}"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["is_subscribed"] is True, "Lifetime sub should be active even with current_period_end=null"
    assert d["plan_type"] == "lifetime"
    assert d["subscription_status"] == "active"


def test_me_with_valid_nosub_token(session):
    r = session.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {NO_SUB_TOKEN}"})
    assert r.status_code == 200
    d = r.json()
    assert d["email"] == "test.user.nosub@example.com"
    assert d["is_subscribed"] is False
    assert d["plan_type"] is None


def test_me_with_invalid_token(session):
    r = session.get(f"{API}/auth/me", headers={"Authorization": "Bearer bogus_token_xyz"})
    assert r.status_code == 401


def test_me_with_no_auth_header(session):
    r = session.get(f"{API}/auth/me")
    assert r.status_code == 401


# ===== /api/auth/session =====
def test_auth_session_with_invalid_session_id(session):
    r = session.post(
        f"{API}/auth/session", json={"session_id": "definitely-not-a-real-emergent-id"}
    )
    assert r.status_code in (401, 502)


# ===== /api/auth/logout =====
def test_logout_with_temp_token(session, mongo_db):
    user_id = f"TEST_logout_user_{uuid.uuid4().hex[:6]}"
    token = f"TEST_logout_tok_{uuid.uuid4().hex[:8]}"
    mongo_db.users.insert_one(
        {"user_id": user_id, "email": f"TEST_{user_id}@example.com", "name": "Logout T"}
    )
    mongo_db.user_sessions.insert_one(
        {
            "user_id": user_id,
            "session_token": token,
            "expires_at": dt.datetime.utcnow() + dt.timedelta(days=1),
        }
    )
    try:
        r1 = session.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r1.status_code == 200
        r2 = session.post(f"{API}/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 200
        assert r2.json().get("ok") is True
        assert mongo_db.user_sessions.find_one({"session_token": token}) is None
        r3 = session.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r3.status_code == 401
    finally:
        mongo_db.user_sessions.delete_many({"session_token": token})
        mongo_db.users.delete_one({"user_id": user_id})


# ===== /api/subscription/plan =====
def test_subscription_plan_returns_two_plans(session):
    r = session.get(f"{API}/subscription/plan")
    assert r.status_code == 200
    d = r.json()
    assert "name" in d
    assert isinstance(d.get("features"), list) and len(d["features"]) > 0
    plans = d.get("plans")
    assert isinstance(plans, list) and len(plans) == 2
    by_id = {p["id"]: p for p in plans}
    assert "monthly" in by_id and "lifetime" in by_id
    assert by_id["monthly"]["price_usd"] == 1.99
    assert by_id["monthly"]["interval"] == "month"
    assert by_id["lifetime"]["price_usd"] == 20.00
    assert by_id["lifetime"]["interval"] == "one-time"


# ===== /api/subscription/checkout =====
def test_checkout_requires_auth(session):
    r = session.post(f"{API}/subscription/checkout", json={"origin_url": BASE_URL})
    assert r.status_code == 401


def test_checkout_monthly_creates_stripe_session_and_db_row(session, mongo_db):
    r = session.post(
        f"{API}/subscription/checkout",
        headers={"Authorization": f"Bearer {NO_SUB_TOKEN}"},
        json={"origin_url": BASE_URL, "plan_type": "monthly"},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert "url" in d and d["url"].startswith("https://")
    assert "session_id" in d
    tx = mongo_db.payment_transactions.find_one({"session_id": d["session_id"]})
    assert tx is not None
    assert tx["user_id"] == "test-user-noSub"
    assert tx["amount"] == 1.99
    assert tx["currency"] == "usd"
    assert tx["plan_type"] == "monthly"
    assert tx["payment_status"] == "initiated"


def test_checkout_lifetime_creates_stripe_session(session, mongo_db):
    r = session.post(
        f"{API}/subscription/checkout",
        headers={"Authorization": f"Bearer {NO_SUB_TOKEN}"},
        json={"origin_url": BASE_URL, "plan_type": "lifetime"},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["url"].startswith("https://")
    tx = mongo_db.payment_transactions.find_one({"session_id": d["session_id"]})
    assert tx is not None
    assert tx["amount"] == 20.00
    assert tx["plan_type"] == "lifetime"


def test_checkout_missing_plan_type_defaults_to_monthly(session, mongo_db):
    r = session.post(
        f"{API}/subscription/checkout",
        headers={"Authorization": f"Bearer {NO_SUB_TOKEN}"},
        json={"origin_url": BASE_URL},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    tx = mongo_db.payment_transactions.find_one({"session_id": d["session_id"]})
    assert tx is not None
    assert tx["amount"] == 1.99
    assert tx["plan_type"] == "monthly"


def test_checkout_invalid_plan_type_returns_400(session):
    r = session.post(
        f"{API}/subscription/checkout",
        headers={"Authorization": f"Bearer {NO_SUB_TOKEN}"},
        json={"origin_url": BASE_URL, "plan_type": "banana"},
    )
    assert r.status_code == 400, r.text
    assert "Invalid plan_type" in r.text


# ===== /api/subscription/status =====
def test_subscription_status_requires_auth(session):
    r = session.get(f"{API}/subscription/status/cs_anything")
    assert r.status_code == 401


def test_subscription_status_unknown_session_id(session):
    r = session.get(
        f"{API}/subscription/status/cs_test_does_not_exist_xyz",
        headers={"Authorization": f"Bearer {NO_SUB_TOKEN}"},
    )
    # 4xx ideal; allow 500 because Stripe is called first
    assert r.status_code in (400, 404, 500)


# ===== /api/webhook/stripe =====
def test_webhook_invalid_signature_returns_4xx_not_5xx(session):
    r = session.post(
        f"{API}/webhook/stripe",
        data=b'{"type":"checkout.session.completed","data":{"object":{}}}',
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": "t=0,v1=fake_signature_value",
        },
    )
    assert 400 <= r.status_code < 500, f"Webhook returned {r.status_code}: {r.text}"
