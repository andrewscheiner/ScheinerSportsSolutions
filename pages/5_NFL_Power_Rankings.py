import streamlit as st
import pandas as pd

st.markdown("**This page is still under development and only contains historical data while in the testing process.**")
st.title("🏈 NFL Power Rankings")
st.markdown("**Evaluating teams every week to determine betting edges.**")

st.markdown("Goal: Create a weekly updated NFL Power Rankings model that can identify betting edges against the spread.")
st.markdown("What is a power ranking? It is a way of assigning an overall number to a team based on players, injuries, and performance. Typically these create a ranking from best to last, but I will use it to put teams up against each other and find the estimated point spread.")
st.markdown("Scope: NFL Games from the 2023-24 season")

option = st.radio("View by:", ("Team", "Week"))

columns = [
    "Home Team", "Away Team", "Week", "Home Score", "Away Score", "Score Diff",
    "Away Spread", "Home ML", "Home PR", "Away PR", "Away Spread Prediction"
]

if option == "Team":
    xls = pd.ExcelFile("data/all_teams_power_predictions.xlsx")
    teams = sorted(xls.sheet_names)
    team = st.selectbox("Select a team:", teams)
    df = pd.read_excel(xls, sheet_name=team)
    df.columns = columns
    st.dataframe(df)
else:
    week = st.slider("Select week:", 1, 22, 1)
    df = pd.read_excel("data/all_weeks_power_predictions.xlsx")
    week_df = df[df['week'] == week]
    week_df.columns = columns
    st.dataframe(week_df)