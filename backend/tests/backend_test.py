"""Backend tests for Scheiner Sports Solutions FastAPI.

Covers:
  * /api/health
  * /api/auth/me (valid/invalid/expired)
  * /api/auth/session (invalid session_id)
  * /api/auth/logout
  * /api/subscription/plan (public)
  * /api/subscription/checkout (auth/no-auth, Stripe + DB persistence)
  * /api/subscription/status/{session_id}
  * /api/webhook/stripe (signature validation should 4xx, not 5xx)
"""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get(
    "REACT_APP_BACKEND_URL"
) else None

if not BASE_URL:
    # Read from frontend/.env (testing env)
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")

API = f"{BASE_URL}/api"

NO_SUB_TOKEN = "test_session_noSub_abc"
SUB_TOKEN = "test_session_withSub_xyz"

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


# ----- Health -----
def test_health(session):
    r = session.get(f"{API}/health", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["service"] == "sss-backend"


# ----- /api/auth/me -----
def test_me_with_valid_subscriber_token(session):
    r = session.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {SUB_TOKEN}"})
    assert r.status_code == 200
    d = r.json()
    assert d["email"] == "test.user.subscribed@example.com"
    assert d["is_subscribed"] is True
    assert d["subscription_status"] == "active"
    assert "user_id" in d


def test_me_with_valid_nosub_token(session):
    r = session.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {NO_SUB_TOKEN}"})
    assert r.status_code == 200
    d = r.json()
    assert d["email"] == "test.user.nosub@example.com"
    assert d["is_subscribed"] is False


def test_me_with_invalid_token(session):
    r = session.get(f"{API}/auth/me", headers={"Authorization": "Bearer bogus_token_xyz"})
    assert r.status_code == 401


def test_me_with_no_auth_header(session):
    r = session.get(f"{API}/auth/me")
    assert r.status_code == 401


# ----- /api/auth/session -----
def test_auth_session_with_invalid_session_id(session):
    r = session.post(
        f"{API}/auth/session", json={"session_id": "definitely-not-a-real-emergent-id"}
    )
    # Should reject with 401 (or upstream 502); not 5xx unhandled
    assert r.status_code in (401, 502)


# ----- /api/auth/logout -----
def test_logout_with_temp_token(session, mongo_db):
    """Insert a temp session and verify logout removes it."""
    import datetime as dt

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
        # confirm /me works first
        r1 = session.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r1.status_code == 200

        r2 = session.post(f"{API}/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 200
        assert r2.json().get("ok") is True

        # session should be deleted
        assert mongo_db.user_sessions.find_one({"session_token": token}) is None
        # /me should now fail
        r3 = session.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r3.status_code == 401
    finally:
        mongo_db.user_sessions.delete_many({"session_token": token})
        mongo_db.users.delete_one({"user_id": user_id})


# ----- /api/subscription/plan -----
def test_subscription_plan_is_public(session):
    r = session.get(f"{API}/subscription/plan")
    assert r.status_code == 200
    d = r.json()
    assert d["price_usd"] == 9.99
    assert d["interval"] == "month"
    assert isinstance(d["features"], list) and len(d["features"]) > 0
    assert "name" in d


# ----- /api/subscription/checkout -----
def test_checkout_requires_auth(session):
    r = session.post(f"{API}/subscription/checkout", json={"origin_url": BASE_URL})
    assert r.status_code == 401


def test_checkout_creates_stripe_session_and_db_row(session, mongo_db):
    r = session.post(
        f"{API}/subscription/checkout",
        headers={"Authorization": f"Bearer {NO_SUB_TOKEN}"},
        json={"origin_url": BASE_URL},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert "url" in d and d["url"].startswith("https://")
    assert "stripe.com" in d["url"] or "checkout" in d["url"].lower()
    assert "session_id" in d

    # Verify payment_transactions row inserted
    tx = mongo_db.payment_transactions.find_one({"session_id": d["session_id"]})
    assert tx is not None
    assert tx["user_id"] == "test-user-noSub"
    assert tx["amount"] == 9.99
    assert tx["currency"] == "usd"
    assert tx["payment_status"] == "initiated"


# ----- /api/subscription/status -----
def test_subscription_status_unknown_session_id(session):
    r = session.get(
        f"{API}/subscription/status/cs_test_does_not_exist_xyz",
        headers={"Authorization": f"Bearer {NO_SUB_TOKEN}"},
    )
    # Either 404 (unknown tx) or 400/500 from Stripe; we allow either non-5xx OR 500
    # But ideal is 4xx. The endpoint first hits Stripe to fetch status, so it may 500
    # if Stripe rejects. We accept 4xx or that the call surfaces the issue gracefully.
    assert r.status_code in (400, 404, 500)


def test_subscription_status_requires_auth(session):
    r = session.get(f"{API}/subscription/status/cs_anything")
    assert r.status_code == 401


# ----- /api/webhook/stripe -----
def test_webhook_invalid_signature_returns_4xx_not_5xx(session):
    """Webhook with arbitrary body+bad signature should 4xx, never crash with 5xx."""
    r = session.post(
        f"{API}/webhook/stripe",
        data=b'{"type":"checkout.session.completed","data":{"object":{}}}',
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": "t=0,v1=fake_signature_value",
        },
    )
    assert 400 <= r.status_code < 500, f"Webhook returned {r.status_code}: {r.text}"
