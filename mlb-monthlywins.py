import pybaseball as pyb
from pybaseball import schedule_and_record
import pandas as pd
import requests
import time

pd.options.mode.copy_on_write = False
mlb_teams = [
    'ARI', 'ATL', 'BAL', 'BOS', 'CHC', 'CHW', 'CIN', 'CLE', 'COL', 'DET',
    'HOU', 'KCR', 'LAA', 'LAD', 'MIA', 'MIL', 'MIN', 'NYM', 'NYY', 'ATH',
    'PHI', 'PIT', 'SDP', 'SFG', 'SEA', 'STL', 'TBR', 'TEX', 'TOR', 'WSN'
]

pyb.request_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}
pyb.cache.enable()

def safe_schedule(year, team):
    for attempt in range(5):
        try:
            return pyb.schedule_and_record(year, team)
        except Exception as e:
            print(f"Retry {attempt+1} for {team}: {e}")
            time.sleep(2)
    return None

# Fetch schedule and record data for all MLB teams
schedule_records = []
for team in mlb_teams:
    # url = f"https://www.baseball-reference.com/teams/{team}/2026-schedule-scores.shtml"
    # resp = requests.get(url)
    # print(team, resp.status_code)
    # print(resp.text[:500])
    schedule_records.append(safe_schedule(2026, team))
    print(f"Fetched schedule and record for {team} in 2026")

# Concatenate all schedule records into a single DataFrame
master_schedule = pd.concat(schedule_records, ignore_index=True)

master_schedule.to_csv(r'data/2026_schedule.csv', index=False)