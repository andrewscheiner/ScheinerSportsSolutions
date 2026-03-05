import streamlit as st
import auth
import db
from auth import create_login_url, fetch_and_verify_token
from db import upsert_user
import streamlit.components.v1 as components
from urllib.parse import urlencode

st.set_page_config(page_title="Authentication")

# Ensure session keys exist
st.session_state.setdefault("user", None)
st.session_state.setdefault("oauth_state", None)
st.session_state.setdefault("auth_error", None)

# If Google redirected back with ?code=...&state=...
if "code" in st.query_params and st.session_state["user"] is None:
    base = st.secrets.get("REDIRECT_URI", "http://localhost:8501/auth/callback")
    # Build raw query string from st.query_params (values are lists)
    qs = urlencode(st.query_params, doseq=True)
    full_url = base + ("?" + qs if qs else "")
    st.info("Completing sign-in...")

    try:
        idinfo = fetch_and_verify_token(full_url)
        google_id = idinfo["sub"]
        email = idinfo.get("email")
        name = idinfo.get("name")
        # NOTE: picture removed per request

        upsert_user(google_id, email, name)
        st.session_state["user"] = {"google_id": google_id, "email": email, "name": name}

        # Remove query params from the browser URL without using experimental APIs
        # Replace the current history entry with the base path (no query string)
        safe_url = base  # exact redirect URI you registered (no query)
        js = f"window.history.replaceState(null, '', '{safe_url}');"
        components.html(f"<script>{js}</script>", height=0)

    except Exception as e:
        st.session_state["auth_error"] = f"Auth error: {e}"
        st.exception(e)


# Main UI
st.title("Authentication")

if st.session_state["user"] is None:
    st.write("You are not signed in.")
    login_url = create_login_url()
    st.markdown(f"[Sign in with Google]({login_url})")
    st.caption("If the page stays blank after redirect, check the terminal for errors.")
else:
    user = st.session_state["user"]
    st.write(f"Signed in as **{user['email']}**")
    st.write(f"Hi, {user['name']}!")
    if st.button("Log out"):
        st.session_state["user"] = None