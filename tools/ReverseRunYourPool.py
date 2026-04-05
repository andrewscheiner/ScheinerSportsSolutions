import streamlit as st
import pandas as pd
from datetime import datetime

def app():

    st.markdown("""
<style>

table {
    border-collapse: collapse;
    width: 100%;
    background-color: #ffffff;
    overflow: hidden;
    font-family: 'Inter', sans-serif;
}

/* Center ALL text */
table td, table th {
    text-align: center !important;
    vertical-align: middle !important;
}

/* Add border to EVERY cell */
table td, table th {
    border: 1px solid #000000 !important;
}

/* Header */
thead th {
    background-color: #006666 !important;
    color: #CAEBEB !important;
    font-size: 16px;
    font-weight: 900;
    padding: 14px 20px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 1px solid #004f4f !important;
}

/* Body cells */
tbody td {
    padding: 12px 20px;
    font-size: 14px;
    font-weight: 600;
    color: #1a1c1e;
}

/* Hover effect */
tbody tr:hover {
    background-color: #e8f5f5;
}

/* INDEX COLUMN — Streamlit uses .row_heading */
table th.row_heading, table td.row_heading {
    color: #006666 !important;
    font-weight: bold !important;
    background-color: #f0fafa !important;
}

/* Top-left blank corner cell */
table th.blank {
    background-color: #006666 !important;
    color: #f0fafa    !important;
}

/* Make table scrollable on mobile */
@media (max-width: 576px) {
    table {
        display: block;
        overflow-x: auto;
        white-space: nowrap;
    }
}

</style>
""", unsafe_allow_html=True)
    
    st.title("🔄 MLB Runs Given Up / Reverse Run Your Pool")
    st.markdown("Seasonal MLB tool that tracks how many runs each team has given up in games so far this season.")
    st.markdown("Used for **Reverse** Run Your Pool where the goal is to have your team give up each run total from 0-13 at least once over the course of the season. First team to give up each run total wins!")

    #load in previous data - get datetime of last run
    pre_data = pd.read_csv(r'data/runs_given_up.csv', index_col='Tm')
    #rename index column fron 'Tm' to 'Team'
    pre_data.index.name = 'Team'
    #convert matches column to int
    pre_data['Matches'] = pre_data['Matches'].astype(int)

    #sort by matches
    final_data = pre_data.sort_values(by="Matches", ascending=False)

    #highlight matches
    def highlight_win_pct(val):
        if val > 0:
            return "background-color: #2FC535"   # green
        
    #print final dataframe
    st.table(final_data.style.map(highlight_win_pct, subset=final_data.columns[0:14]))