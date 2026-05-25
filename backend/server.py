"""
Scheiner Sports Solutions — FastAPI backend.
Handles:
  * Emergent Google OAuth session exchange + persistent user/session storage
  * Stripe Checkout for single-tier monthly subscription ($9.99/mo)
  * Subscription status + webhook handling
"""
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout,
    CheckoutSessionRequest,
)

load_dotenv()

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
STRIPE_API_KEY = os.environ["STRIPE_API_KEY"]
MONTHLY_PRICE_USD = float(os.environ.get("MONTHLY_PRICE_USD", "1.99"))
LIFETIME_PRICE_USD = float(os.environ.get("LIFETIME_PRICE_USD", "20.00"))
SUBSCRIPTION_NAME = os.environ.get("SUBSCRIPTION_NAME", "Pro")

PLAN_PRICES = {
    "monthly": MONTHLY_PRICE_USD,
    "lifetime": LIFETIME_PRICE_USD,
}

EMERGENT_AUTH_DATA_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"

# ----------------------------------------------------------------------------
# App + DB setup
# ----------------------------------------------------------------------------
app = FastAPI(title="Scheiner Sports Solutions API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client[DB_NAME]


# ----------------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------------
class SessionExchangeRequest(BaseModel):
    session_id: str


class UserOut(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    is_subscribed: bool = False
    subscription_status: str = "inactive"  # active | inactive | cancelled
    plan_type: Optional[str] = None  # "monthly" | "lifetime" | None


class CheckoutCreateRequest(BaseModel):
    origin_url: str
    plan_type: str = "monthly"  # "monthly" or "lifetime"


# ----------------------------------------------------------------------------
# Auth helpers
# ----------------------------------------------------------------------------
async def get_current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    """Resolve current user from a Bearer session_token in the Authorization header."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()

    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")

    expires_at = session["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")

    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def _user_to_out(user: dict) -> UserOut:
    sub = await db.subscriptions.find_one({"user_id": user["user_id"]}, {"_id": 0})
    is_active = False
    status = "inactive"
    plan_type = None
    if sub:
        status = sub.get("status", "inactive")
        plan_type = sub.get("plan_type")
        if status == "active":
            if plan_type == "lifetime":
                is_active = True
            else:
                period_end = sub.get("current_period_end")
                if period_end:
                    if isinstance(period_end, str):
                        period_end = datetime.fromisoformat(period_end)
                    if period_end.tzinfo is None:
                        period_end = period_end.replace(tzinfo=timezone.utc)
                    is_active = period_end >= datetime.now(timezone.utc)
                else:
                    is_active = True
    out = UserOut(
        user_id=user["user_id"],
        email=user["email"],
        name=user.get("name", ""),
        picture=user.get("picture"),
        is_subscribed=is_active,
        subscription_status=status,
        plan_type=plan_type if is_active else None,
    )
    return out


# ----------------------------------------------------------------------------
# Health
# ----------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    return {"ok": True, "service": "sss-backend"}


# ----------------------------------------------------------------------------
# Auth endpoints
# ----------------------------------------------------------------------------
@app.post("/api/auth/session")
async def exchange_session(payload: SessionExchangeRequest):
    """Exchange Emergent session_id (from URL fragment) for a long-lived session_token."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(
                EMERGENT_AUTH_DATA_URL,
                headers={"X-Session-ID": payload.session_id},
            )
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Auth provider error: {e}")

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired session_id")

    data = resp.json()
    email = data.get("email")
    name = data.get("name") or ""
    picture = data.get("picture")
    session_token = data.get("session_token")
    if not email or not session_token:
        raise HTTPException(status_code=502, detail="Auth provider returned invalid payload")

    # Upsert user by email
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"name": name, "picture": picture, "updated_at": datetime.now(timezone.utc)}},
        )
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one(
            {
                "user_id": user_id,
                "email": email,
                "name": name,
                "picture": picture,
                "created_at": datetime.now(timezone.utc),
            }
        )

    # Store the session token (7-day expiry)
    await db.user_sessions.insert_one(
        {
            "user_id": user_id,
            "session_token": session_token,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
            "created_at": datetime.now(timezone.utc),
        }
    )

    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    user_out = await _user_to_out(user)
    return {"session_token": session_token, "user": user_out.model_dump()}


