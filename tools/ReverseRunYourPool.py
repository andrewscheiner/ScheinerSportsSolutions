import streamlit as st
import pandas as pd
import pybaseball
from pybaseball import schedule_and_record
from datetime import datetime, time

def app():
    
    st.title("🔄 MLB Runs Given Up / Reverse Run Your Pool")
    st.markdown("Seasonal MLB tool that tracks how many runs each team has given up in games so far this season.")
    st.markdown("Used for **Reverse** Run Your Pool where the goal is to have your team give up each run total from 0-13 at least once over the course of the season. First team to give up each run total wins!")

    #### Try caching R.RYP results - speed up results;
    #### If data has been loaded for the day, use cached data
    #### Else, use pybaseball to gather most recent data
    try:
        #load in previous data - get datetime of last run
        pre_data = pd.read_csv(r'data/runs_given_up.csv', index_col='Tm')
        # Parse your datetime from the string
        pre_data_datetime = datetime.strptime(
            pre_data['Last Updated'][0], '%Y-%m-%d %H:%M:%S'
        )
        # Build today's 03:00 AM reference
        today_3am = datetime.combine(datetime.today().date(), time(3, 0))

        # Compare- if data's datetime is earlier than today at 03:00 AM, need to re-run pybaseball
        if pre_data_datetime < today_3am:
            st.write(f"Last updated: {pre_data_datetime}")
            del pre_data['Last Updated']  #remove last updated column for display
            st.dataframe(pre_data)
        else:
            st.write("Pybaseball must be re-run.")
            raise Exception("BLANK")

    except:
        #run pybaseball to create initial data
        mlb_teams = [
            'ARI', 'ATL', 'BAL', 'BOS', 'CHC', 'CHW', 'CIN', 'CLE', 'COL', 'DET',
            'HOU', 'KCR', 'LAA', 'LAD', 'MIA', 'MIL', 'MIN', 'NYM', 'NYY', 'ATH',
            'PHI', 'PIT', 'SDP', 'SFG', 'SEA', 'STL', 'TBR', 'TEX', 'TOR', 'WSN'
        ]
        # Fetch schedule and record data for all MLB teams
        progress_bar = st.progress(0)   # progress bar
        status_text = st.empty()        # placeholder for text
        schedule_records = []
        for i, team in enumerate(mlb_teams):
            # Update progress bar
            progress = int((i + 1) / len(mlb_teams) * 100)
            progress_bar.progress(progress)
            # Update text
            status_text.text(f"Processing team {i+1}/{len(mlb_teams)}: {team}")
            # Get schedule and record for each team
            schedule_records.append(schedule_and_record(2025, team))

        # Concatenate all schedule records into a single DataFrame
        df = pd.concat(schedule_records, ignore_index=True)

        #only keep rows with data after Japan series
        df['Date'] = df['Date'].astype(str)
        df = df[~((df['Date']=='Tuesday, Mar 18') | (df['Date']=='Wednesday, Mar 19'))]

        #only keep rows with runs data
        df = df[df['R'].notnull()]

        # Add a column for runs given up (opponent's score)
        df['Runs Allowed'] = df['RA'].astype(int) 

        # Group by team and runs given up and count occurrences
        runs_given_up = df.groupby(['Tm', 'Runs Allowed']).size().unstack(fill_value=0)

        # #load in runs_given_up
        # runs_given_up = pd.read_csv('runs_given_up.csv', index_col='Tm')

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
        data = {col: [0] * len(mlb_teams) for col in columns}

        # Create the DataFrame and set the row names to mlb_teams
        ryp = pd.DataFrame(data, index=mlb_teams)

        #update runs given up using the standard RYP table format
        ryp.update(runs_given_up)

        #sort by matches
        ryp = ryp.sort_values(by='Matches', ascending=False)

        # Convert all values in the DataFrame to integers
        ryp = ryp.astype(int)

        # Add column for datetime
        ryp['Last Updated'] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        #save to csv for faster loading
        ryp.to_csv(r'data/runs_given_up.csv', index_label='Tm')

        #Hide progress, done
        progress_bar.empty()
        status_text.empty()
        st.success("All teams processed!")
        #Display dataframe
        st.write(f"Last updated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
        del ryp['Last Updated']  #remove last updated column for display
        st.dataframe(ryp)