"""Scheiner Sports Solutions — Streamlit entry point.

Auth-gated with per-tool subscription gating:
  * Free tools: NBA Betting Systems, Laddering Tool, Tango Tracker,
                NFL Power Rankings, MLB Reverse RYP
  * Pro tools : NRFI Model, NBA Daily Insights, Slump Detector
"""
import os
import sys
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth_gate import (
    ensure_authenticated,
    handle_stripe_return_if_needed,
    require_subscription,
    render_account_sidebar,
    _inject_global_css,
    _render_paywall,
    get_current_token,
)

st.set_page_config(
    page_title="Scheiner Sports Solutions",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 1. Auth gate (always required)
user = ensure_authenticated()

# 2. Handle return-from-Stripe (no whole-app subscription gate)
handle_stripe_return_if_needed()

# 3. Render dashboard
_inject_global_css()
render_account_sidebar(user)

# Lazy imports for tool modules
import tools.BettingSystems as betting_systems
import tools.NFLPowerRankings as nfl
import tools.PitcherProps as pitcher
import tools.TangoTracker as tango
import tools.LadderingTool as ladder
import tools.SlumpDetector as slump
import tools.ReverseRunYourPool as reverse_pool
import tools.NBADaily as nba_daily
import tools.NRFIModel as nrfi

# ----- Tool registry -----
# label, page_id, render_fn, icon, requires_pro, group
TOOLS = [
    # Betting Systems
    {"label": "NRFI Report",         "page": "nrfi",            "fn": nrfi.app,           "icon": "💸", "pro": True,  "group": "betting"},
    {"label": "NBA Daily Insights",  "page": "nba_daily",       "fn": nba_daily.app,      "icon": "🏀", "pro": True,  "group": "betting"},
    {"label": "NBA Betting Systems", "page": "betting_systems", "fn": betting_systems.app,"icon": "🏀", "pro": False, "group": "betting"},
    {"label": "Laddering Tool",      "page": "ladder",          "fn": ladder.app,         "icon": "🪜", "pro": False, "group": "betting"},
    # Seasonal Tools
    {"label": "Tango Tracker",       "page": "tango",           "fn": tango.app,          "icon": "🔍", "pro": False, "group": "seasonal"},
    {"label": "NFL Power Rankings",  "page": "nfl",             "fn": nfl.app,            "icon": "🏈", "pro": False, "group": "seasonal"},
    {"label": "Slump Detector",      "page": "slump",           "fn": slump.app,          "icon": "🧊", "pro": True,  "group": "seasonal"},
    {"label": "MLB Reverse RYP",     "page": "reverse_pool",    "fn": reverse_pool.app,   "icon": "🔄", "pro": False, "group": "seasonal"},
]
TOOLS_BY_PAGE = {t["page"]: t for t in TOOLS}

# Persistent page state
if "page" not in st.session_state:
    st.session_state.page = "home"


def _render_tool_button(tool):
    """Render a Streamlit button with a PRO badge appended when locked."""
    is_locked = tool["pro"] and not user.get("is_subscribed")
    label = f"{tool['icon']}  {tool['label']}"
    if tool["pro"]:
        label += "   🔒 PRO" if is_locked else "   ⭐ PRO"
    if st.button(label, key=f"nav_{tool['page']}", use_container_width=True):
        st.session_state.page = tool["page"]
        st.rerun()


def _render_dashboard_home():
    st.markdown(
        """
        <div class="sss-hero" data-testid="dashboard-hero">
          <span class="sss-pill">Pro Dashboard</span>
          <h1>Scheiner <span>Sports Solutions</span></h1>
          <p>Sports betting, fantasy sports, and game-theory tools — designed by Andrew Scheiner. Choose a tool below.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Upgrade strip for non-subscribers
    if not user.get("is_subscribed"):
        st.markdown(
            """
            <div class="sss-card" data-testid="upgrade-banner" style="border-color:#D4AF37;background:linear-gradient(135deg,#121C16 0%,#1a2a1f 100%);margin-bottom:1.2rem;">
              <h3>🔒 Pro tools locked</h3>
              <p>Unlock the <strong>NRFI Model</strong>, <strong>NBA Daily Insights</strong>, and <strong>Slump Detector</strong> for $1.99/mo — or $20 once for lifetime access.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        c1, c2, _ = st.columns([1, 1, 3])
        with c1:
            if st.button("⭐ Upgrade to Pro", key="home_upgrade_btn", use_container_width=True):
                st.session_state.page = "upgrade"
                st.rerun()

    # Betting Systems section
    st.markdown(
        "<h2 style='color:#D4AF37;text-transform:uppercase;letter-spacing:0.06em;font-size:1.1rem;margin-top:1.5rem;'>Betting Systems</h2>",
        unsafe_allow_html=True,
    )
    betting_tools = [t for t in TOOLS if t["group"] == "betting"]
    cols = st.columns(len(betting_tools))
    for col, tool in zip(cols, betting_tools):
        with col:
            _render_tool_button(tool)

    # Seasonal Tools section
    st.markdown(
        "<h2 style='color:#D4AF37;text-transform:uppercase;letter-spacing:0.06em;font-size:1.1rem;margin-top:1.5rem;'>Seasonal Tools</h2>",
        unsafe_allow_html=True,
    )
    seasonal_tools = [t for t in TOOLS if t["group"] == "seasonal"]
    cols2 = st.columns(len(seasonal_tools))
    for col, tool in zip(cols2, seasonal_tools):
        with col:
            _render_tool_button(tool)


def _render_tool_page(tool):
    if st.button("← Back to dashboard", key="back_home_btn"):
        st.session_state.page = "home"
        st.rerun()
    # Subscription gate (only for pro tools)
    if tool["pro"]:
        require_subscription(user, tool_label=tool["label"])
    try:
        tool["fn"]()
    except Exception as e:
        st.error(f"Sorry, this tool failed to load: {e}")


# ----- Router -----
page = st.session_state.get("page", "home")

if page == "upgrade":
    if st.button("← Back to dashboard", key="upgrade_back_btn"):
        st.session_state.page = "home"
        st.rerun()
    _render_paywall(user, get_current_token(), locked_tool=None)
elif page in TOOLS_BY_PAGE:
    _render_tool_page(TOOLS_BY_PAGE[page])
else:
    _render_dashboard_home()

# ----- Footer -----
st.markdown("---")
st.markdown(
    """
    <div style="color:#788478;font-size:0.85rem;line-height:1.6;" data-testid="footer">
      <p><strong>Data sources &amp; packages:</strong> ESPN, Fangraphs, pybaseball, nfl-data-py, MLB Stats API, Kaggle.</p>
      <p><strong>Disclaimer:</strong> I will not be displaying any lines <strong>posted by sportsbooks</strong>, and all predictions generated by my models are only recommendations. Please bet responsibly and only risk what you are willing to lose.</p>
      <p>© Andrew Scheiner 2026</p>
    </div>
    """,
    unsafe_allow_html=True,
)
