import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

def app():
    st.set_page_config(page_title="Reverse Run Your Pool", page_icon="", layout="wide")

    st.title("Reverse Run Your Pool")

    # URL to scrape
    url = "https://www.baseball-reference.com/leagues/majors/2025-schedule.shtml"

    # Send a GET request to the URL
    response = requests.get(url)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the HTML content of the page
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all <p> elements with class 'game'
        game_paragraphs = soup.find_all('p', class_='game')

        # Extract the desired information
        games_data = []
        for game in game_paragraphs:
            links = game.find_all('a')
            scores = re.findall('(?<=\()\d*(?=\))', game.text)
            for i in range(len(scores)):
                scores[i] = int(scores[i])
            
            game_info = {
                'links_text': [link.text.strip() for link in links],
                'scores': [s for s in scores]
            }
            games_data.append(game_info)

        # Convert games_data into a DataFrame
        games_df = pd.DataFrame(games_data)

        # Add columns for the first and second values of links_text and scores
        games_df['link_1'] = games_df['links_text'].apply(lambda x: x[0] if len(x) > 0 else None)
        games_df['link_2'] = games_df['links_text'].apply(lambda x: x[1] if len(x) > 1 else None)
        games_df['score_1'] = games_df['scores'].apply(lambda x: x[0] if len(x) > 0 else None)
        games_df['score_2'] = games_df['scores'].apply(lambda x: x[1] if len(x) > 1 else None)

        # Drop the original lists of links_text and scores
        games_df.drop(columns=['links_text', 'scores'], inplace=True)

        # Remove rows where score_1 is NaN
        games_df = games_df.dropna(subset=['score_1'])

        # Drop the first two rows -- Japan series
        games_df = games_df.iloc[2:].reset_index(drop=True)

        # Reshape the dataframe
        reshaped_df = pd.DataFrame({
            'Tm': games_df['link_1'].tolist() + games_df['link_2'].tolist(),
            'Runs Allowed': games_df['score_2'].tolist() + games_df['score_1'].tolist()
        })

        #save teams to a list
        mlbTeams = reshaped_df['Tm'].unique().tolist()

        #convert runs allowed to int
        reshaped_df['Runs Allowed'] = reshaped_df['Runs Allowed'].astype(int) 

        # Reset the index
        reshaped_df.reset_index(drop=True, inplace=True)

        #begin shape of df for R.RYP
        runs_given_up = reshaped_df.groupby(['Tm', 'Runs Allowed']).size().unstack(fill_value=0)

        #create column for games played
        #use -1 to keep stats for how many games a team played - need to consider when runs allowed >13
        runs_given_up['-1'] = runs_given_up.sum(axis=1) #GAMES PLAYED
        #convert columns to numbers (ints)
        runs_given_up.columns = runs_given_up.columns.astype(int)
        #keep only columns of 13 or less runs
        runs_given_up = runs_given_up.loc[:, runs_given_up.columns <= 13]
        #add column for matches
        runs_given_up['Matches'] = ((runs_given_up > 0).sum(axis=1))-1
        #change column name to specify games played
        runs_given_up = runs_given_up.rename({-1: 'Games'}, axis=1)

        # List of columns
        columns = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 'Matches', 'Games']

        # Initialize the DataFrame with zeros
        data = {col: [0] * len(mlbTeams) for col in columns}

        # Create the DataFrame and set the row names to mlb_teams
        ryp = pd.DataFrame(data, index=mlbTeams)

        #update runs given up using the standard RYP table format
        ryp.update(runs_given_up)

        #sort by matches
        ryp = ryp.sort_values(by='Matches', ascending=False)

        # Convert all values in the DataFrame to integers
        ryp = ryp.astype(int)

        # Display the DataFrame in Streamlit
        st.dataframe(ryp)

    else:
        st.write(f"Failed to retrieve the page. Status code: {response.status_code}")

    