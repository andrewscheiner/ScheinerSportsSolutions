import pybaseball
from pybaseball import statcast_batter
import pandas as pd
import matplotlib.pyplot as plt
import math
import streamlit as st
import altair as alt

def app():
    st.title("🧊 Slump Detector")
    st.markdown("**Using SPRT, a statistical test to determine a player's true batting average.**")
    st.markdown("Use cases: fantasy baseball pickups, GM trade decisions, scouting reports for minor leaguers.")


    # Load player list
    players = pd.read_csv(r"data/mlbam_ids.csv")
    player_names = players['Name'].dropna().unique().tolist()

    # Search input and selection
    search_query = st.text_input("Search player (type part of the name)", "Aaron Judge")
    matches = [n for n in player_names if search_query.lower() in n.lower()]

    if not matches:
        st.warning("No matches found for your search. Showing top players.")
        matches = player_names[:200]  # limit to avoid huge lists

    selected_player = st.selectbox("Select player", matches, index=0)
    player_id = int(players.loc[players['Name'] == selected_player, 'MLBAMID'].values[0])

    st.write(f"Selected: {selected_player}")

    data = statcast_batter('2025-04-01', '2025-09-30', player_id)

    at_bats = data.groupby(['game_pk', 'at_bat_number']).head(1)

    # Map events to hit/out
    hit_events = {'single', 'double', 'triple', 'home_run'}
    out_events = {'field_out', 'strikeout', 'force_out', 'field_error', 'grounded_into_double_play', \
                'double_play', 'fielders_choice', 'strikeout_double_play'}

    #apply function to map events to at-bat results
    def event_to_ab(event):
        #if event is a hit, return 1
        if event in hit_events:
            return 1
        #if event is an out, return 0
        elif event in out_events:
            return 0
        #if event is not a hit or out, return None
        else:
            return None  # excludes walks, HBP, etc.
    at_bats['ab_result'] = at_bats['events'].apply(event_to_ab)

    # Drop non-at-bats, convert set of results to a list
    at_bats_results = at_bats.dropna(subset=['ab_result'])['ab_result'].tolist()

    #SPRT
    def sprt_batting_average(at_bats_x, p0, p1, alpha, beta):
        """
        Sequential Probability Ratio Test (SPRT) for batting average.
        
        Parameters:
            at_bats_x (list of int): Sequence of at-bats (1 = hit, 0 = out).
            p0 (float): Null hypothesis batting average.
            p1 (float): Alternative hypothesis batting average.
            alpha (float): Type I error rate.
            beta (float): Type II error rate.
        
        Returns:
            decision (str): 'Accept H0', 'Accept H1', or 'Continue'.
            llr (float): Final log-likelihood ratio.
            steps (list): LLR after each at-bat.
        """
        # Compute SPRT decision thresholds in probability space:
        threshold_accept_h1 = (1 - beta) / alpha   # A: odds threshold to accept H1
        threshold_accept_h0 = beta / (1 - alpha)   # B: odds threshold to accept H0

        # Convert thresholds to log space for comparison with the log-likelihood ratio (LLR)
        log_threshold_accept_h1 = math.log(threshold_accept_h1)
        log_threshold_accept_h0 = math.log(threshold_accept_h0)
        
        # Precompute the per-observation log-likelihood increments:
        # - If a plate appearance is a hit, add log(p1/p0)
        # - If it's an out, add log((1-p1)/(1-p0))
        log_inc_on_hit = math.log(p1 / p0)
        log_inc_on_out = math.log((1 - p1) / (1 - p0))
        
        # Initialize cumulative log-likelihood ratio and history of values
        cumulative_llr = 0.0
        llr_history = []
        
        # Process each at-bat sequentially and update the cumulative LLR
        for ab in at_bats_x:
            # Treat 1 as a hit; any other value (commonly 0) treated as an out
            if ab == 1:
                cumulative_llr += log_inc_on_hit
            else:
                cumulative_llr += log_inc_on_out

            # Record the LLR after this observation
            llr_history.append(cumulative_llr)
            
        # Check stopping rules:
        # - If LLR >= log_threshold_accept_h1, evidence favors H1 (p ≈ p1)
        # - If LLR <= log_threshold_accept_h0, evidence favors H0 (p ≈ p0)
        if cumulative_llr >= log_threshold_accept_h1: #and len(llr_history) >= 10000:
            return f"Accept H1 (≈. {p1} hitter)", cumulative_llr, llr_history
        elif cumulative_llr <= log_threshold_accept_h0:
            return f"Accept H0 (≈. {p0} hitter)", cumulative_llr, llr_history
        
        # If neither threshold was crossed, more data is required
        return "Continue (need more data)", cumulative_llr, llr_history

    # SPRT parameters via Streamlit sliders
    h0 = st.slider("Null hypothesis batting average (p0)", min_value=0.1, max_value=0.4, value=0.300, step=0.001, format="%.3f")
    h1 = st.slider("Alternative hypothesis batting average (p1)", min_value=0.1, max_value=0.4, value=0.330, step=0.001, format="%.3f")

    # require p1 > p0
    if h1 <= h0:
        st.error("p1 must be greater than p0. Please adjust the sliders.")
        st.stop()

    a = st.slider("Type I error (alpha)", min_value=0.001, max_value=1.0, value=0.01, step=0.001, format="%.3f")
    b = st.slider("Type II error (beta)", min_value=0.001, max_value=1.0, value=0.10, step=0.001, format="%.3f")

    decision, llr, steps = sprt_batting_average(at_bats_results, h0, h1, a, b)

    # Prepare dataframe for plotting
    df_llr = pd.DataFrame({
        "at_bat": list(range(1, len(steps) + 1)),
        "llr": steps
    })

    # Compute thresholds from current alpha (a) and beta (b)
    h1_thr = math.log((1 - b) / a)
    h0_thr = math.log(b / (1 - a))

    # Line with points and tooltips
    llr_line = alt.Chart(df_llr).mark_line(point=True).encode(
        x=alt.X("at_bat:Q", title="At-bat number"),
        y=alt.Y("llr:Q", title="Log-Likelihood Ratio"),
        tooltip=["at_bat", "llr"]
    ).properties(height=400)

    # Horizontal threshold rules
    h1_rule = alt.Chart(pd.DataFrame({"y":[h1_thr]})).mark_rule(color="green", strokeDash=[6,6]).encode(y="y:Q")
    h0_rule = alt.Chart(pd.DataFrame({"y":[h0_thr]})).mark_rule(color="red", strokeDash=[6,6]).encode(y="y:Q")

    # Combine and display
    chart = (llr_line + h1_rule + h0_rule).interactive()
    st.altair_chart(chart, use_container_width=True)

    #Create explanation for decision based on final llr
    def sprt_explanation(llr, p0=h0, p1=h1, alpha=a, beta=b, player=selected_player):
        # thresholds
        A = (1 - beta) / alpha
        B = beta / (1 - alpha)
        lnA, lnB = math.log(A), math.log(B)

        if llr >= lnA:
            decision = f"Evidence strongly supports {player} being closer to a {p1:.3f} hitter."
            explanation = (
                f"{player}'s log-likelihood ratio is {llr:.2f}, which is above the upper threshold {lnA:.2f}. "
                f"This means we can confidently classify him as a {p1:.3f}-level hitter rather than {p0:.3f}."
            )
        elif llr <= lnB:
            decision = f"Evidence supports {player} being closer to a {p0:.3f} hitter."
            explanation = (
                f"{player}'s log-likelihood ratio is {llr:.2f}, which is below the lower threshold {lnB:.2f}. "
                f"This means we classify him as a {p0:.3f}-level hitter."
            )
        else:
            decision = f"Not enough evidence yet for {player}."
            explanation = (
                f"{player}'s log-likelihood ratio is {llr:.2f}, which is between thresholds "
                f"{lnB:.2f} and {lnA:.2f}. We need more at-bats before making a confident decision."
            )

        return decision, explanation

    # Streamlit UI
    decision, explanation = sprt_explanation(llr)

    st.title("SPRT Decision and Explanation")
    st.subheader("Player: " + selected_player)
    st.write("Decision:", decision)
    st.write(explanation)

    st.markdown("Scope: Baseball Savant Statcast data from 2025 season")