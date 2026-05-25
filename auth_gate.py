"""Authentication and subscription gating utilities for the Streamlit app.

This module is intentionally Streamlit-only (no React/JS framework). It uses:
  * `st.query_params` for session_token persistence across reloads
  * A tiny `st.components.v1.html` block to intercept the Emergent OAuth
    `#session_id=...` URL fragment and exchange it server-side.

REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
"""
import os
import time
from typing import Optional

import requests
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

# Backend URL (FastAPI). The same public URL serves both /api (port 8001) and /
# (port 3000 = streamlit) thanks to Kubernetes ingress.
_FRONTEND_ENV = "/app/frontend/.env"
if os.path.exists(_FRONTEND_ENV):
    load_dotenv(_FRONTEND_ENV)

BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API_BASE = f"{BACKEND_URL}/api" if BACKEND_URL else "/api"


# ---------------------------------------------------------------------------
# Low-level HTTP helpers
# ---------------------------------------------------------------------------
def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def fetch_me(token: str) -> Optional[dict]:
    try:
        r = requests.get(f"{API_BASE}/auth/me", headers=_auth_headers(token), timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None


def exchange_session_id(session_id: str) -> Optional[dict]:
    try:
        r = requests.post(
            f"{API_BASE}/auth/session",
            json={"session_id": session_id},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None


def create_stripe_checkout(token: str, origin_url: str) -> Optional[dict]:
    try:
        r = requests.post(
            f"{API_BASE}/subscription/checkout",
            headers=_auth_headers(token),
            json={"origin_url": origin_url},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None


def poll_stripe_status(token: str, stripe_session_id: str) -> Optional[dict]:
    try:
        r = requests.get(
            f"{API_BASE}/subscription/status/{stripe_session_id}",
            headers=_auth_headers(token),
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None


def fetch_plan() -> Optional[dict]:
    try:
        r = requests.get(f"{API_BASE}/subscription/plan", timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None


def logout(token: str):
    try:
        requests.post(f"{API_BASE}/auth/logout", headers=_auth_headers(token), timeout=5)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Streamlit-side helpers
# ---------------------------------------------------------------------------
def _process_session_id_fragment():
    """
    The Emergent OAuth flow redirects users to `{site}/#session_id=<id>`.
    Streamlit cannot read the URL fragment server-side, so we inject a tiny
    JS snippet that parses the fragment and bounces the page to
    `?session_token=<token>` after exchanging via the backend.
    """
    # REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    components.html(
        f"""
        <script>
        (async function() {{
          try {{
            const hash = window.parent.location.hash || '';
            if (!hash.includes('session_id=')) return;
            const params = new URLSearchParams(hash.replace(/^#/, ''));
            const sid = params.get('session_id');
            if (!sid) return;
            const resp = await fetch('{API_BASE}/auth/session', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json' }},
              body: JSON.stringify({{ session_id: sid }})
            }});
            if (!resp.ok) return;
            const data = await resp.json();
            const token = data.session_token;
            if (!token) return;
            try {{ window.parent.localStorage.setItem('sss_session_token', token); }} catch (e) {{}}
            const origin = window.parent.location.origin + window.parent.location.pathname;
            window.parent.location.replace(origin + '?session_token=' + encodeURIComponent(token));
          }} catch (e) {{ console.error('OAuth exchange failed', e); }}
        }})();
        </script>
        """,
        height=0,
    )


def _restore_token_from_storage():
    """If no session_token in the URL, attempt to restore one from localStorage."""
    components.html(
        """
        <script>
        (function() {
          try {
            const params = new URLSearchParams(window.parent.location.search);
            if (params.get('session_token')) return;
            const hash = window.parent.location.hash || '';
            if (hash.includes('session_id=')) return;  // handled by fragment processor
            const stored = window.parent.localStorage.getItem('sss_session_token');
            if (!stored) return;
            params.set('session_token', stored);
            const origin = window.parent.location.origin + window.parent.location.pathname;
            window.parent.location.replace(origin + '?' + params.toString());
          } catch (e) {}
        })();
        </script>
        """,
        height=0,
    )


def _clear_local_token():
    components.html(
        """
        <script>
        try { window.parent.localStorage.removeItem('sss_session_token'); } catch (e) {}
        </script>
        """,
        height=0,
    )


def get_query_params() -> dict:
    """Streamlit >=1.30 uses st.query_params (mapping-like)."""
    try:
        return dict(st.query_params)
    except Exception:
        return {}


def get_current_token() -> Optional[str]:
    params = get_query_params()
    tok = params.get("session_token")
    if isinstance(tok, list):
        tok = tok[0] if tok else None
    return tok


def get_origin_url() -> str:
    return BACKEND_URL or ""


# ---------------------------------------------------------------------------
# Public: ensure_authenticated() -> dict|None
# ---------------------------------------------------------------------------
def ensure_authenticated() -> Optional[dict]:
    """
    Renders the login screen when no valid session exists; returns the user dict
    when authenticated. Call this at the top of the main script.
    """
    # First-pass: try to consume any #session_id= fragment from Google OAuth.
    _process_session_id_fragment()

    token = get_current_token()
    user = fetch_me(token) if token else None

    if user:
        return user

    # No valid auth yet → try restoring previous token from localStorage.
    if not token:
        _restore_token_from_storage()

    _render_login_screen()
    st.stop()
    return None


# ---------------------------------------------------------------------------
# Public: ensure_subscribed(user)
# ---------------------------------------------------------------------------
def ensure_subscribed(user: dict):
    """
    If the user is not subscribed, render the paywall and stop the script.
    Also handles return-from-Stripe (?stripe_session_id=...).
    """
    token = get_current_token()

    # Handle return-from-stripe inline
    params = get_query_params()
    stripe_sid = params.get("stripe_session_id")
    if isinstance(stripe_sid, list):
        stripe_sid = stripe_sid[0] if stripe_sid else None

    if stripe_sid and token:
        _handle_stripe_return(token, stripe_sid)
        return  # _handle_stripe_return will rerun via st.rerun()

    if user.get("is_subscribed"):
        return

    _render_paywall(user, token)
    st.stop()


# ---------------------------------------------------------------------------
# Internal: UI renderers
# ---------------------------------------------------------------------------
def _inject_global_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');
        html, body, [class*="css"] { font-family: 'Manrope', sans-serif; }
        #MainMenu {visibility: hidden;} footer {visibility: hidden;}
        .stApp { background-color: var(--background-color); }
        .sss-hero {
          background: radial-gradient(circle at 20% 20%, rgba(212,175,55,0.18), transparent 50%),
                      radial-gradient(circle at 80% 80%, rgba(13,44,26,0.6), transparent 55%),
                      linear-gradient(135deg, #0A0F0C 0%, #0D2C1A 100%);
          padding: 3.5rem 2.5rem;
          border-radius: 18px;
          margin-bottom: 1.5rem;
          border: 1px solid rgba(212,175,55,0.25);
          color: #F8FAFC;
        }
        .sss-hero h1 {
          font-family: 'Manrope', sans-serif;
          font-weight: 800;
          letter-spacing: -0.02em;
          font-size: 2.6rem;
          margin: 0 0 0.6rem 0;
          text-transform: uppercase;
          color: #F8FAFC;
        }
        .sss-hero h1 span { color: #D4AF37; }
        .sss-hero p { font-size: 1.05rem; color: #d8e0d7; max-width: 720px; margin: 0; }
        .sss-card {
          background: #121C16;
          border: 1px solid rgba(212,175,55,0.18);
          border-radius: 14px;
          padding: 1.5rem 1.5rem;
          height: 100%;
        }
        .sss-card h3 {
          color: #D4AF37; margin: 0 0 0.4rem 0; font-weight: 700;
          letter-spacing: 0.04em; text-transform: uppercase; font-size: 1rem;
        }
        .sss-card p { color: #d8e0d7; margin: 0; font-size: 0.95rem; }
        .sss-pill {
          display: inline-block; padding: 4px 12px; border-radius: 999px;
          background: rgba(212,175,55,0.15); color: #D4AF37;
          font-weight: 600; font-size: 0.8rem; letter-spacing: 0.06em;
          text-transform: uppercase; margin-bottom: 0.8rem;
        }
        .sss-price {
          font-family: 'Manrope', sans-serif; font-weight: 800;
          font-size: 3.5rem; color: #D4AF37; line-height: 1;
        }
        .sss-price small { font-size: 1rem; color: #9ca99e; font-weight: 500; margin-left: 6px; }
        .sss-feature {
          padding: 8px 0; border-bottom: 1px solid rgba(212,175,55,0.1);
          color: #d8e0d7; font-size: 0.95rem;
        }
        .sss-feature:last-child { border-bottom: none; }
        .sss-feature::before {
          content: "✓ "; color: #D4AF37; font-weight: 800; margin-right: 6px;
        }
        .stButton > button {
          background-color: #D4AF37 !important;
          color: #0A0F0C !important;
          font-weight: 700 !important;
          border-radius: 10px !important;
          border: none !important;
          padding: 0.7rem 1.4rem !important;
          letter-spacing: 0.02em !important;
        }
        .stButton > button:hover { background-color: #FFD700 !important; }
        [data-testid="stSidebar"] { background: #0d1410; border-right: 1px solid #1E293B; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_login_screen():
    _inject_global_css()
    st.markdown(
        """
        <div class="sss-hero" data-testid="login-hero">
          <span class="sss-pill">Sports Analytics · Subscription</span>
          <h1>Scheiner <span>Sports Solutions</span></h1>
          <p>Daily NBA & MLB betting models, NRFI predictions, pitcher props, laddering tools, and seasonal trackers — engineered nightly from MLB Stats, Fangraphs, and ESPN.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1.2, 1])
    with col1:
        st.markdown(
            """
            <div class="sss-card" data-testid="login-features-card">
              <h3>What you get</h3>
              <div class="sss-feature">NBA betting systems &amp; daily insights</div>
              <div class="sss-feature">NRFI model with ML-backed predictions</div>
              <div class="sss-feature">MLB pitcher props &amp; CY Young Tango Tracker</div>
              <div class="sss-feature">Laddering tool, Slump detector, Reverse RYP</div>
              <div class="sss-feature">NFL weekly power rankings</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            """
            <div class="sss-card" data-testid="login-cta-card">
              <h3>Sign in to continue</h3>
              <p>Use your Google account — secure one-click sign-in.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # JS-driven login button (uses window.location.origin so the redirect
        # always matches the current host - never hardcoded).
        # REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
        components.html(
            """
            <div style="margin-top:14px;">
              <button id="sss-google-login"
                      data-testid="login-google-btn"
                      style="background:#D4AF37;color:#0A0F0C;border:none;border-radius:10px;
                             padding:14px 22px;font-weight:700;font-size:1rem;cursor:pointer;
                             width:100%;font-family:'Manrope',sans-serif;letter-spacing:0.02em;">
                Sign in with Google
              </button>
            </div>
            <script>
              document.getElementById('sss-google-login').addEventListener('click', function() {
                const redirectUrl = window.parent.location.origin + window.parent.location.pathname;
                window.parent.location.href =
                  'https://auth.emergentagent.com/?redirect=' + encodeURIComponent(redirectUrl);
              });
            </script>
            """,
            height=80,
        )

    st.markdown(
        "<p style='color:#788478;font-size:0.8rem;margin-top:1.5rem;'>"
        "By signing in you agree to bet responsibly. © Andrew Scheiner 2026"
        "</p>",
        unsafe_allow_html=True,
    )


def _render_paywall(user: dict, token: str):
    _inject_global_css()
    plan = fetch_plan() or {
        "name": "Pro",
        "price_usd": 9.99,
        "interval": "month",
        "features": [],
    }

    st.markdown(
        f"""
        <div class="sss-hero" data-testid="paywall-hero">
          <span class="sss-pill">Step 2 of 2 · Subscribe</span>
          <h1>Welcome, <span>{user.get('name','').split(' ')[0] or 'Bettor'}</span></h1>
          <p>One subscription unlocks every betting system, prop model, and seasonal tool. Cancel anytime from your dashboard.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1.2, 1])
    with col1:
        features_html = "".join(
            f'<div class="sss-feature">{f}</div>' for f in plan.get("features", [])
        )
        st.markdown(
            f"""
            <div class="sss-card" data-testid="paywall-features-card">
              <h3>What's included</h3>
              {features_html}
              <div class="sss-feature">Daily refreshed models (GitHub Actions overnight)</div>
              <div class="sss-feature">No ads · No sportsbook lines · No upsells</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
            <div class="sss-card" data-testid="paywall-pricing-card">
              <h3>{plan.get('name','Pro')}</h3>
              <div class="sss-price">${plan.get('price_usd', 9.99):.2f}<small>/{plan.get('interval','month')}</small></div>
              <p style="color:#9ca99e;margin-top:0.5rem;">Billed monthly. Secure checkout via Stripe.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Subscribe with Stripe", key="subscribe_btn", use_container_width=True):
            origin = get_origin_url()
            data = create_stripe_checkout(token, origin)
            if data and data.get("url"):
                # Navigate the parent window to Stripe Checkout
                components.html(
                    f"""
                    <script>
                      window.parent.location.href = "{data['url']}";
                    </script>
                    """,
                    height=0,
                )
                st.info("Redirecting to Stripe…")
                st.stop()
            else:
                st.error("Could not start checkout. Please try again.")

        if st.button("Sign out", key="logout_paywall_btn"):
            _do_logout(token)


def _handle_stripe_return(token: str, stripe_session_id: str):
    _inject_global_css()
    st.markdown(
        """
        <div class="sss-hero" data-testid="stripe-return-hero">
          <span class="sss-pill">Processing Payment</span>
          <h1>Confirming your <span>subscription…</span></h1>
          <p>Hang tight — we're verifying your payment with Stripe. This usually takes a few seconds.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    placeholder = st.empty()
    paid = False
    for attempt in range(8):
        status = poll_stripe_status(token, stripe_session_id)
        if not status:
            placeholder.warning(f"Checking payment status… (attempt {attempt+1})")
        else:
            ps = status.get("payment_status")
            if ps == "paid":
                paid = True
                break
            if status.get("status") == "expired":
                placeholder.error("Checkout session expired. Please try again.")
                break
            placeholder.info(f"Payment status: {ps} — re-checking…")
        time.sleep(1.5)

    # Clean the query string regardless of outcome
    try:
        st.query_params.clear()
        if token:
            st.query_params["session_token"] = token
    except Exception:
        pass

    if paid:
        placeholder.success("Payment confirmed! Loading your dashboard…")
        time.sleep(0.8)
        st.rerun()
    else:
        placeholder.error("Payment not confirmed. If you completed checkout, refresh in a few seconds.")
        if st.button("Back to dashboard"):
            st.rerun()
    st.stop()


def _do_logout(token: Optional[str]):
    if token:
        logout(token)
    _clear_local_token()
    try:
        st.query_params.clear()
    except Exception:
        pass
    components.html(
        """
        <script>
          const o = window.parent.location.origin + window.parent.location.pathname;
          window.parent.location.replace(o);
        </script>
        """,
        height=0,
    )
    st.stop()


# ---------------------------------------------------------------------------
# Sidebar account widget
# ---------------------------------------------------------------------------
def render_account_sidebar(user: dict):
    token = get_current_token()
    with st.sidebar:
        st.markdown(
            f"""
            <div style="padding:12px;border:1px solid rgba(212,175,55,0.2);border-radius:12px;background:#121C16;margin-bottom:12px;" data-testid="account-card">
              <div style="display:flex;align-items:center;gap:10px;">
                <img src="{user.get('picture') or 'https://via.placeholder.com/40'}" style="width:38px;height:38px;border-radius:50%;border:1px solid #D4AF37;">
                <div>
                  <div style="font-weight:700;color:#F8FAFC;font-size:0.95rem;">{user.get('name','User')}</div>
                  <div style="color:#9ca99e;font-size:0.78rem;">{user.get('email','')}</div>
                </div>
              </div>
              <div style="margin-top:8px;font-size:0.78rem;color:#D4AF37;font-weight:600;">
                {'PRO · ACTIVE' if user.get('is_subscribed') else 'FREE'}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Sign out", key="sidebar_logout_btn", use_container_width=True):
            _do_logout(token)
