import pybaseball as pyb
from pybaseball import schedule_and_record
import pandas as pd

mlb_teams = [
    'ARI', 'ATL', 'BAL', 'BOS', 'CHC', 'CHW', 'CIN', 'CLE', 'COL', 'DET',
    'HOU', 'KCR', 'LAA', 'LAD', 'MIA', 'MIL', 'MIN', 'NYM', 'NYY', 'ATH',
    'PHI', 'PIT', 'SDP', 'SFG', 'SEA', 'STL', 'TBR', 'TEX', 'TOR', 'WSN'
]

# Fetch schedule and record data for all MLB teams
schedule_records = [schedule_and_record(2026, team) for team in mlb_teams]

# Concatenate all schedule records into a single DataFrame
master_schedule = pd.concat(schedule_records, ignore_index=True)

master_schedule.to_csv(r'data/2026_schedule.csv', index=False)