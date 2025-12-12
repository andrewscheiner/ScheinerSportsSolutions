import streamlit as st
import pandas as pd

def app():
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
        xls = pd.ExcelFile("data/all_weeks_power_predictions.xlsx")
        weeks = sorted(xls.sheet_names, key=lambda x: int(x.split()[1]))
        week = st.selectbox("Select week:", weeks)
        df = pd.read_excel(xls, sheet_name=week)
        df.columns = columns
        st.dataframe(df)