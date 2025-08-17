#################################################################################
### Imports
#################################################################################
import streamlit as st

import requests
import json
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup as bs
import regex as re
import numpy

st.title("📈 NRFI Model")
st.markdown("Predict No-Run First Inning outcomes using dynamic probability modeling.")

#################################################################################
### Scrape prob starters
#################################################################################
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

#function to get matchups and pitchers for each game
def getProbStarters():
    #get site
    url = "https://baseballsavant.mlb.com/probable-pitchers"
    site = requests.get(url)
    #get html content of site
    content = bs(site.content)

    #matchups
    matchups = []
    _matchups = [i.text for i in content.find_all('h2')]
    for m in _matchups:
        matchups.append(re.findall('(.*)\s@', m)[0])
        matchups.append(re.findall('@\s(.*)', m)[0])

    ##fix "finding pitchers algorithm" by including a combined regex statement
    regex1 = r"<h3>(To be announced.)</h3>" #find any TBD spots
    regex2 = r"<a class=\"matchup-link\".*>(.*)<" #find all pitcher names
    combined_regex = "|".join([regex1, regex2])
    #pitchers
    players = []
    _players = re.findall(combined_regex, str(content)) #find all players or TBD in website
    for i in _players:
        if i[0] == 'To be announced.':
            players.append("TBD")
        elif (i[1] != 'To be announced.') and (i[1] != ''):
            players.append(i[1])

    #make a list of lists for away/home pitcher info
    matchupInfo = []
    for m0 in range(0,len(matchups),2):
        #print(m0)
        #home pitcher, away pitcher, hometeam, awayteam
        matchupInfo.append([players[m0+1],players[m0],  matchups[m0+1], matchups[m0]])
    
    #convert matchups into a pandas dataframe (to align with nrfi program)
    matchupDF = pd.DataFrame(matchupInfo, columns=["HomePitcher", "AwayPitcher", "HomeTeam", "AwayTeam"])
    matchupDF["AwayTeam"] = mapTeamInitials(matchupDF["AwayTeam"])
    matchupDF["HomeTeam"] = mapTeamInitials(matchupDF["HomeTeam"])

    ##Remove accents from names
    player_name_mapping = {'á': 'a',
           'é': 'e',
           'É': 'e',
           'í': 'i',
           'ó': 'o',
           'ú': 'u',
           'ñ': 'n',
           'ö': 'o',
           'ü': 'u',
           'č': 'c',
           'ć': 'c'
           }
    matchupDF["AwayPitcher"]=matchupDF["AwayPitcher"].replace(player_name_mapping, regex=True)
    matchupDF["HomePitcher"]=matchupDF["HomePitcher"].replace(player_name_mapping, regex=True)

    return matchupDF

#################################################################################
### API
#################################################################################
today = datetime.today().strftime('%Y-%m-%d')
url = "http://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&startDate=2025-03-01&endDate="+str(today)
headers = {"accept": "application/json"}
response = requests.get(url, headers=headers).text
# Load the JSON data into a Python dictionary
json_object = json.loads(response)

gameInfo = []
#for each day
for g in json_object['dates']:
    #for each game in the day
    for h in g['games']:
        #if regular season game (exclude spring)
        if h['gameType'] == 'R':
            #append game type, date, awayteam, hometeam
            gameInfo.append([
                h['gameType'],
                h['officialDate'],
                h['teams']['away']['team']['name'],
                h['teams']['home']['team']['name']
            ])
games = pd.DataFrame(gameInfo, columns=["Type", "Date", "Away", "Home"])

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
games['Away'] = games['Away'].map(teamInitialsMapping)
games['Home'] = games['Home'].map(teamInitialsMapping)

homeGames = games.copy()
homeGames = homeGames.rename(columns={"Away":"Opponent"})
homeGames['ID'] = homeGames['Date']+"-"+homeGames['Home']
homeGames['GameID'] = homeGames['Date']+"-"+homeGames['Opponent']+"-"+homeGames['Home']

awayGames = games.copy()
awayGames = awayGames.rename(columns={"Home":"Opponent"})
awayGames['ID'] = awayGames['Date']+"-"+awayGames['Away']
awayGames['GameID'] = awayGames['Date']+"-"+awayGames['Away']+"-"+awayGames['Opponent']

gamesFinal = pd.concat([homeGames, awayGames],axis=0)
gamesFinal.to_csv("gamesFinal.csv")

#################################################################################
### NRFI
#################################################################################









