import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

st.title("🏀 NBA Betting Systems")
st.markdown("**Is it smarter to bet the underdog to win outright or to cover?**")

st.markdown("Scope: NBA Games from the 2007 season through January 2023.")

oddsData = pd.read_csv(r'data/nbaBettingData.csv')
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
oddsData_final['Favorite Covered'] = oddsData_final.apply(favCover, axis=1)
oddsData_final['Favorite Won Outright'] = oddsData_final.apply(favOutright, axis=1)
oddsData_final['Underdog Covered'] = oddsData_final.apply(dogCover, axis=1)
oddsData_final['Underdog Outright'] = oddsData_final.apply(dogOutright, axis=1)
#total over?
oddsData_final['TotalOver'] = ((oddsData_final['HomeScore'] + oddsData_final['AwayScore']) > \
                                oddsData_final['PreFlopTotal'])*1
#get abs value spread
oddsData_final['PositiveSpread'] = oddsData_final["HomeSpread"].abs()

#graph title
title = ''
# Streamlit UI for spread filter
filter_option = st.radio(
    "Choose spread filter type:",
    ("Less than or equal to (<=)", "Equal to (==)", "Between (a <= x <= b)")
)

if filter_option == "Less than or equal to (<=)":
    spreadFilter = st.slider(
        'Show betting results where the spread is <= (less than or equal to):',
        min_value=0, max_value=20, value=4, step=1
    )
    if st.button('Update Results'):
        oddsData_plot = oddsData_final[oddsData_final['PositiveSpread'] <= spreadFilter]
    title = f'Betting and Game Results - Spreads of <= {spreadFilter}'

elif filter_option == "Equal to (==)":
    spreadFilter_eq = st.slider(
        'Show betting results where the spread is exactly:',
        min_value=0, max_value=20, value=4, step=1
    )
    if st.button('Update Results'):
        oddsData_plot = oddsData_final[oddsData_final['PositiveSpread'] == spreadFilter_eq]
    title = f'Betting and Game Results - Spreads of = {spreadFilter_eq}'

elif filter_option == "Between (a <= x <= b)":
    spread_min, spread_max = st.slider(
        'Show betting results where the spread is between:',
        min_value=0, max_value=20, value=(2, 6), step=1
    )
    if st.button('Update Results'):
        oddsData_plot = oddsData_final[
            (oddsData_final['PositiveSpread'] >= spread_min) &
            (oddsData_final['PositiveSpread'] <= spread_max)
        ]
    title = f'Betting and Game Results - Spreads between {spread_min} and {spread_max}'
       
try:
    bettingResult_vc = oddsData_plot[["Favorite Covered","Favorite Won Outright","Underdog Covered","Underdog Outright"]].value_counts()
    bettingResult_vc_df = pd.DataFrame(bettingResult_vc).reset_index()
except:
    st.warning("Please select a spread filter and click 'Update Results' to see the graph.")
    st.stop()

# Map each result row to a label based on the conditions
def get_label(row):
    vals = row[['Favorite Covered', 'Favorite Won Outright', 'Underdog Covered', 'Underdog Outright']].tolist()
    if vals == [1, 1, 0, 0]:
        return 'Favorite Covered'
    elif vals == [0, 0, 1, 1]:
        return 'Underdog Won'
    elif vals == [0, 1, 1, 0]:
        return 'Favorite Won, Dog Covered'
    elif vals == [-1, -1, -1, -1]:
        return 'Pick-Em'
    elif vals == [0, 1, 0, 0]:
        return 'Push'
    else:
        return str(vals)

new_labels = bettingResult_vc_df.apply(get_label, axis=1)

# Plot game results based on filtered spread
fig, ax = plt.subplots()
bettingResult_vc.plot(kind="bar", ax=ax)

# Calculate percentages
total = bettingResult_vc.sum()
percentages = (bettingResult_vc / total * 100).round(2)

# Add data labels and percentages on bars
for i, (count, pct) in enumerate(zip(bettingResult_vc, percentages)):
    ax.text(i, count + total * 0.01, f"{count}\n({pct}%)", ha='center', va='bottom', fontsize=10)

# X-axis
ax.set_xticks(range(len(new_labels)))
ax.set_xticklabels(new_labels, rotation=45)

# Labels
ax.set_xlabel('Betting Results')
ax.set_ylabel('Frequency')
ax.set_title(title, pad=30)  # Increased pad for more margin

st.pyplot(fig)
st.markdown(f"**Total games in selection:** {total} ({total / 18649 * 100:.2f}%)")

st.markdown("Data scope: 18,649 games over 15.5 NBA seasons (2007-Jan 2023)")
st.markdown("Data source: Kaggle")