@app.get("/api/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    out = await _user_to_out(user)
    return out.model_dump()


@app.post("/api/auth/logout")
async def logout(authorization: Optional[str] = Header(default=None)):
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        await db.user_sessions.delete_one({"session_token": token})
    return {"ok": True}


# ----------------------------------------------------------------------------
# Subscription endpoints
# ----------------------------------------------------------------------------
@app.post("/api/subscription/checkout")
async def create_checkout(
    payload: CheckoutCreateRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Create a Stripe Checkout session.

    plan_type = "monthly" → $1.99 charged, grants 30 days access
    plan_type = "lifetime" → $20 charged, grants permanent access
    """
    plan_type = (payload.plan_type or "monthly").lower()
    if plan_type not in PLAN_PRICES:
        raise HTTPException(status_code=400, detail="Invalid plan_type")
    amount = PLAN_PRICES[plan_type]

    host_url = str(request.base_url)
    webhook_url = f"{host_url.rstrip('/')}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    origin = payload.origin_url.rstrip("/")
    success_url = f"{origin}/?stripe_session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/?stripe_cancelled=1"

    metadata = {
        "user_id": user["user_id"],
        "email": user["email"],
        "product": f"sss_pro_{plan_type}",
        "plan_type": plan_type,
    }

    checkout_request = CheckoutSessionRequest(
        amount=amount,
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
    )
    session = await stripe_checkout.create_checkout_session(checkout_request)

    await db.payment_transactions.insert_one(
        {
            "user_id": user["user_id"],
            "email": user["email"],
            "session_id": session.session_id,
            "amount": amount,
            "currency": "usd",
            "plan_type": plan_type,
            "metadata": metadata,
            "payment_status": "initiated",
            "status": "open",
            "created_at": datetime.now(timezone.utc),
        }
    )

    return {"url": session.url, "session_id": session.session_id}


@app.get("/api/subscription/status/{checkout_session_id}")
async def subscription_status(
    checkout_session_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Poll Stripe to refresh the status of a checkout session and activate subscription idempotently."""
    host_url = str(request.base_url)
    webhook_url = f"{host_url.rstrip('/')}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    status_resp = await stripe_checkout.get_checkout_status(checkout_session_id)

    tx = await db.payment_transactions.find_one(
        {"session_id": checkout_session_id}, {"_id": 0}
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Unknown checkout session")

    # Update the transaction (idempotent activation)
    already_paid = tx.get("payment_status") == "paid"
    await db.payment_transactions.update_one(
        {"session_id": checkout_session_id},
        {
            "$set": {
                "payment_status": status_resp.payment_status,
                "status": status_resp.status,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    if (
        not already_paid
        and status_resp.payment_status == "paid"
        and tx.get("user_id") == user["user_id"]
    ):
        plan_type = tx.get("plan_type") or "monthly"
        await _activate_subscription(user["user_id"], checkout_session_id, plan_type)

    return {
        "payment_status": status_resp.payment_status,
        "status": status_resp.status,
        "amount_total": status_resp.amount_total,
        "currency": status_resp.currency,
    }


async def _activate_subscription(user_id: str, session_id: str, plan_type: str = "monthly"):
    now = datetime.now(timezone.utc)
    update = {
        "user_id": user_id,
        "status": "active",
        "plan_type": plan_type,
        "current_period_start": now,
        "last_session_id": session_id,
        "updated_at": now,
    }
    if plan_type == "lifetime":
        update["current_period_end"] = None  # lifetime never expires
    else:
        update["current_period_end"] = now + timedelta(days=30)
    await db.subscriptions.update_one(
        {"user_id": user_id},
        {"$set": update},
        upsert=True,
    )


@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request):
    host_url = str(request.base_url)
    webhook_url = f"{host_url.rstrip('/')}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    body = await request.body()
    sig = request.headers.get("Stripe-Signature", "")

    try:
        event = await stripe_checkout.handle_webhook(body, sig)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {e}")

    session_id = getattr(event, "session_id", None)
    payment_status = getattr(event, "payment_status", None)
    metadata = getattr(event, "metadata", None) or {}

    if session_id:
        tx = await db.payment_transactions.find_one(
            {"session_id": session_id}, {"_id": 0}
        )
        already_paid = bool(tx and tx.get("payment_status") == "paid")
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "payment_status": payment_status,
                    "webhook_event_type": getattr(event, "event_type", None),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        user_id = metadata.get("user_id") if isinstance(metadata, dict) else None
        plan_type = (metadata.get("plan_type") if isinstance(metadata, dict) else None) or (tx.get("plan_type") if tx else None) or "monthly"
        if not user_id and tx:
            user_id = tx.get("user_id")
        if (not already_paid) and payment_status == "paid" and user_id:
            await _activate_subscription(user_id, session_id, plan_type)

    return {"received": True}


# ----------------------------------------------------------------------------
# Pricing info (public)
# ----------------------------------------------------------------------------
@app.get("/api/subscription/plan")
async def get_plan():
    features = [
        "Unlock NRFI Model with ML predictions",
        "Unlock NBA Daily Insights",
        "Unlock Slump Detector",
        "Daily refreshed data (GitHub Actions overnight)",
        "Full access to every current & future Pro tool",
    ]
    return {
        "name": SUBSCRIPTION_NAME,
        "plans": [
            {
                "id": "monthly",
                "label": "Monthly",
                "price_usd": MONTHLY_PRICE_USD,
                "interval": "month",
                "tagline": "Cancel anytime",
            },
            {
                "id": "lifetime",
                "label": "Lifetime",
                "price_usd": LIFETIME_PRICE_USD,
                "interval": "one-time",
                "tagline": "Pay once · never billed again",
            },
        ],
        "features": features,
    }
