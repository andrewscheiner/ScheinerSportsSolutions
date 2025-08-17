import streamlit as st
from scipy.stats import lognorm
import numpy as np

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

# Parameters for Log-Normal Distribution
stat_per_game = 10.2  # Average stat per game
mu = np.log(stat_per_game)  # Log of the mean
sigma = 0.5     # Standard deviation (can be tuned)
intervals = [stat_per_game-2] + [stat_per_game] + [12, 13, 15, 18, 20, 25]

# Example: Find P(X ≥ 12), P(X ≥ 15), P(X ≥ 20), P(X ≥ 25)
results = {k: prob_gte_k_lognorm(k, mu, sigma) for k in intervals}
print(f"Results: {results}")

wagers = get_wager_ladder(len(results)) 
print(f"Wagers: {wagers}, Sum: {sum(wagers)}")

winnings = calculate_winnings(results, wagers)
print(f"Winnings: {winnings}, Sum: {sum(winnings.values())}")