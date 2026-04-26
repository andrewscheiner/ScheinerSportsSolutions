import pybaseball as pyb
from datetime import datetime

# 2025-26
# Pull all Statcast events for the date
todayx = datetime.today().strftime('%Y-%m-%d')
nrfi = pyb.statcast(start_dt='2026-03-25', end_dt=todayx)

#save to csv for faster loading
nrfi.to_csv(r'data/nrfi.csv', index_label='Tm')