import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

st.title("💰 Betting Systems")
st.markdown("Analyze historical betting systems to understand which trends occur most often.")

oddsData = pd.read_csv(r'data\\oddsData.csv')
#Sort
oddsData = oddsData.sort_values(['date', 'team'])
oddsData_final = oddsData[oddsData['home/visitor']=='vs']
#reset index
oddsData_final = oddsData_final.reset_index(drop=True)
#COLUMN CLEANUP
try: 
    del oddsData_final['home/visitor']
except:
    print('Already del')
oddsData_final = oddsData_final.rename(columns={'date':'Date', 'season':'Season', \
    'team':'Home', 'opponent':'Away', 'score':'HomeScore', 'opponentScore':'AwayScore', \
    'moneyLine':'HomeML', 'opponentMoneyLine':'AwayML', 'total':'PreFlopTotal', \
    'spread':'HomeSpread', 'secondHalfTotal':'SecondHalfTotal'})

################ Helper functions ####################
def favCover(row):
    #pfSpread_corrected ex: -1.0 turns to 1 bc a fav of -1 would need to win by more than 1
    pfSpread = row['HomeSpread']
    pfSpread_corrected = pfSpread*-1 

    #away team is fav
    if pfSpread > 0:
        if row['score_diff'] > pfSpread_corrected:
            return 0
        else:
            return 1
    #home team is fav
    elif pfSpread < 0:
        if row['score_diff'] > pfSpread_corrected:
            return 1
        else:
            return 0
    #pick em
    else:
        return -1
######################################################
def favOutright(row):
    #pfSpread_corrected ex: -1.0 turns to 1 bc a fav of -1 would need to win by more than 1
    pfSpread = row['HomeSpread']
    pfSpread_corrected = pfSpread*-1 

    #away team is fav
    if pfSpread > 0:
        if row['score_diff'] < 0:
            return 1
        else:
            return 0
    #home team is fav
    elif pfSpread < 0:
        if row['score_diff'] < 0:
            return 0
        else:
            return 1
    #pick em
    else:
        return -1
######################################################
def dogCover(row):
    #pfSpread_corrected ex: -1.0 turns to 1 bc a fav of -1 would need to win by more than 1
    pfSpread = row['HomeSpread']
    pfSpread_corrected = pfSpread*-1 

    #away team is dog
    if pfSpread < 0:
        if row['score_diff'] < pfSpread_corrected:
            return 1
        else:
            return 0
    #home team is dog
    elif pfSpread > 0:
        if row['score_diff'] > pfSpread_corrected:
            return 1
        else:
            return 0
    #pick em
    else:
        return -1
######################################################
def dogOutright(row):
    #pfSpread_corrected ex: -1.0 turns to 1 bc a fav of -1 would need to win by more than 1
    pfSpread = row['HomeSpread']
    pfSpread_corrected = pfSpread*-1 

    #away team is dog
    if pfSpread < 0:
        if row['score_diff'] < 0:
            return 1
        else:
            return 0
    #home team is dog
    elif pfSpread > 0:
        if row['score_diff'] > 0:
            return 1
        else:
            return 0
    #pick em
    else:
        return -1
######################################################
######################################################

#gather results
oddsData_final['score_diff'] = oddsData_final['HomeScore'] - oddsData_final['AwayScore']
oddsData_final['FavoriteCover'] = oddsData_final.apply(favCover, axis=1)
oddsData_final['FavoriteOutright'] = oddsData_final.apply(favOutright, axis=1)
oddsData_final['DogCover'] = oddsData_final.apply(dogCover, axis=1)
oddsData_final['DogOutright'] = oddsData_final.apply(dogOutright, axis=1)
#total over?
oddsData_final['TotalOver'] = ((oddsData_final['HomeScore'] + oddsData_final['AwayScore']) > \
                                oddsData_final['PreFlopTotal'])*1

# Streamlit UI for spread filter
spreadFilter = st.slider('Select maximum spread value:', min_value=0, max_value=20, value=4, step=1)
if st.button('Update Results'):
    # Convert negative spreads to a positive number
    oddsData_final['PositiveSpread'] = oddsData_final["HomeSpread"].abs()

    # Filter spreads based on user selection
    oddsData_plot = oddsData_final[oddsData_final['PositiveSpread'] <= spreadFilter]
    bettingResult_vc = oddsData_plot[["FavoriteCover","FavoriteOutright","DogCover","DogOutright"]].value_counts()

    # Plot game results based on filtered spread
    fig, ax = plt.subplots()
    bettingResult_vc.plot(kind="bar", ax=ax)
    # Customize x-axis labels
    new_labels = ['FavoriteCover', 'DogOutright', 'DogCover & FavML', 'Pick-Em', 'Push']
    ax.set_xticks(range(len(new_labels)))
    ax.set_xticklabels(new_labels, rotation=45)

    # Labels
    ax.set_xlabel('Game Results')
    ax.set_ylabel('Frequency')
    ax.set_title(f'Betting and Game Results - Spreads of <= {spreadFilter}')

    st.pyplot(fig)