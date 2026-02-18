import requests
import json
import datetime
from datetime import datetime, timedelta
import pandas as pd

# Generate list of dates from October 21, 2025 to today
start_date = datetime(2025, 10, 21)
end_date = datetime.now()

dates = []
current_date = start_date
while current_date <= end_date:
    dates.append(current_date.strftime("%Y%m%d"))
    current_date += timedelta(days=1)

#print(dates)

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

def get_nba_historical_scoreboard(date):
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

        #initialize a dataframe to store daily scoreboard info
        game_info = []

        #For each game, get game info
        for game in games:
            #Teams
            teams = game["competitions"][0]["competitors"]
            #Home
            home = teams[0]
            #Away
            away = teams[1]
            #Append data
            game_info.append(appendData(home) + appendData(away))

        return pd.DataFrame(game_info, columns=[
            'Home Team', 'Home Abbreviation', 'Home ID', 'Home Score',
            'Home Q1', 'Home Q2', 'Home Q3', 'Home Q4',
            'Away Team', 'Away Abbreviation', 'Away ID', 'Away Score',
            'Away Q1', 'Away Q2', 'Away Q3', 'Away Q4'
        ])

    except requests.RequestException as e:
        print(f"Error fetching data: {e}")

#curr_season_scores = get_nba_historical_scoreboard("20260108")
#curr_season_scores

curr_season_scores = pd.DataFrame()

for i in dates:
    print(f"Fetching data for date: {i}")
    curr_season_scores = pd.concat([curr_season_scores, get_nba_historical_scoreboard(i)], axis=0)
    print(f"Completed for date: {i}")
    print("-" * 40)

print("All data fetched.")
curr_season_scores.to_csv('data/nba_scores_2025_2026.csv', index=False)