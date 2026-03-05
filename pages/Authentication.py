import streamlit as st
import auth
import db
from auth import create_login_url, fetch_and_verify_token
from db import upsert_user

st.set_page_config(page_title="Authentication")

if "user" not in st.session_state:
    st.session_state["user"] = None

query_params = st.query_params

# If Google redirected to /auth/callback, Google appended ?code=...&state=...
if "code" in query_params and st.session_state.get("user") is None:
    # Reconstruct the exact URL Google called:
    base = st.secrets["REDIRECT_URI"]  # e.g., "http://localhost:8501/"
    qs = st.experimental_get_query_string()  # returns "code=...&state=..."
    full_url = base + ("?" + qs if qs else "")
    idinfo = fetch_and_verify_token(full_url)

    google_id = idinfo["sub"]
    email = idinfo.get("email")
    name = idinfo.get("name")

    upsert_user(google_id, email, name)
    st.session_state["user"] = {"google_id": google_id, "email": email, "name": name}
    st.experimental_rerun()

# Main UI
st.title("Authentication")

st.write("REDIRECT_URI used by app:", st.secrets.get("REDIRECT_URI"))

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
        st.experimental_rerun()