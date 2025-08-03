#Packages
import streamlit as st
import pandas as pd
import altair as alt

#Set page config (only once, first command)
st.set_page_config(
    page_title="Andrew Scheiner's Sports Dashboard",
    page_icon=":trophy:",
    layout="wide",
    initial_sidebar_state="expanded")

#Title test
st.title('Scheiner Sports Solutions')
st.write('An interactive Streamlit dashboard containing multiple sports solutions \
         for fantasy and betting help. Designed by Andrew Scheiner.')

alt.themes.enable("dark")

st.write("© Andrew Scheiner 2025")