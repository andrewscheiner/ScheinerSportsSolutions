import pandas as pd
import streamlit as st
from datetime import datetime

def app():

    st.title("⚾ MLB Monthly Wins")
    st.markdown("Display current and future MLB monthly wins data for all 30 teams. Updated daily during the season.")

    def warn(msg: str):
        st.markdown(
            f"""
            <div style="
                padding: 18px 20px;
                background-color: #fff8e6;
                border-left: 6px solid #e6a700;
                border-radius: 6px;
                font-size: 1.05rem;
                margin-top: 15px;
                line-height: 1.4;
            ">
                <strong style="color:#b07d00;">⚠️ Warning</strong><br>
                {msg}
            </div>
            """,
            unsafe_allow_html=True
        )
    warn("The most recent data upload was 6/21. Please use caution when making betting decisions using the following results. Please check back soon for updated MLB results.")

    #load in data
    master_schedule = pd.read_csv(r'data/2026_schedule.csv').reset_index(drop=True)

    # Convert date to month for each game
    _months = []
    for i in range(master_schedule.shape[0]):
        _months.append(datetime.strptime(master_schedule['Date'].iloc[i].split(" (")[0], "%A, %b %d").strftime("%B"))
        #print(f"{master_schedule['Date'].iloc[i]}, {master_schedule['Tm'].iloc[i]}")
    master_schedule['Month'] = _months

    #result
    master_schedule_gp = master_schedule[master_schedule['W/L'].notna()]
    master_schedule_gp["Result"] = master_schedule_gp['R'] > master_schedule_gp['RA']
    master_schedule_gp.head(7)

    #WPCT
    total_games = master_schedule_gp['Result'].notna().sum()  # Count of games with a result
    wins = (master_schedule_gp['Result'] == True).sum()  # Count of wins
    win_percentage = wins / total_games if total_games > 0 else 0

    #current WPCT
    team_win_percentage = master_schedule_gp.groupby('Tm').apply(
        lambda group: (group['Result'].sum() / group['Result'].count()) if group['Result'].count() > 0 else 0
    ).reset_index(name='Win_Percentage')

    #Month SOS
    def get_month_SOS(month):
        month_schedule = master_schedule[master_schedule['Month'] == month].copy()

        opp_wpct_map = team_win_percentage.set_index('Tm')['Win_Percentage']
        month_schedule['Opp_WPCT'] = month_schedule['Opp'].map(opp_wpct_map)

        print(month_schedule[['Tm', 'Home_Away', 'Opp', 'W/L', 'R', 'RA', 'Opp_WPCT']].reset_index(drop=True))

        return (
            month_schedule.groupby('Tm', as_index=False)
            .agg(
                Games=('Opp_WPCT', 'count'),
                SOS=('Opp_WPCT', 'mean')
            )
            .assign(SOS=lambda df: df['SOS'].round(3))
            .sort_values(by='SOS', ascending=True)
        )

    def get_monthly_standings(month):
        # Filter the master schedule for the specified month
        month_schedule = master_schedule_gp[master_schedule_gp['Month'] == month]
        
        # Get each team's record for the month
        standings = month_schedule.groupby('Tm')['Result'].value_counts().unstack(fill_value=0).rename(columns={True: 'Win', False: 'Loss'})
        
        # Calculate games played
        standings['GP'] = standings['Win'] + standings['Loss']

        # Calculate win percentage
        standings['WPCT'] = standings['Win'] / standings['GP']
        standings['WPCT'] = standings['WPCT'].round(3)

        # Sort by Wins, then WPCT
        standings = standings[['Win', 'Loss', 'GP', 'WPCT']].sort_values(['Win', 'WPCT'], ascending=[False, False])

        # Ranking logic (includes ties)
        standings['Rank'] = None
        prev_win = prev_wpct = None
        rank = 1
        ties = 0
        for idx, row in standings.iterrows():
            if (row['Win'], row['WPCT']) == (prev_win, prev_wpct):
                standings.at[idx, 'Rank'] = f"T{rank}"
                ties += 1
            else:
                rank += ties
                standings.at[idx, 'Rank'] = str(rank)
                ties = 1
                prev_win, prev_wpct = row['Win'], row['WPCT']

        # Move Rank to first column
        standings = standings.reset_index()
        cols = ['Rank', 'Tm', 'Win', 'Loss', 'GP', 'WPCT']
        standings = standings[cols]
        standings = standings.rename(columns={'Tm': 'Team'})

        #set new rank as index
        standings.columns.name = None
        standings.index = standings['Rank']
        del standings['Rank']  # Remove the 'Rank' column from the DataFrame

        return standings
    
    #get monthly standings for the current month
    current_month = datetime.now().strftime("%B")
    st.write(f'{current_month} MLB Standings')
    st.dataframe(get_monthly_standings(current_month))

    #get next month's outlook
    now = datetime.now()
    year = now.year + (1 if now.month == 12 else 0)
    month = 1 if now.month == 12 else now.month + 1
    next_month = datetime(year, month, 1).strftime("%B")

    st.write(f'{next_month} MLB Outlook')
    st.dataframe(get_month_SOS(next_month).reset_index(drop=True))