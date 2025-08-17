import streamlit as st

st.set_page_config(
    page_title="Andrew Scheiner's Sports Dashboard",
    page_icon=":trophy:",
    layout="wide",
    initial_sidebar_state="expanded")

st.set_page_config(page_title="Andrew Scheiner's Sports Dashboard", page_icon=":trophy:", layout="wide")

st.title('Scheiner Sports Solutions')
st.markdown('An interactive Streamlit dashboard containing multiple sports solutions \
         for fantasy and betting help. Designed by Andrew Scheiner.')

# Optional: Add quick links or highlights
st.subheader("Featured Tools")
st.markdown("- ⚾ **Pitcher Props**: Dive into pitcher performance metrics")
st.markdown("- 🔍 **Tango Tracker**: Track player movement and trends")
st.markdown("- 🪜 **Laddering Tool**: Construct strategic bet ladders for scalable returns")
st.markdown("- 📈 **NRFI Model**: Predict No-Run First Inning outcomes")
st.markdown("- 📅 **Monthly Wins Tool**: Monitor your betting success over time")
