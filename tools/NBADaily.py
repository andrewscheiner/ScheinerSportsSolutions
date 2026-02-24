import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import requests
import json
import datetime
from datetime import datetime, timedelta

def app():
    st.title("🏀 NBA Daily Insights")
    st.markdown("**A scoreboard showing every NBA game for the daily and giving smart insights.**")

    st.markdown("Data: NBA Games from the current season")

    df = pd.read_csv(r'data/nba_scores_2025_2026.csv')

    ##### Import appenddata fx
    def appendData(team, today=False):
        #If we are getting today's data, only get team names
        if today:
            try:
                return [
                    team['team']['displayName'],
                    team['team']['abbreviation'],
                    team['team']['id']            
                ]
            # If team is missing score for a postponed game, return blank dataframe
            except: return [None,None,None,None]

        #If we are getting historical data, get teams and scores since game has happened
        else:
            # Append team data with error handling for missing line scores
            try:
                return [
                    team['team']['displayName'],
                    team['team']['abbreviation'],
                    team['team']['id'],
                    int(team['score']),
                    team['linescores'][0]['value'],
                    team['linescores'][1]['value'],
                    team['linescores'][2]['value'],
                    team['linescores'][3]['value']
                ]
            # If team is missing score for a postponed game, return blank dataframe
            except: return [None,None,None,None,None,None,None,None]

    ### 1. Add core derived column
    # --- Half totals ---
    df["Home 1H"] = df["Home Q1"] + df["Home Q2"]
    df["Home 2H"] = df["Home Q3"] + df["Home Q4"]

    df["Away 1H"] = df["Away Q1"] + df["Away Q2"]
    df["Away 2H"] = df["Away Q3"] + df["Away Q4"]

    # --- Game totals ---
    df["Game Total"] = df["Home Score"] + df["Away Score"]

    # --- Half winners ---
    df["1H Winner"] = df.apply(
        lambda x: x["Home Team"] if x["Home 1H"] > x["Away 1H"] else x["Away Team"],
        axis=1
    )

    df["2H Winner"] = df.apply(
        lambda x: x["Home Team"] if x["Home 2H"] > x["Away 2H"] else x["Away Team"],
        axis=1
    )

    # --- Point differentials ---
    df["1H Diff"] = df["Home 1H"] - df["Away 1H"]
    df["2H Diff"] = df["Home 2H"] - df["Away 2H"]

    # --- Win/Loss ---
    df["Home Win"] = df["Home Score"] > df["Away Score"]
    df["Away Win"] = df["Away Score"] > df["Home Score"]

    df["Winner"] = df.apply(
        lambda x: x["Home Team"] if x["Home Win"] else x["Away Team"],
        axis=1
    )
    df["Loser"] = df.apply(
        lambda x: x["Away Team"] if x["Home Win"] else x["Home Team"],
        axis=1
    )

    ### 2. Home/Away records per team
    home_record = df.groupby("Home ID")["Home Win"].agg(["sum", "count"])
    home_record.rename(columns={"sum": "Home Wins", "count": "Home Games"}, inplace=True)
    home_record["Home Losses"] = home_record["Home Games"] - home_record["Home Wins"]
    del home_record["Home Games"]
    home_record['Home ID'] = home_record.index.astype(str)
    home_record.index.name = None

    away_record = df.groupby("Away ID")["Away Win"].agg(["sum", "count"])
    away_record.rename(columns={"sum": "Away Wins", "count": "Away Games"}, inplace=True)
    away_record["Away Losses"] = away_record["Away Games"] - away_record["Away Wins"]
    del away_record["Away Games"]
    away_record['Away ID'] = away_record.index.astype(str)
    away_record.index.name = None

    ### 3. Win/loss last 5 and last 10
    # Build long-form team-game table
    home_df = df[["Home ID", "Home Win"]].rename(columns={"Home ID": "Team", "Home Win": "Win"})
    away_df = df[["Away ID", "Away Win"]].rename(columns={"Away ID": "Team", "Away Win": "Win"})
    team_games = pd.concat([home_df, away_df], ignore_index=True)
    team_games["Last5"] = team_games.groupby("Team")["Win"].rolling(5).sum().reset_index(0, drop=True)
    team_games["Last10"] = team_games.groupby("Team")["Win"].rolling(10).sum().reset_index(0, drop=True)
    team_games_latest = team_games.groupby('Team').tail(1)
    team_games_latest['Team'] = team_games_latest['Team'].astype(str)
    # team_games_latest['Home ID'] = team_games_latest['Team']
    # team_games_latest['Away ID'] = team_games_latest['Team']
    del team_games_latest["Win"]

    ### 4. Home/away game totals, half totals, PPG
    #Home
    home_totals = df.groupby("Home ID")[["Home 1H", "Home 2H", "Home Score"]].mean().round(0) \
        .rename(columns={"Home Score": "Home PPG"})
    home_totals['Home ID'] = home_totals.index.astype(str)
    home_totals.index.name = None
    #Away
    away_totals = df.groupby("Away ID")[["Away 1H", "Away 2H", "Away Score"]].mean().round(0) \
        .rename(columns={"Away Score": "Away PPG"})
    away_totals['Away ID'] = away_totals.index.astype(str)
    away_totals.index.name = None
    
    ### 5. 1H/2H point differentials
    # HOME First half
    home_1h = df.groupby("Home ID")["1H Diff"].mean().round(0).rename("Home 1H Diff")
    home_1h = pd.DataFrame(home_1h)
    home_1h['Home ID'] = home_1h.index.astype(str)
    home_1h.index.name = None
    # AWAY First half
    away_1h = df.groupby("Away ID")["1H Diff"].apply(lambda x: -x.mean()).round(0) \
        .rename("Away 1H Diff")  # invert because diff is Home - Away
    away_1h = pd.DataFrame(away_1h)
    away_1h['Away ID'] = away_1h.index.astype(str)
    away_1h.index.name = None

    #first_half_diff = home_1h.add(away_1h, fill_value=0)

    # Second half
    # HOME
    home_2h = df.groupby("Home ID")["2H Diff"].mean().round(0).rename("Home 2H Diff")
    home_2h = pd.DataFrame(home_2h)
    home_2h['Home ID'] = home_2h.index.astype(str)
    home_2h.index.name = None
    # AWAY
    away_2h = df.groupby("Away ID")["2H Diff"].apply(lambda x: -x.mean()).round(0) \
            .rename("Away 2H Diff")
    away_2h = pd.DataFrame(away_2h)
    away_2h['Away ID'] = away_2h.index.astype(str)
    away_2h.index.name = None

    #second_half_diff = home_2h.add(away_2h, fill_value=0)

    #######################
    # Today's scores
    #######################
    #Merge all stats into today's games
    def fetch_team_stats(team_df, type):
        # 1. Home/Away Record
        if type == "Home":
            st.dataframe(team_df)
            st.dataframe(home_record)
            team_df = team_df.merge(home_record, on=f"{type} ID", how="left")
        else:
            team_df = team_df.merge(away_record, on=f"{type} ID", how="left")

        # 2. Rolling record
        st.dataframe(team_df)
        st.dataframe(team_games_latest)
        team_df = team_df.merge(team_games_latest, left_on=f"{type} ID", right_on="Team", how="left") \
            .rename(columns={"Last5": "Home Last5", "Last10": "Home Last10"})

        # 3. Game/half totals
        if type == "Home":
            st.dataframe(team_df)
            st.dataframe(home_totals)
            team_df = team_df.merge(home_totals, on=f"{type} ID", how="left")
        else:
            team_df = team_df.merge(away_totals, on=f"{type} ID", how="left")

        # 4. Half differentials
        if type == "Home":
            st.dataframe(team_df)
            st.dataframe(home_1h)
            team_df = team_df.merge(home_1h, on=f"{type} ID", how="left")
            team_df = team_df.merge(home_2h, on=f"{type} ID", how="left")
        else:
            team_df = team_df.merge(away_1h, on=f"{type} ID", how="left")
            team_df = team_df.merge(away_2h, on=f"{type} ID", how="left")

        return team_df

    #####################################
    ##### Get today's games
    #####################################
    def get_today_games(date):
        # Fetch NBA scoreboard data for a specific date
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date}"
        try:
            # Call requests
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # Raise error for bad status codes
            data = response.json()
            # Save JSON
            with open('nba_scoreboard.json', 'w') as f:
                json.dump(data, f, indent=2)

            #Find games
            games = data.get("events", [])
            if not games:
                print("No games found.")
                return

            #initialize dataframes to store daily scoreboard info
            home_teams_local = []
            away_teams_local = []
            #game_info = []

            #For each game, get game info
            #print(games[0]['competitions'][0]['competitors'][0]["team"]["displayName"])
            for game in games:
                #Teams
                teams = game["competitions"][0]["competitors"]
                #Home
                home = teams[0]
                home_teams_local.append(appendData(home, today=True))
                #Away
                away = teams[1]
                away_teams_local.append(appendData(away, today=True))

            #Get team stats for home team
            home_teams_local_df = pd.DataFrame(home_teams_local, columns=[
                'Home Team', 'Home Abbreviation', 'Home ID'
            ])
            home_teams_local_df['Home ID'] = home_teams_local_df['Home ID'].astype(str)
            home_stats = fetch_team_stats(home_teams_local_df, type="Home")

            #Get team stats for away team
            away_teams_local_df = pd.DataFrame(away_teams_local, columns=[
                'Away Team', 'Away Abbreviation', 'Away ID'
            ])
            away_teams_local_df['Away ID'] = away_teams_local_df['Away ID'].astype(str)
            away_stats = fetch_team_stats(away_teams_local_df, type="Away")

            #Append data
            return pd.concat([home_stats, away_stats], axis=1)

        except requests.RequestException as e:
            print(f"Error fetching data: {e}")

    ###########################
    # Get daily scoreboard
    ###########################
    #Get today's date YYYYMMDD
    today_date = datetime.now().strftime("%Y%m%d") #ex: 20260223
    scoreboard = get_today_games(today_date)

    # # DEBUG
    # scoreboard["Team"] = scoreboard["Team"].apply(
    #     lambda x: x.iloc[0] if isinstance(x, pd.Series) else x
    # )
    # st.write(scoreboard.dtypes)
    # for col in scoreboard.columns:
    #     types = scoreboard[col].apply(type).unique()
    #     st.write_stream(col, types)
    # st.dataframe(scoreboard)

    ###### Rolling conversions
    scoreboard["Home Last5"] = (scoreboard["Home Last5"]).astype(int)
    scoreboard["Home Last10"] = (scoreboard["Home Last10"]).astype(int)
    scoreboard["Away Last5"] = (scoreboard["Away Last5"]).astype(int)
    scoreboard["Away Last10"] = (scoreboard["Away Last10"]).astype(int)

    ###### Consolidate scoreboard
    scoreboard = scoreboard[['Home Team', 'Home Wins', 'Home Losses', 'Home PPG',
       'Home Last5', 'Home Last10', 'Home 1H', 'Home 2H', 'Home 1H Diff', 'Home 2H Diff', 
       'Away Team','Away Wins', 'Away Losses', 'Away PPG', 
       'Away Last5', 'Away Last10', 'Away 1H', 'Away 2H',  'Away 1H Diff', 'Away 2H Diff']]
    st.dataframe(scoreboard)

    #############################
    #### KEY INSIGHTS
    #############################
    #Betting odds function
    def pct_to_american(p):
        """
        Convert win probability (0–1) to American odds.
        Example: 0.20 -> +400
        """
        # Underdog
        if p < 0.5:
            return f"+{int((100 * (1 - p) / p))}"
        # Favorite
        return int((-100 * p / (1 - p)))
    
    # Generate key insights for a user
    # Each row is a game
    def generate_insights(game):

        # Print game
        print(f"********** {game['Away Team']} @ {game['Home Team']} **********")

        #Record
        home_win_pct = game["Home Wins"] / (game["Home Wins"] + game["Home Losses"])
        if home_win_pct >= 0.6:
            print(f"{game['Home Team']} have an implied home moneyline of {pct_to_american(home_win_pct)}")
        elif home_win_pct <= 0.35:
            print(f"{game['Home Team']} have an implied home moneyline of {pct_to_american(home_win_pct)}")


        # PPG
        if game['Home PPG'] - game['Away PPG'] >= 10:
            print(f"{game['Home Team']} have a significant scoring advantage of {game['Home PPG'] - game['Away PPG']} points.")
        elif game['Away PPG'] - game['Home PPG'] >= 10:
            print(f"{game['Away Team']} have a significant scoring advantage of {game['Away PPG'] - game['Home PPG']} points.")
        
        #### Last X games
        # 4+ / 5 = good
        # 7+ / 10 = good
        if game["Home Last10"] > 6:
            print(f"{game['Home Team']} have won {game['Home Last10']} of their last 10 games.")
        elif game["Home Last5"] > 3:
            print(f"{game['Home Team']} have won {game['Home Last5']} of their last 5 games.")
        if game["Away Last10"] > 6:
            print(f"{game['Away Team']} have won {game['Away Last10']} of their last 10 games.")
        elif game["Away Last5"] > 3:
            print(f"{game['Away Team']} have won {game['Away Last5']} of their last 5 games.")

        # 0 or 1 games / 5 = bad
        # 0-2 games / 10 = bad
        if game["Home Last10"] <= 2:
            print(f"{game['Home Team']} have won only {game['Home Last10']} of their last 10 games.")
        elif game["Home Last5"] <= 1:
            print(f"{game['Home Team']} have won only {game['Home Last5']} of their last 5 games.")
        if game["Away Last10"] <= 2:
            print(f"{game['Away Team']} have won only {game['Away Last10']} of their last 10 games.")
        elif game["Away Last5"] <= 1:
            print(f"{game['Away Team']} have won only {game['Away Last5']} of their last 5 games.")

        #Half Diffs
        if game["Home 1H Diff"] >= 5:
            print(f"{game['Home Team']} have a strong first half differential of {game['Home 1H Diff']} points.")
        elif game["Home 1H Diff"] <= -5:
            print(f"{game['Home Team']} have a weak first half differential of {game['Home 1H Diff']} points.")
        if game["Away 1H Diff"] >= 5:
            print(f"{game['Away Team']} have a strong first half differential of {game['Away 1H Diff']} points.")
        elif game["Away 1H Diff"] <= -5:
            print(f"{game['Away Team']} have a weak first half differential of {game['Away 1H Diff']} points.")
        if game["Home 2H Diff"] >= 5:
            print(f"{game['Home Team']} have a strong second half differential of {game['Home 2H Diff']} points.")
        elif game["Home 2H Diff"] <= -5:
            print(f"{game['Home Team']} have a weak second half differential of {game['Home 2H Diff']} points.")
        if game["Away 2H Diff"] >= 5:
            print(f"{game['Away Team']} have a strong second half differential of {game['Away 2H Diff']} points.")
        elif game["Away 2H Diff"] <= -5:
            print(f"{game['Away Team']} have a weak second half differential of {game['Away 2H Diff']} points.")
        
        #Half Totals
        if game["Home 1H"] - game["Away 1H"] >= 5:
            print(f"{game['Home Team']} have a strong first half scoring advantage of {game['Home 1H'] - game['Away 1H']} points.")
        elif game["Away 1H"] - game["Home 1H"] >= 5:
            print(f"{game['Away Team']} have a strong first half scoring advantage of {game['Away 1H'] - game['Home 1H']} points.")
        if game["Home 2H"] - game["Away 2H"] >= 5:
            print(f"{game['Home Team']} have a strong second half scoring advantage of {game['Home 2H'] - game['Away 2H']} points.")
        elif game["Away 2H"] - game["Home 2H"] >= 5:
            print(f"{game['Away Team']} have a strong second half scoring advantage of {game['Away 2H'] - game['Home 2H']} points.")

    #Print insight per game
    for index, game in scoreboard.iterrows():
        generate_insights(game)