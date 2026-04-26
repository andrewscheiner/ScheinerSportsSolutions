import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup as bs
import regex as re

def app():

    st.title("💸 No Runs In The First Inning (NRFI) Model")
    st.markdown("Analytically predict if a run will score in the first inning of today's baseball games.")

    #load in data
    df = pd.read_csv(r'data/nrfi.csv')

    #keep only the columns we need for the model
    cols = ['home_team', 'away_team', 'inning', 'player_name', 'pitcher', 
            'home_score', 'away_score', 'game_pk']

    # get first inning data with only specific columns
    df1 = df[df['inning'] == 1]
    df2 = df1[cols].reset_index(drop=True)

    # get teams
    teams = ['BOS', 'CWS', 'CLE', 'COL', 'LAA', 'MIA', 'MIN', 'PIT', 'SF', 'TB',
        'TEX', 'WSH', 'AZ', 'ATH', 'NYY','CIN', 'DET', 'SD', 'PHI', 'CHC',
        'MIL', 'BAL', 'KC', 'HOU', 'ATL','SEA', 'LAD', 'STL', 'TOR', 'NYM']

    print(len(teams))

    teamsdf = pd.DataFrame(teams, columns=['Team'])
    teamsdf['Games'] = 0
    teamsdf['RunsScored'] = 0
    teamsdf['Team_RSPF'] = 0.0

    # get pitchers
    pitchers = df2[['player_name', 'pitcher']].drop_duplicates(keep='first').reset_index(drop=True)
    pitchers['Appearances'] = 0
    pitchers['RunsGivenUp'] = 0
    pitchers['Pitcher_RAPF'] = 0.0

    # Away pitchers
    away = (
        df1
        .groupby(["game_pk", "away_team"])["pitcher"]
        .first()
        .reset_index()
        .rename(columns={"pitcher": "AwayPitcherID"})
    )

    # Home pitchers
    home = (
        df1
        .groupby(["game_pk", "home_team"])["pitcher"]
        .last()
        .reset_index()
        .rename(columns={"pitcher": "HomePitcherID"})
    )

    # Merge into final table
    gamepitchers = (
        away.merge(home, on="game_pk", how="inner")
            .drop(columns=["away_team", "home_team"])
    )

    ## Game / NRFI info
    gameinfo = df2.groupby(["game_pk"]).max()
    gameinfo = gameinfo[['home_team', 'away_team','home_score', 'away_score']].reset_index()
    gameinfo = gameinfo.merge(gamepitchers, on="game_pk", how="inner")

    ########################################
    # Function to update database
    ########################################
    def update_database(dataset):
        
        # Update teams table
        for index, row in dataset.iterrows():
            home_team = row['home_team']
            away_team = row['away_team']
            home_score = row['home_score']
            away_score = row['away_score']
            
            # Update home team stats
            teamsdf.loc[teamsdf['Team'] == home_team, 'Games'] += 1
            teamsdf.loc[teamsdf['Team'] == home_team, 'RunsScored'] += home_score
            
            # Update away team stats
            teamsdf.loc[teamsdf['Team'] == away_team, 'Games'] += 1
            teamsdf.loc[teamsdf['Team'] == away_team, 'RunsScored'] += away_score

        # Update pitchers table
        for index, row in dataset.iterrows():
            home_pitcher = row['HomePitcherID']
            away_pitcher = row['AwayPitcherID']
            home_score = row['home_score']
            away_score = row['away_score']
            
            # Update home pitcher stats
            pitchers.loc[pitchers['pitcher'] == home_pitcher, 'Appearances'] += 1
            pitchers.loc[pitchers['pitcher'] == home_pitcher, 'RunsGivenUp'] += away_score
            
            # Update away pitcher stats
            pitchers.loc[pitchers['pitcher'] == away_pitcher, 'Appearances'] += 1
            pitchers.loc[pitchers['pitcher'] == away_pitcher, 'RunsGivenUp'] += home_score

        # update rpf calculations
        teamsdf['Team_RSPF'] = teamsdf['RunsScored'] / teamsdf['Games']
        pitchers['Pitcher_RAPF'] = pitchers['RunsGivenUp'] / pitchers['Appearances']

    # update database using nrfi info
    update_database(gameinfo)

    # pitcher name mapping
    pitchers['player_name'] = pitchers['player_name'].str.replace(
        r'^(.*),\s*(.*)$', r'\2 \1', regex=True
    )
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
    pitchers['player_name'] = pitchers['player_name'].replace(player_name_mapping, regex=True)

    ############################################
    # Today's games
    ############################################

    # mapping function to convert team names to initials
    def mapTeamInitials(col):
        teamInitialsMapping = {'Arizona Diamondbacks':'AZ',
        'Atlanta Braves':'ATL',
        'Baltimore Orioles':'BAL',
        'Boston Red Sox':'BOS',
        'Chicago Cubs':'CHC',
        'Chicago White Sox':'CWS',
        'Cincinnati Reds':'CIN',
        'Cleveland Guardians':'CLE',
        'Colorado Rockies':'COL',
        'Detroit Tigers':'DET',
        'Houston Astros':'HOU',
        'Kansas City Royals':'KC',
        'Los Angeles Angels':'LAA',
        'Los Angeles Dodgers':'LAD',
        'Miami Marlins':'MIA',
        'Milwaukee Brewers':'MIL',
        'Minnesota Twins':'MIN',
        'New York Mets':'NYM',
        'New York Yankees':'NYY',
        'Oakland Athletics':'ATH',
        'Athletics': 'ATH',
        'Philadelphia Phillies':'PHI',
        'Pittsburgh Pirates':'PIT',
        'San Diego Padres':'SD',
        'San Francisco Giants':'SF',
        'Seattle Mariners':'SEA',
        'St. Louis Cardinals':'STL',
        'Tampa Bay Rays':'TB',
        'Texas Rangers':'TEX',
        'Toronto Blue Jays':'TOR',
        'Washington Nationals':'WSH'}
        return col.map(teamInitialsMapping)

    #function to get matchups and pitchers for each game
    #def getProbStarters(awayPitcherDict, homePitcherDict, teamCodeDict):
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

    # call function to get today's starters
    todayStarters = getProbStarters()

    # merge all data together
    home_pitchers = pitchers.rename(columns={
        'player_name': 'HomePitcher',
        'Appearances': 'Home_Appearances',
        'RunsGivenUp': 'Home_RunsGivenUp',
        'Pitcher_RAPF': 'Home_Pitcher_RAPF'
    })[['HomePitcher', 'Home_Appearances', 'Home_RunsGivenUp', 'Home_Pitcher_RAPF']]

    away_pitchers = pitchers.rename(columns={
        'player_name': 'AwayPitcher',
        'Appearances': 'Away_Appearances',
        'RunsGivenUp': 'Away_RunsGivenUp',
        'Pitcher_RAPF': 'Away_Pitcher_RAPF'
    })[['AwayPitcher', 'Away_Appearances', 'Away_RunsGivenUp', 'Away_Pitcher_RAPF']]

    home_teams = teamsdf.rename(columns={
        'Team': 'HomeTeam',
        'Games': 'Home_Games',
        'RunsScored': 'Home_RunsScored',
        'Team_RSPF': 'Home_Team_RSPF'
    })

    away_teams = teamsdf.rename(columns={
        'Team': 'AwayTeam',
        'Games': 'Away_Games',
        'RunsScored': 'Away_RunsScored',
        'Team_RSPF': 'Away_Team_RSPF'
    })

    todayStarters_expanded = (
        todayStarters
        .merge(home_pitchers, on='HomePitcher', how='left')
        .merge(away_pitchers, on='AwayPitcher', how='left')
        .merge(home_teams, on='HomeTeam', how='left')
        .merge(away_teams, on='AwayTeam', how='left')
    )

    probStarters = todayStarters_expanded[[ \
        'HomeTeam', 'AwayTeam', 'HomePitcher', 'AwayPitcher', \
        'Home_Pitcher_RAPF', 'Away_Pitcher_RAPF', 'Home_Team_RSPF', 'Away_Team_RSPF']]


    #### NRFI price
    def calcPrice(x):
        if x <= 0:
            return("YRFI")
        #nrfi chance > 0.5
        elif x > 0.5:
            price = int(round(((x/(1-x))*100)*-1,0))
            return(price)
        #nrfi chance < 0.5, but not 0
        elif x < 0.5 and x > 0:
            price = int(round((((1-x)/x)*100),0))
            return("+"+str(price))
        else:
            return("+100")
        
    def getNRFIPrice(nrfiTable, appendPrice_):

        #if I decide I do not want to append the NRFI price, skip function
        if appendPrice_ == False:
            return nrfiTable
        
        else:
            #get expected runs in the first inning based off of the 4 factors:
            ##away pitcher RAPF, home pitcher RAPF, away team RPF, home team RPF averaged
            ###subtract 1 to get expected prob for no runs
            expectedNRFIProb = []
            for game in range(nrfiTable.shape[0]):
                expectedNRFIProb.append(1 - ((nrfiTable.iloc[game,4] + nrfiTable.iloc[game,5] + \
                                            nrfiTable.iloc[game,6] + nrfiTable.iloc[game,7])/4))
            print(f"expectedNRFIProb: {expectedNRFIProb}")

            #convert each NRFI prob into american odds (think moneyline value)
            nrfiPrice = []
            for x in expectedNRFIProb:
                nrfiPrice.append(calcPrice(x))
            #print(nrfiPrice)
            #add YRFI price to table as well
            # yrfiPrice = []
            # for y in expectedNRFIProb:
            #     yrfiPrice.append(calcPrice(1-y))

            #append prices to final prediction output
            nrfiTable["NRFIPrice"] = nrfiPrice
            #nrfiTable["YRFIPrice"] = yrfiPrice
            return nrfiTable
        

    #add probability of NRFI and moneyline price (to compare to market value)
    ##second arg: False=no price, True=get price
    probStarters = getNRFIPrice(probStarters, appendPrice_=True)
    st.dataframe(probStarters)