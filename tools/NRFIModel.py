import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup as bs
import regex as re
import numpy as np

import sklearn.model_selection as model_selection
import sklearn.tree as tree
import sklearn.metrics as metrics

def app():

    st.markdown("""
    <style>

    table {
        border-collapse: collapse;
        width: 100%;
        background-color: #ffffff;
        overflow: hidden;
        font-family: 'Inter', sans-serif;
    }

    /* Center ALL text */
    table td, table th {
        text-align: center !important;
        vertical-align: middle !important;
    }

    /* Add border to EVERY cell */
    table td, table th {
        border: 1px solid #000000 !important;
    }

    /* Header */
    thead th {
        background-color: #006666 !important;
        color: #CAEBEB !important;
        font-size: 16px;
        font-weight: 900;
        padding: 14px 20px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: 1px solid #004f4f !important;
    }

    /* Body cells */
    tbody td {
        padding: 12px 20px;
        font-size: 14px;
        font-weight: 600;
        color: #1a1c1e;
    }

    /* Hover effect */
    tbody tr:hover {
        background-color: #e8f5f5;
    }

    /* INDEX COLUMN — Streamlit uses .row_heading */
    table th.row_heading, table td.row_heading {
        color: #006666 !important;
        font-weight: bold !important;
        background-color: #f0fafa !important;
    }

    /* Top-left blank corner cell */
    table th.blank {
        background-color: #006666 !important;
        color: #f0fafa    !important;
    }

    /* Make table scrollable on mobile */
    @media (max-width: 576px) {
        table {
            display: block;
            overflow-x: auto;
            white-space: nowrap;
        }
    }

    </style>
    """ , unsafe_allow_html=True)

    st.title("💸 No Runs In The First Inning (NRFI) Model")
    st.markdown("Analytically predict if a run will score in the first inning of today's baseball games.")

    #load in data
    df2 = pd.read_csv(r'data/nrfi.csv').reset_index(drop=True)

    # get teams
    teams = ['BOS', 'CWS', 'CLE', 'COL', 'LAA', 'MIA', 'MIN', 'PIT', 'SF', 'TB',
        'TEX', 'WSH', 'AZ', 'ATH', 'NYY','CIN', 'DET', 'SD', 'PHI', 'CHC',
        'MIL', 'BAL', 'KC', 'HOU', 'ATL','SEA', 'LAD', 'STL', 'TOR', 'NYM']

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
        df2
        .groupby(["game_pk", "away_team"])["pitcher"]
        .first()
        .reset_index()
        .rename(columns={"pitcher": "AwayPitcherID"})
    )

    # Home pitchers
    home = (
        df2
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

    #create columns for team/pitcher cumulative stats
    gameinfo['Home_Pitcher_RAPF'] = 0.0
    gameinfo['Away_Pitcher_RAPF'] = 0.0
    gameinfo['Home_Team_RSPF'] = 0.0
    gameinfo['Away_Team_RSPF'] = 0.0

    # add NRFI to game info
    gameinfo['NRFI'] = gameinfo['home_score'] + gameinfo['away_score'] <= 0

    ########################################
    # Function to update database
    ########################################
    def update_database_sequential(dataset, teamsdf, pitchers, sort_keys='game_pk'):
        """
        Sequentially update dataset with team/pitcher stats and update teamsdf/pitchers
        so each subsequent game sees the updated stats.

        Parameters
        - dataset: DataFrame of games (will not be modified in-place unless you want)
        - teamsdf: DataFrame with columns ['Team','Games','RunsScored', ...]
        - pitchers: DataFrame with columns ['pitcher','Appearances','RunsGivenUp', ...]
        - sort_keys: list of column names to sort dataset by (e.g., ['game_date','game_pk'])
        Returns
        - updated_dataset (copy), updated_teamsdf, updated_pitchers
        """

        # Work on copies to avoid surprising side effects
        df = dataset.copy().reset_index(drop=True)
        teams = teamsdf.set_index('Team').copy()
        p = pitchers.set_index('pitcher').copy()

        # Ensure numeric columns exist and fill missing with zeros
        for col in ['Games', 'RunsScored']:
            if col not in teams.columns:
                teams[col] = 0
        for col in ['Appearances', 'RunsGivenUp']:
            if col not in p.columns:
                p[col] = 0

        # Create fast lookup dicts
        team_games = teams['Games'].to_dict()
        team_runs = teams['RunsScored'].to_dict()
        pitcher_apps = p['Appearances'].to_dict()
        pitcher_runs = p['RunsGivenUp'].to_dict()

        # Optional sorting: ensure sequential order
        if sort_keys:
            df = df.sort_values(sort_keys, ascending=True).reset_index(drop=True)

        # Prepare output columns
        df['Home_Team_RSPF'] = np.nan
        df['Away_Team_RSPF'] = np.nan
        df['Home_Pitcher_RAPF'] = np.nan
        df['Away_Pitcher_RAPF'] = np.nan

        # Iterate sequentially
        for idx, row in df.iterrows():
            home_team = row['home_team']
            away_team = row['away_team']
            home_pitcher = row['HomePitcherID']
            away_pitcher = row['AwayPitcherID']
            home_score = row.get('home_score', 0)
            away_score = row.get('away_score', 0)

            # Get current team stats (defaults if missing)
            hg = team_games.get(home_team, 0)
            hr = team_runs.get(home_team, 0)
            ag = team_games.get(away_team, 0)
            ar = team_runs.get(away_team, 0)

            # Compute RSPF safely (avoid division by zero)
            home_rspf = hr / hg if hg > 0 else 0.0
            away_rspf = ar / ag if ag > 0 else 0.0

            # Get current pitcher stats (defaults if missing)
            hap = pitcher_apps.get(home_pitcher, 0)
            hrg = pitcher_runs.get(home_pitcher, 0)
            aap = pitcher_apps.get(away_pitcher, 0)
            arg = pitcher_runs.get(away_pitcher, 0)

            home_rapf = hrg / hap if hap > 0 else 0.0
            away_rapf = arg / aap if aap > 0 else 0.0

            # Write current stats into the dataset row
            df.at[idx, 'Home_Team_RSPF'] = home_rspf
            df.at[idx, 'Away_Team_RSPF'] = away_rspf
            df.at[idx, 'Home_Pitcher_RAPF'] = home_rapf
            df.at[idx, 'Away_Pitcher_RAPF'] = away_rapf

            # Now update team stats to include this game's results
            team_games[home_team] = hg + 1
            team_runs[home_team] = hr + home_score
            team_games[away_team] = ag + 1
            team_runs[away_team] = ar + away_score

            # Update pitcher stats (appearances and runs given up)
            pitcher_apps[home_pitcher] = hap + 1
            pitcher_runs[home_pitcher] = hrg + away_score
            pitcher_apps[away_pitcher] = aap + 1
            pitcher_runs[away_pitcher] = arg + home_score

        # After loop, recompute rates and write back to DataFrames if desired
        teams_updated = teams.copy()
        teams_updated['Games'] = teams_updated.index.map(lambda t: team_games.get(t, 0))
        teams_updated['RunsScored'] = teams_updated.index.map(lambda t: team_runs.get(t, 0))
        teams_updated['Team_RSPF'] = teams_updated.apply(
            lambda r: (r['RunsScored'] / r['Games']) if r['Games'] > 0 else 0.0, axis=1
        )

        pitchers_updated = p.copy()
        pitchers_updated['Appearances'] = pitchers_updated.index.map(lambda pid: pitcher_apps.get(pid, 0))
        pitchers_updated['RunsGivenUp'] = pitchers_updated.index.map(lambda pid: pitcher_runs.get(pid, 0))
        pitchers_updated['Pitcher_RAPF'] = pitchers_updated.apply(
            lambda r: (r['RunsGivenUp'] / r['Appearances']) if r['Appearances'] > 0 else 0.0, axis=1
        )

        return df, teams_updated.reset_index(), pitchers_updated.reset_index()

    # call function to update database sequentially
    updated_games, updated_teamsdf, updated_pitchers = update_database_sequential(
        dataset=gameinfo,
        teamsdf=teamsdf,
        pitchers=pitchers
    )

    updated_pitchers['player_name'] = updated_pitchers['player_name'].str.replace(
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
    updated_pitchers['player_name'] = updated_pitchers['player_name'].replace(player_name_mapping, regex=True)

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

    #Sortable NRFI Price
    def sortablePrice(x):
        if pd.isna(x) or x < 0 or x > 1 or x == 0 or x == 1:
            return np.nan
        #nrfi chance > 0.5
        elif x > 0.5:
            price = int(round(((x/(1-x))*100)*-1,0))
            return(price)
        #nrfi chance < 0.5, but not 0
        #### NO PLUS SIGN FOR SORTING PURPOSES
        elif x < 0.5 and x > 0:
            price = int(round((((1-x)/x)*100),0))
            return(price)
        elif x == 0.5:
            return(100)
        else:
            return np.nan

    # calculate NRFI probability as 1 - average of the 4 stats
    updated_games['NRFIProb'] = (1 - ((updated_games['Home_Pitcher_RAPF'] + \
                                  updated_games['Away_Pitcher_RAPF'] + \
                                    updated_games['Home_Team_RSPF'] + \
                                        updated_games['Away_Team_RSPF'])/4))
    updated_games['NRFIPrice'] = updated_games['NRFIProb'].apply(lambda x: sortablePrice(x))

    ### Analysis
    def is_correct(prob, nrfi):
        if pd.isna(prob) or pd.isna(nrfi) or prob < 0 or prob > 1:
            return np.nan
        if prob >= 0.5 and nrfi == True:
            return True
        elif prob < 0.5 and nrfi == False:
            return True
        elif prob >= 0.5 and nrfi == False:
            return False
        else:
            return False
    nrfi_backtest_analyze = updated_games[['game_pk', 'NRFI', 'NRFIProb']]
    nrfi_backtest_analyze = updated_games.loc[:, ['game_pk', 'NRFI', 'NRFIProb']].copy()
    nrfi_backtest_analyze.loc[:, 'Correct'] = nrfi_backtest_analyze.apply(
        lambda row: is_correct(row['NRFIProb'], row['NRFI']),
        axis=1
    )
    #correct_pct = nrfi_backtest_analyze['Correct'].dropna().mean() * 100
    #nrfi_backtest_analyze.value_counts('Correct')

    #### ML MODEL
    feature_cols = [
        'Home_Pitcher_RAPF',
        'Away_Pitcher_RAPF',
        'Home_Team_RSPF',
        'Away_Team_RSPF'
    ]
    X = updated_games[feature_cols]
    y = updated_games['NRFI'].astype(int)

    splitratios = [0.2, 0.3, 0.4]*3

    best_dt_classifier = []
    best_acc = [0]
    final_sr = 0
    final_X = None
    final_X_train_shape = None
    final_X_test_shape = None

    for sr in splitratios:
        X_train, X_test, y_train, y_test = model_selection.train_test_split(X, y, test_size=sr, random_state=42)
        # Decision Tree
        dt_classifier = tree.DecisionTreeClassifier()
        dt_classifier.fit(X_train, y_train)
        predictions = dt_classifier.predict(X_test)
        accuracy = metrics.accuracy_score(y_test, predictions)

        #get all stats for best DT model
        if accuracy > best_acc[-1]:
            #print("reached")
            best_dt_classifier.append(dt_classifier)
            best_acc.append(accuracy)
            final_sr = sr
            final_X = X
            final_X_train_shape = X_train.shape
            final_X_test_shape = X_test.shape
        #print(sr, accuracy)

    # Display Results
    #print(f"\nResults for Decision Tree (Split Ratio: {final_sr}):")
    #print(f"Best Accuracy: {best_acc[-1]:.3f}")

    # Find importance of variables
    impVals = list(best_dt_classifier[-1].feature_importances_)
    colNames = list(best_dt_classifier[-1].feature_names_in_)
    for i in range(final_X.shape[1]):
        print(colNames[i],":",impVals[i])

    #print(X_test)
    #print(dt_classifier.predict(X_test.iloc[0:1,]))

    #print shape of test and train
    #print("Training shape:",final_X_train_shape)
    #print("Testing shape:",final_X_test_shape)

    ### Implement ML into probable startes
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

    todayStarters = getProbStarters()
    
    ### Merge in stats
    home_pitchers = updated_pitchers.rename(columns={
        'player_name': 'HomePitcher',
        'Appearances': 'Home_Appearances',
        'RunsGivenUp': 'Home_RunsGivenUp',
        'Pitcher_RAPF': 'Home_Pitcher_RAPF'
    })[['HomePitcher', 'Home_Appearances', 'Home_RunsGivenUp', 'Home_Pitcher_RAPF']]

    away_pitchers = updated_pitchers.rename(columns={
        'player_name': 'AwayPitcher',
        'Appearances': 'Away_Appearances',
        'RunsGivenUp': 'Away_RunsGivenUp',
        'Pitcher_RAPF': 'Away_Pitcher_RAPF'
    })[['AwayPitcher', 'Away_Appearances', 'Away_RunsGivenUp', 'Away_Pitcher_RAPF']]

    home_teams = updated_teamsdf.rename(columns={
        'Team': 'HomeTeam',
        'Games': 'Home_Games',
        'RunsScored': 'Home_RunsScored',
        'Team_RSPF': 'Home_Team_RSPF'
    })

    away_teams = updated_teamsdf.rename(columns={
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

    #More price calculations
    def calcPrice(x):
        if pd.isna(x):
            return np.nan
        #nrfi chance > 0.5
        elif x > 0.5:
            price = int(round(((x/(1-x))*100)*-1,0))
            return(price)
        #nrfi chance < 0.5, but not 0
        elif x < 0.5 and x > 0:
            price = int(round((((1-x)/x)*100),0))
            return("+"+str(price))
        elif x == 0.5:
            return("+100")
        else:
            return np.nan

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
            print(nrfiPrice)
            #add YRFI price to table as well
            # yrfiPrice = []
            # for y in expectedNRFIProb:
            #     yrfiPrice.append(calcPrice(1-y))

            #SORT -- convert each NRFI prob into american odds (think moneyline value)
            nrfiPriceSort = []
            for x in expectedNRFIProb:
                nrfiPriceSort.append(sortablePrice(x))
            print(nrfiPriceSort)

            #append prices to final prediction output
            nrfiTable["NRFIPrice"] = nrfiPrice
            nrfiTable["Sort_Price"] = nrfiPriceSort
            #nrfiTable["YRFIPrice"] = yrfiPrice
            return nrfiTable
        
    #Get price for today's games
    probStarters = getNRFIPrice(probStarters, appendPrice_=True)

    #predict NRFI? for probable matchups
    #print(best_dt_classifier[-1].decision_path(probStarters[0:]))
    probStarters["SSS_ML_Prediction"] = best_dt_classifier[-1].predict(probStarters[['Home_Pitcher_RAPF',
        'Away_Pitcher_RAPF',
        'Home_Team_RSPF',
        'Away_Team_RSPF']])
    probStarters["SSS_ML_Prediction"] = probStarters["SSS_ML_Prediction"].apply(lambda x: "NRFI" if x == 1 else "YRFI")
    
    #Make a decision based off price and ML
    decisionmatrix = []
    for i in range(probStarters.shape[0]):
        if probStarters.iloc[i,-1] == "NRFI" and probStarters.iloc[i,-2] < 0:
            decisionmatrix.append("NRFI")
        elif probStarters.iloc[i,-1] == "YRFI" and probStarters.iloc[i,-2] > 0:
            decisionmatrix.append("YRFI")
        else:
            decisionmatrix.append("No Bet")
    probStarters["SSS_Decision"] = decisionmatrix

    # Style Table
    def color_rows(row):
            if row["SSS_Decision"] == "NRFI":
                return ["background-color: #006666"] * len(row)
            elif row["SSS_Decision"] == "YRFI":
                return ["background-color: #003dd6"] * len(row)
            elif row["SSS_Decision"] == "No Bet":
                return ["background-color: #454545"] * len(row)
            return [""] * len(row)

    st.table(probStarters.style.apply(color_rows, axis=1))