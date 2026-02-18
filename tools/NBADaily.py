import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def app():
    st.title("🏀 NBA Daily Insights")
    st.markdown("**A scoreboard showing every NBA game for the daily and giving smart insights.**")

    st.markdown("Data: NBA Games from the current season")

    oddsData = pd.read_csv(r'data/nba_scores_2025_2026.csv')