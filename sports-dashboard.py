##################################################
# Streamlit
##################################################
import streamlit as st
import pandas as pd
import altair as alt
##################################################

##################################################
# Daily Pitcher Props
##################################################
import pybaseball as pyb
import statsapi
from scipy.stats import rankdata
from datetime import datetime
import unicodedata
import os
import openpyxl
from openpyxl.utils.dataframe import dataframe_to_rows
##################################################

##################################################
# Setup webpage
##################################################
st.set_page_config(
    page_title="Andrew Scheiner's Sports Dashboard",
    page_icon=":trophy:",
    layout="wide",
    initial_sidebar_state="expanded")
#Title test
st.title('Scheiner Sports Solutions')
st.write('An interactive Streamlit dashboard containing multiple sports solutions \
         for fantasy and betting help. Designed by Andrew Scheiner.')
alt.themes.enable("dark")
##################################################

##################################################
# MLB Daily Pitcher Props
##################################################
def mapTeamInitials(col):
    teamInitialsMapping = {'Arizona Diamondbacks':'ARI',
    'Atlanta Braves':'ATL',
    'Baltimore Orioles':'BAL',
    'Boston Red Sox':'BOS',
    'Chicago Cubs':'CHC',
    'Chicago White Sox':'CHW',
    'Cincinnati Reds':'CIN',
    'Cleveland Guardians':'CLE',
    'Colorado Rockies':'COL',
    'Detroit Tigers':'DET',
    'Houston Astros':'HOU',
    'Kansas City Royals':'KCR',
    'Los Angeles Angels':'LAA',
    'Los Angeles Dodgers':'LAD',
    'Miami Marlins':'MIA',
    'Milwaukee Brewers':'MIL',
    'Minnesota Twins':'MIN',
    'New York Mets':'NYM',
    'New York Yankees':'NYY',
    'Oakland Athletics':'OAK',
    'Athletics': 'ATH',
    'Philadelphia Phillies':'PHI',
    'Pittsburgh Pirates':'PIT',
    'San Diego Padres':'SDP',
    'San Francisco Giants':'SFG',
    'Seattle Mariners':'SEA',
    'St. Louis Cardinals':'STL',
    'Tampa Bay Rays':'TBR',
    'Texas Rangers':'TEX',
    'Toronto Blue Jays':'TOR',
    'Washington Nationals':'WSN'}
    return col.map(teamInitialsMapping)
pitch = pyb.pitching_stats(2025, qual=10)
#get relevant columns
pitch = pitch[['Name', 'IP', 'G', 'TBF', 'BB%', 'K%', 'SwStr%', 'Swing%', 'Balls', 'Pitches', \
    'HR/9', 'HardHit%', 'FB%']]
#change IP to Outs/G (Outs / GS)
pitch['Out/G'] = (pitch['IP'] * 3) / pitch['G']
del pitch['G']
#change TBF to P/PA (Pitches / TBF)
pitch['P/PA'] = pitch['Pitches'] / pitch['TBF']
del pitch['TBF']
#change balls/pitches to Ball%
pitch['Ball%'] = pitch['Balls'] / pitch['Pitches']
del pitch['Balls']
del pitch['Pitches']
# Convert each numerical column in 'pitch' to percentile (0-100), whole numbers
pitch_percentile = pitch.copy()
num_cols = pitch.select_dtypes(include='number').columns
for col in num_cols:
    if col == 'IP' or col == 'HR/9' or col == 'HardHit%' or col == 'FB%':
        continue
    # Reverse percentile for 'BB%', 'Ball%', 'P/PA'
    if col in ['BB%', 'Ball%', 'P/PA']:
        pitch_percentile[col] = (1 - (rankdata(pitch[col], method='average') - 1) / (len(pitch[col]) - 1)) * 100
    else:
        pitch_percentile[col] = (rankdata(pitch[col], method='average') - 1) / (len(pitch[col]) - 1) * 100
    pitch_percentile[col] = pitch_percentile[col].round(0).astype(int)
tbat = pyb.team_batting(2025, qual=0)
#get relevant columns
tbat = tbat[['Team', 'BB%', 'K%', 'Swing%']]
tbat.rename(columns={'BB%': 'Team_BB%', \
                     'K%': 'Team_K%', \
                     'Swing%': 'Team_Swing%'}, inplace=True)
