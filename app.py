
import time
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Milwaukee Brewers Farm Leaderboard", layout="wide")

CURRENT_YEAR = datetime.now().year

# Current Brewers affiliates include Nashville, Biloxi, Wisconsin, Wilson,
# ACL Brewers, DSL Brewers Blue, and DSL Brewers Gold.
TEAM_IDS = {
    "AAA Nashville": 158,
    "AA Biloxi": 159,
    "High-A Wisconsin": 290,
    "Single-A Wilson": 291,   # same franchise slot formerly used by Carolina
    "ACL Brewers": 406,
    "DSL Brewers Blue": 607,
    "DSL Brewers Gold": 2101,
}

API_BASE = "https://statsapi.mlb.com/api/v1"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 BrewersFarmLeaderboard/1.0"})


def safe_get_json(url: str, params: dict | None = None) -> dict:
    try:
        r = SESSION.get(url, params=params, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_roster(team_id: int, season: int) -> list[dict]:
    data = safe_get_json(
        f"{API_BASE}/teams/{team_id}/roster",
        {"rosterType": "active", "season": season},
    )
    return data.get("roster", [])


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_player_group_stats(player_id: int, group: str, season: int) -> dict:
    data = safe_get_json(
        f"{API_BASE}/people/{player_id}/stats",
        {"stats": "season", "group": group, "season": season},
    )
    stats_blocks = data.get("stats", [])
    if not stats_blocks:
        return {}
    for block in stats_blocks:
        splits = block.get("splits", [])
        if splits:
            return splits[0].get("stat", {}) or {}
    return {}


def as_float(value, default=0.0):
    try:
        if value in (None, "", "--", "-.--"):
            return default
        return float(value)
    except Exception:
        return default


def as_int(value, default=0):
    try:
        if value in (None, "", "--"):
            return default
        return int(float(value))
    except Exception:
        return default


def build_rows_for_team(team_name: str, team_id: int, season: int) -> tuple[list[dict], list[dict]]:
    hitters = []
    pitchers = []

    roster = fetch_roster(team_id, season)
    for player in roster:
        person = player.get("person", {})
        position = (player.get("position") or {}).get("abbreviation", "")
        player_id = person.get("id")
        player_name = person.get("fullName", "Unknown")

        if not player_id:
            continue

        is_pitcher = position == "P"

        if is_pitcher:
            stat = fetch_player_group_stats(player_id, "pitching", season)
            pitchers.append(
                {
                    "Player": player_name,
                    "Level": team_name,
                    "Pos": position,
                    "G": as_int(stat.get("gamesPlayed")),
                    "GS": as_int(stat.get("gamesStarted")),
                    "IP": as_float(stat.get("inningsPitched")),
                    "ERA": as_float(stat.get("era")),
                    "WHIP": as_float(stat.get("whip")),
                    "K": as_int(stat.get("strikeOuts")),
                    "BB": as_int(stat.get("baseOnBalls")),
                    "SV": as_int(stat.get("saves")),
                    "HLD": as_int(stat.get("holds")),
                    "W": as_int(stat.get("wins")),
                    "L": as_int(stat.get("losses")),
                    "K/BB": round(
                        as_int(stat.get("strikeOuts")) / max(as_int(stat.get("baseOnBalls")), 1),
                        2,
                    ),
                }
            )
        else:
            stat = fetch_player_group_stats(player_id, "hitting", season)
            hitters.append(
                {
                    "Player": player_name,
                    "Level": team_name,
                    "Pos": position,
                    "G": as_int(stat.get("gamesPlayed")),
                    "AB": as_int(stat.get("atBats")),
                    "AVG": as_float(stat.get("avg")),
                    "OBP": as_float(stat.get("obp")),
                    "SLG": as_float(stat.get("slg")),
                    "OPS": as_float(stat.get("ops")),
                    "HR": as_int(stat.get("homeRuns")),
                    "RBI": as_int(stat.get("rbi")),
                    "SB": as_int(stat.get("stolenBases")),
                    "BB": as_int(stat.get("baseOnBalls")),
                    "K": as_int(stat.get("strikeOuts")),
                }
            )

    return hitters, pitchers


@st.cache_data(ttl=1800, show_spinner=False)
def load_all_data(season: int):
    all_hitters = []
    all_pitchers = []
    loaded_levels = []
    failed_levels = []

    for team_name, team_id in TEAM_IDS.items():
        try:
            h, p = build_rows_for_team(team_name, team_id, season)
            if h or p:
                loaded_levels.append(team_name)
            else:
                failed_levels.append(team_name)
            all_hitters.extend(h)
            all_pitchers.extend(p)
            time.sleep(0.05)
        except Exception:
            failed_levels.append(team_name)

    hitters_df = pd.DataFrame(all_hitters)
    pitchers_df = pd.DataFrame(all_pitchers)

    if not hitters_df.empty:
        hitters_df = hitters_df.sort_values(["OPS", "HR", "RBI"], ascending=[False, False, False])
    if not pitchers_df.empty:
        pitchers_df = pitchers_df.sort_values(["ERA", "WHIP", "K"], ascending=[True, True, False])

    return hitters_df, pitchers_df, loaded_levels, failed_levels


def apply_favorites(df: pd.DataFrame, favorites: set[str]) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        return out
    out["Favorite"] = out["Player"].str.lower().isin(favorites)
    return out


st.title("Milwaukee Brewers Farm Leaderboard")
st.caption("Actual season stats across the Brewers system — not just the roster.")

with st.sidebar:
    st.header("Settings")
    season = st.number_input("Season", min_value=2021, max_value=CURRENT_YEAR, value=CURRENT_YEAR, step=1)
    favorite_text = st.text_area(
        "Favorite players",
        placeholder="Jesús Made, Cooper Pratt, Jeferson Quero",
        help="Comma-separated names. Favorites float to the top.",
    )
    show_only_favorites = st.checkbox("Show favorites only", value=False)

favorites = {name.strip().lower() for name in favorite_text.split(",") if name.strip()}

with st.spinner("Loading Brewers minor-league stats..."):
    hitters, pitchers, loaded_levels, failed_levels = load_all_data(int(season))

hitters = apply_favorites(hitters, favorites)
pitchers = apply_favorites(pitchers, favorites)

all_levels = [lvl for lvl in TEAM_IDS.keys() if lvl in set(hitters.get("Level", pd.Series(dtype=str)).tolist() + pitchers.get("Level", pd.Series(dtype=str)).tolist())]
selected_levels = st.multiselect("Levels", options=all_levels or list(TEAM_IDS.keys()), default=all_levels or list(TEAM_IDS.keys()))

if selected_levels:
    if not hitters.empty:
        hitters = hitters[hitters["Level"].isin(selected_levels)]
    if not pitchers.empty:
        pitchers = pitchers[pitchers["Level"].isin(selected_levels)]

if show_only_favorites:
    if not hitters.empty:
        hitters = hitters[hitters["Favorite"]]
    if not pitchers.empty:
        pitchers = pitchers[pitchers["Favorite"]]

c1, c2, c3 = st.columns(3)
c1.metric("Hitters loaded", len(hitters))
c2.metric("Pitchers loaded", len(pitchers))
c3.metric("Levels loaded", len(loaded_levels))

if failed_levels:
    st.warning("These levels did not return usable data right now: " + ", ".join(failed_levels))

tab1, tab2 = st.tabs(["Hitters", "Pitchers"])

with tab1:
    st.subheader("Hitter leaderboard")
    hitter_sort = st.selectbox("Sort hitters by", ["OPS", "HR", "RBI", "AVG", "OBP", "SLG", "SB", "BB", "K"], index=0)
    if not hitters.empty:
        hitters_display = hitters.sort_values(
            by=["Favorite", hitter_sort, "Player"],
            ascending=[False, False, True],
        ).reset_index(drop=True)
        st.dataframe(
            hitters_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "AVG": st.column_config.NumberColumn(format="%.3f"),
                "OBP": st.column_config.NumberColumn(format="%.3f"),
                "SLG": st.column_config.NumberColumn(format="%.3f"),
                "OPS": st.column_config.NumberColumn(format="%.3f"),
                "Favorite": st.column_config.CheckboxColumn(),
            },
        )
    else:
        st.info("No hitter stats loaded.")

with tab2:
    st.subheader("Pitcher leaderboard")
    pitcher_sort = st.selectbox("Sort pitchers by", ["ERA", "WHIP", "K", "K/BB", "SV", "IP", "W"], index=0)
    if not pitchers.empty:
        ascending = pitcher_sort in {"ERA", "WHIP"}
        pitchers_display = pitchers.sort_values(
            by=["Favorite", pitcher_sort, "Player"],
            ascending=[False, ascending, True],
        ).reset_index(drop=True)
        st.dataframe(
            pitchers_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ERA": st.column_config.NumberColumn(format="%.2f"),
                "WHIP": st.column_config.NumberColumn(format="%.2f"),
                "IP": st.column_config.NumberColumn(format="%.1f"),
                "K/BB": st.column_config.NumberColumn(format="%.2f"),
                "Favorite": st.column_config.CheckboxColumn(),
            },
        )
    else:
        st.info("No pitcher stats loaded.")

st.caption("Data refresh is cached for about 30 minutes to keep the app responsive.")
