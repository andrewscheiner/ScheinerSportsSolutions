import streamlit as st
import pandas as pd
from datetime import datetime

def app():
    
    st.title("🔄 MLB Runs Given Up / Reverse Run Your Pool")
    st.markdown("Seasonal MLB tool that tracks how many runs each team has given up in games so far this season.")
    st.markdown("Used for **Reverse** Run Your Pool where the goal is to have your team give up each run total from 0-13 at least once over the course of the season. First team to give up each run total wins!")

    #load in previous data - get datetime of last run
    pre_data = pd.read_csv(r'data/runs_given_up.csv', index_col='Tm')
    #st.dataframe(pre_data.sort_values(by="Matches", ascending=False))
    st.dataframe(pre_data)