tbat_pctile = tbat.copy()
for col in ['Team_BB%', 'Team_K%', 'Team_Swing%']:
    tbat_pctile[col] = (rankdata(tbat_pctile[col], method='average') - 1) / (len(tbat_pctile[col]) - 1) * 100
    tbat_pctile[col] = tbat_pctile[col].round(0).astype(int)
today = datetime.today().strftime('%m/%d/%Y')
games = statsapi.schedule(start_date=today, end_date=today)
pitchers = []
for game in games:
    pitchers.append([game.get('home_probable_pitcher', {}), \
                     game.get('home_name', {}), \
                     game.get('away_name', {})])
    pitchers.append([game.get('away_probable_pitcher', {}), \
                     game.get('away_name', {}), \
                     game.get('home_name', {})])
pitchers_df = pd.DataFrame(pitchers, columns=['Pitcher', 'Team', 'Opponent'])
pitchers_df['Team'] = mapTeamInitials(pitchers_df['Team'])
pitchers_df['Opponent'] = mapTeamInitials(pitchers_df['Opponent'])
def remove_accents(input_str):
    if isinstance(input_str, str):
        nfkd_form = unicodedata.normalize('NFKD', input_str)
        return "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    return input_str
pitchers_df['Pitcher'] = pitchers_df['Pitcher'].apply(remove_accents)
daily_df = pd.merge(pitchers_df, pitch_percentile, left_on='Pitcher', right_on='Name', how='left')
del daily_df['Name']
daily_df_2 = pd.merge(daily_df, tbat_pctile, left_on='Opponent', right_on='Team', how='left')
del daily_df_2['Team_y']
daily_df_2.rename(columns={'Team_x': 'PitcherTeam'}, inplace=True)
#remove rows with NAN
daily_df_2 = daily_df_2.dropna()
#remove .0 from columns
for col in daily_df_2.select_dtypes(include='number').columns:
    if col == 'IP' or col == 'HR/9' or col == 'HardHit%' or col == 'FB%':
        continue
    daily_df_2[col] = daily_df_2[col].astype(int)
daily_df_2 = daily_df_2.reset_index(drop=True)

##################################################
# MLB Daily Walks
##################################################
daily_bb = daily_df_2[['Pitcher', 'Opponent', 'IP', 'BB%', 'Ball%', 'Team_BB%']]

daily_bb_over = daily_bb[(daily_bb['BB%'] <= 50) & (daily_bb['Ball%'] <= 75) & (daily_bb['Team_BB%'] >= 50)] \
    .sort_values(by=['BB%', 'Team_BB%'], ascending=[True, True]).reset_index(drop=True)
daily_bb_over['Bet'] = 'OVER'

daily_bb_under = daily_bb[(daily_bb['BB%'] > 50) & (daily_bb['Ball%'] > 75) & (daily_bb['Team_BB%'] < 50)] \
    .sort_values(by=['BB%', 'Team_BB%'], ascending=[True, True]).reset_index(drop=True)
daily_bb_under['Bet'] = 'UNDER'

#concat over and under
walks = pd.concat([daily_bb_over, daily_bb_under], ignore_index=True)
st.subheader('Daily Walks Guide')
st.dataframe(walks)
##################################################

##################################################
# MLB Daily Ks
##################################################
daily_k = daily_df_2[['Pitcher', 'Opponent', 'Out/G', 'K%', 'SwStr%', 'Team_K%']]

daily_k_over = daily_k[(daily_k['K%'] >= 50) & (daily_k['SwStr%'] >= 50) & (daily_k['Team_K%'] >= 50)] \
    .sort_values(by=['K%', 'SwStr%', 'Team_K%'], ascending=[False, False, False]).reset_index(drop=True)
daily_k_over['Bet'] = 'OVER'

daily_k_under = daily_k[(daily_k['K%'] < 50) & (daily_k['SwStr%'] < 50) & (daily_k['Team_K%'] < 50)] \
    .sort_values(by=['K%', 'SwStr%', 'Team_K%'], ascending=[False, False, False]).reset_index(drop=True)
