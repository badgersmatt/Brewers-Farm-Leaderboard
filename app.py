import streamlit as st
import pandas as pd
import requests

st.title("Milwaukee Brewers Farm Leaderboard")

# Brewers affiliate team IDs (MiLB API)
TEAMS = {
    "AAA Nashville": 158,
    "AA Biloxi": 159,
    "High-A Wisconsin": 290,
    "Low-A Carolina": 291,
}

def fetch_team_stats(team_id):
    url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster?rosterType=active"
    roster = requests.get(url).json()

    players = []
    for p in roster.get("roster", []):
        players.append({
            "Player": p["person"]["fullName"],
            "Position": p["position"]["abbreviation"],
            "TeamID": team_id
        })

    return pd.DataFrame(players)

# Load all teams
all_players = []
for name, tid in TEAMS.items():
    df = fetch_team_stats(tid)
    df["Team"] = name
    all_players.append(df)

data = pd.concat(all_players)

# Favorites input
favorite_text = st.text_input("Enter favorite players (comma separated)")
favorites = {f.strip().lower() for f in favorite_text.split(",") if f}

data["Favorite"] = data["Player"].str.lower().isin(favorites)

# Display
st.dataframe(data.sort_values(["Favorite", "Player"], ascending=[False, True]))
