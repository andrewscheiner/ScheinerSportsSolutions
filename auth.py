import streamlit as st
from authlib.integrations.requests_client import OAuth2Session
from google.oauth2 import id_token
from google.auth.transport import requests as grequests

def get_oauth_client():
    client_id = st.secrets["GOOGLE_CLIENT_ID"]
    client_secret = st.secrets["GOOGLE_CLIENT_SECRET"]
    redirect_uri = st.secrets["REDIRECT_URI"]
    return OAuth2Session(
        client_id,
        client_secret,
        scope="openid email profile",
        redirect_uri=redirect_uri,
    )

def create_login_url():
    oauth = get_oauth_client()
    auth_url, state = oauth.create_authorization_url(
        "https://accounts.google.com/o/oauth2/v2/auth"
    )
    st.session_state["oauth_state"] = state
    return auth_url

def fetch_and_verify_token(full_redirect_url: str):
    oauth = get_oauth_client()
    state = st.session_state.get("oauth_state")
    oauth.state = state
    token = oauth.fetch_token(
        "https://oauth2.googleapis.com/token",
        authorization_response=full_redirect_url,
    )
    idinfo = id_token.verify_oauth2_token(
        token["id_token"],
        grequests.Request(),
        st.secrets["GOOGLE_CLIENT_ID"],
    )
    return idinfo