daily_k_under['Bet'] = 'UNDER'

#concat over and under
strikeouts = pd.concat([daily_k_over, daily_k_under], ignore_index=True)
st.subheader('Daily Strikeouts Guide')
st.dataframe(strikeouts)
##################################################

##################################################
# MLB Daily Outs
##################################################
daily_out = daily_df_2[['Pitcher', 'Opponent', 'Out/G', 'P/PA','Team_Swing%']]

daily_out_over = daily_out[(daily_out['Out/G'] >= 75) & (daily_out['P/PA'] >= 50) & (daily_out['Team_Swing%'] >= 50)] \
    .sort_values(by=['Out/G', 'P/PA', 'Team_Swing%'], ascending=[False, False, False]).reset_index(drop=True)
daily_out_over['Bet'] = 'OVER'

daily_out_under = daily_out[(daily_out['Out/G'] <= 67) & (daily_out['P/PA'] < 50) & (daily_out['Team_Swing%'] < 50)] \
    .sort_values(by=['Out/G', 'P/PA', 'Team_Swing%'], ascending=[False, False, False]).reset_index(drop=True)
daily_out_under['Bet'] = 'UNDER'

#concat over and under
outs = pd.concat([daily_out_over, daily_out_under], ignore_index=True)
st.subheader('Daily Outs Guide')
st.dataframe(outs)
##################################################

##################################################
# MLB Daily Homeruns
##################################################
homeruns = daily_df_2[['Pitcher', 'Opponent', 'HR/9', 'HardHit%', 'FB%']] \
    .sort_values(by=['HR/9', 'HardHit%', 'FB%'], ascending=[False, False, False]).reset_index(drop=True)
##CONDITIONS
homer_per_nine_cond = homeruns['HR/9'] >= 1.8
hardhit_percent = homeruns['HardHit%'] >= 0.44
flyball_percent = homeruns['FB%'] >= 0.40

# Combine into a DataFrame of booleans
hr_conditions = pd.DataFrame([homer_per_nine_cond, hardhit_percent, flyball_percent]).T

# Filter rows where at least 2 conditions are True
filtered_hrs = pd.DataFrame(homeruns[hr_conditions.sum(axis=1) >= 2], columns=homeruns.columns)
st.subheader('Daily HR Targets')
st.dataframe(filtered_hrs)
##################################################

##################################################
# Full output
##################################################
st.subheader('Daily Walks (Full output)')
st.dataframe(daily_bb.sort_values(by=['BB%', 'Team_BB%'], ascending=[True, True]).reset_index(drop=True))
st.subheader('Daily Ks (Full output)')
st.dataframe(daily_k.sort_values(by=['K%', 'SwStr%', 'Team_K%'], ascending=[False, False, False]).reset_index(drop=True))
st.subheader('Daily Outs (Full output)')
st.dataframe(daily_out.sort_values(by=['Out/G', 'P/PA', 'Team_Swing%'], ascending=[False, False, False]))
##################################################

##################################################
# Tango CY Young Tracker
##################################################
season = int(datetime.now().year)
def get_pitching_leaders(lg):
    #get 2024 pitching stat leaders for given league
    cy_young = pyb.pitching_stats(season,season,league=lg)
    #calculate tango cy young points
    cy_young["Tango"] = ((cy_young["IP"]/2) - cy_young["ER"]) + \
                        (cy_young["SO"]/10) + cy_young["W"]
    #get top 5 tango pitchers
    cy_young = cy_young.sort_values('Tango', ascending=False).reset_index(drop=True).head(5)
    #rank index 1-5
    cy_young.index = cy_young.index + 1

    #return tango DF
    return cy_young[["Name", "Tango", "Team", "W", "L", "GS", "IP", "SO", "ERA", "FIP", "WAR",  \
                     "xERA", "xFIP", "LOB%", "CG", "ShO"]]
st.subheader('AL Tango CY Young Tracker')
st.dataframe(get_pitching_leaders("AL"))
st.subheader('NL Tango CY Young Tracker')
st.dataframe(get_pitching_leaders("NL"))
##################################################

st.write("© Andrew Scheiner 2025")