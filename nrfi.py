import pybaseball as pyb
from datetime import datetime

# 2025-26
# Pull all Statcast events for the date
todayx = datetime.today().strftime('%Y-%m-%d')
nrfi = pyb.statcast(start_dt='2026-03-25', end_dt=todayx)

#keep only the columns we need for the model
cols = ['home_team', 'away_team', 'inning', 'player_name', 'pitcher', 
        'home_score', 'away_score', 'game_pk']

# get first inning data with only specific columns
df1 = nrfi[nrfi['inning'] == 1]
df2 = df1[cols].reset_index(drop=True)

#save to csv for faster loading
df2.to_csv(r'data/nrfi.csv', index_label='Tm')