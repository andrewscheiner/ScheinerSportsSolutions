import streamlit as st
from scipy.stats import lognorm
import numpy as np
import pandas as pd

st.title("🪜 Laddering Tool")
st.markdown("Build and visualize progressive betting ladders to optimize risk and reward.")

def calculate_american_odds(probability):
    if probability > 0.5:  # Implies favorite
        odds = -(probability / (1 - probability)) * 100
    else:  # Implies underdog
        odds = ((1 - probability) / probability) * 100
    return int(round(odds,0))

# Complementary CDF (1 - CDF) for P(X ≥ k)
def prob_gte_k_lognorm(k, mu, sigma):
    return calculate_american_odds(1 - lognorm.cdf(k, sigma, scale=np.exp(mu)))

def calculate_winnings(odds_dict, wagers):
    winnings_dict = {}
    keys_ = list(odds_dict.keys())
    odds_ = list(odds_dict.values())
    for i in range(len(odds_dict)):
        key = keys_[i]
        odds = odds_[i]
        if odds > 0:
            winnings = wagers[i] * (odds / 100)
        else:
            winnings = wagers[i] * (100 / abs(odds))
        winnings_dict[key] = round(winnings, 2)
    return winnings_dict

def get_wager_ladder(num_bets, starting_bets=[10, 7.5, 5]):
    values = starting_bets.copy()
    while len(values) < num_bets:
        next_value = round(values[-1] * 0.75, 2)  # Adjust multiplier as needed
        if next_value < 0.1:
            next_value = 0.1
        values.append(next_value)
    return values

# Streamlit UI for Laddering Tool

st.header("Ladder Parameters")

# User inputs
stat_per_game = st.number_input("Average Stat per Game", min_value=0.1, value=10.2, step=0.1)
sigma = st.number_input("Log-Normal Std Dev (σ)", min_value=0.01, value=0.5, step=0.01)

# Intervals input
intervals = st.text_input(
    "Stat Intervals (comma-separated)", 
    value="8,10.2,12,13,15,18,20,25"
)
intervals = [float(x.strip()) for x in intervals.split(",") if x.strip()]

# Bet sizes input
default_bets = ", ".join([str(x) for x in get_wager_ladder(len(intervals))])
bet_sizes = st.text_input(
    "Bet Sizes for Each Interval (comma-separated)", 
    value=default_bets
)
wagers = [float(x.strip()) for x in bet_sizes.split(",") if x.strip()]
if len(wagers) != len(intervals):
    st.warning("Number of bet sizes must match number of intervals.")

# Calculate log-normal parameters
mu = np.log(stat_per_game)

# Calculate odds and winnings
results = {k: prob_gte_k_lognorm(k, mu, sigma) for k in intervals}
winnings = calculate_winnings(results, wagers) if len(wagers) == len(intervals) else {}

# Display results
st.subheader("Ladder Results")
df = pd.DataFrame({
    "Interval (Stat ≥)": intervals,
    "American Odds": [results[k] for k in intervals],
    "Bet Size": wagers if len(wagers) == len(intervals) else [""]*len(intervals),
    "Potential Winnings": [winnings.get(k, "") for k in intervals]
})
st.dataframe(df, use_container_width=True)

if len(wagers) == len(intervals):
    st.markdown(f"**Total Bet:** ${sum(wagers):.2f}")
    st.markdown(f"**Total Potential Winnings:** ${sum([w for w in winnings.values()]):.2f}")