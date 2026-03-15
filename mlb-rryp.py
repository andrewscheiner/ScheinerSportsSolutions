import requests
import json
import datetime
from datetime import datetime, timedelta
import pandas as pd

# Generate list of dates
start_date = datetime(2026, 3, 25)
end_date = datetime.today()

if start_date <= end_date:
    dates = []
    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date.strftime("%Y%m%d"))
        current_date += timedelta(days=1)
    print(dates)
else:
    raise ValueError("Start date must be before or equal to end date")

# Collect data for each team
def appendData(ht, at, date_x):
    date_y = datetime.strptime(date_x, "%Y%m%d").date()
    # Append team data with error handling for missing line scores
    try:
        return pd.DataFrame(
            [
                [
                    ht['team']['abbreviation'],
                    int(at['score']),
                    date_y
                ], 
                [
                    at['team']['abbreviation'],
                    int(ht['score']),
                    date_y
                ]
            ],
            columns=['Abbr', 'RGA', 'Date']
        )
    # If team is missing score for a postponed game, return blank dataframe
    except: return pd.DataFrame([[None,None,None],[None,None,None]])

# Function to get daily scoreboard data
def mlb_scoreboard(date):
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?dates={date}"

        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise error for bad status codes
        data = response.json()

        #Find games
        games = data.get("events", [])
        if not games:
            print("No games found.")

        #initialize a dataframe to store daily scoreboard info
        game_info = pd.DataFrame(
            columns=['Abbr', 'RGA', 'Date']
        )

        #For each game, get game info
        for game in games:
            #Teams
            teams = game["competitions"][0]["competitors"]
            #Home
            home = teams[0]
            #Away
            away = teams[1]
            #Get team names and scores
            #print(appendData(home, away))
            game_info = pd.concat([game_info, appendData(home, away, date)], axis=0).reset_index(drop=True)
        
        #Create dataframe
        return game_info
            
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")

# Fetch data for season
curr_season_scores = pd.DataFrame()
for i in dates:
    print(f"Fetching data for date: {i}")
    curr_season_scores = pd.concat([curr_season_scores, mlb_scoreboard(i)], axis=0)
    print(f"Completed for date: {i}")
    print("-" * 40)
print("All data fetched.")
curr_season_scores.to_csv('mlb_scores.csv', index=False)

# Get list of mlb teams
mlb_teams = (curr_season_scores['Abbr'].unique())
#['KC', 'MIN', 'BAL', 'TEX', 'MIA', 'CHW', 'CIN', 'PIT', 'PHI', 'WSH', \
#'TOR', 'COL', 'ATL', 'ATH', 'CHC', 'LAA', 'MIL', 'TB', 'STL', 'NYM', \
#'HOU', 'BOS', 'SEA', 'NYY', 'SD', 'SF', 'LAD', 'CLE', 'ARI', 'DET']
print(len(mlb_teams))

# Create a pivot table to count occurrences of each run total given up by each team
runs_given_up = curr_season_scores.groupby(['Abbr', 'RGA']).size().unstack(fill_value=0)

# List of columns
columns = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]

# Initialize the DataFrame with zeros
data = {col: [0] * len(mlb_teams) for col in columns}

# Create the DataFrame and set the row names to mlb_teams
ryp = pd.DataFrame(data, index=mlb_teams)

#update runs given up using the standard RYP table format
ryp.update(runs_given_up)

#delete AL and NL from ryp table
ryp = ryp.drop(['AL', 'NL'], axis=0, errors='ignore')

# Convert all values in the DataFrame to integers
ryp = ryp.astype(int)

#create column for games played
#use -1 to keep stats for how many games a team played - need to consider when runs allowed >13
ryp['-1'] = ryp.sum(axis=1) #GAMES PLAYED
#convert columns to numbers (ints)
ryp.columns = ryp.columns.astype(int)
#keep only columns of 13 or less runs
ryp = ryp.loc[:, ryp.columns <= 13]
#add column for matches
ryp['Matches'] = ((ryp > 0).sum(axis=1))-1
#change column name to specify games played
ryp = ryp.rename({-1: 'Games'}, axis=1)

#save to csv for faster loading
ryp.to_csv(r'data/runs_given_up.csv', index_label='Tm')