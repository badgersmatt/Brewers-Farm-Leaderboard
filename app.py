from __future__ import annotations

from datetime import datetime
from io import StringIO
import re

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Milwaukee Brewers Farm Leaderboard", layout="wide")

CURRENT_YEAR = datetime.now().year
HEADERS = {"User-Agent": "Mozilla/5.0 BrewersFarmLeaderboard/2.0"}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# Full-season affiliates use team pages. ACL and DSL use league pages filtered by TEAM.
SOURCES = [
    {
        "level": "AAA Nashville",
        "kind": "team_page",
        "team_slug": "nashville",
        "team_name": "Nashville Sounds",
    },
    {
        "level": "AA Biloxi",
        "kind": "team_page",
        "team_slug": "biloxi",
        "team_name": "Biloxi Shuckers",
    },
    {
        "level": "High-A Wisconsin",
        "kind": "team_page",
        "team_slug": "wisconsin",
        "team_name": "Wisconsin Timber Rattlers",
    },
    {
        "level": "Single-A Wilson",
        "kind": "team_page",
        "team_slug": "wilson",
        "team_name": "Wilson Warbirds",
    },
    {
        "level": "ACL Brewers",
        "kind": "league_page",
        "league_slug": "arizona-complex",
        "team_filter": "ACL Brewers",
    },
    {
        "level": "DSL Brewers Blue",
        "kind": "league_page",
        "league_slug": "dominican-summer",
        "team_filter": "DSL Brewers Blue",
    },
    {
        "level": "DSL Brewers Gold",
        "kind": "league_page",
        "league_slug": "dominican-summer",
        "team_filter": "DSL Brewers Gold",
    },
]

HITTING_COLS = ["PLAYER", "POS", "TEAM", "G", "AB", "AVG", "OBP", "SLG", "OPS", "HR", "RBI", "SB", "BB", "SO"]
PITCHING_COLS = ["PLAYER", "POS", "TEAM", "G", "GS", "IP", "ERA", "WHIP", "SV", "HLD", "SO", "BB", "W", "L"]
NUMERIC_HITTING = ["G", "AB", "AVG", "OBP", "SLG", "OPS", "HR", "RBI", "SB", "BB", "SO"]
NUMERIC_PITCHING = ["G", "GS", "IP", "ERA", "WHIP", "SV", "HLD", "SO", "BB", "W", "L"]


def safe_get_text(url: str) -> str:
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def find_stat_table(html: str, stat_type: str) -> pd.DataFrame:
    """Try to find the player stat table from MiLB HTML using pandas.read_html."""
    try:
        tables = pd.read_html(StringIO(html), displayed_only=False)
    except ValueError:
        return pd.DataFrame()

    wanted = HITTING_COLS if stat_type == "hitting" else PITCHING_COLS
    best = None
    best_score = -1

    for table in tables:
        cols = [str(c).strip().upper() for c in table.columns]
        score = sum(1 for c in wanted if c in cols)
        if "PLAYER" in cols and score > best_score and len(table) > 0:
            table = table.copy()
            table.columns = cols
            best = table
            best_score = score

    if best is None:
        return pd.DataFrame()

    return best


def clean_name(value: str) -> str:
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def clean_hitting_df(df: pd.DataFrame, level: str) -> pd.DataFrame:
    if df.empty:
        return df
    keep = [c for c in HITTING_COLS if c in df.columns]
    out = df[keep].copy()
    out = out[out["PLAYER"].notna()].copy()
    out["PLAYER"] = out["PLAYER"].map(clean_name)
    out = out[out["PLAYER"] != ""]
    out = out[~out["PLAYER"].str.contains("PLAYER", case=False, na=False)]
    if "TEAM" in out.columns:
        out["TEAM"] = out["TEAM"].astype(str).str.strip()
    else:
        out["TEAM"] = ""
    if "POS" not in out.columns:
        out["POS"] = ""
    for col in NUMERIC_HITTING:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    out["Level"] = level
    out = out.rename(columns={"PLAYER": "Player", "POS": "Pos"})
    return out


def clean_pitching_df(df: pd.DataFrame, level: str) -> pd.DataFrame:
    if df.empty:
        return df
    keep = [c for c in PITCHING_COLS if c in df.columns]
    out = df[keep].copy()
    out = out[out["PLAYER"].notna()].copy()
    out["PLAYER"] = out["PLAYER"].map(clean_name)
    out = out[out["PLAYER"] != ""]
    out = out[~out["PLAYER"].str.contains("PLAYER", case=False, na=False)]
    if "TEAM" in out.columns:
        out["TEAM"] = out["TEAM"].astype(str).str.strip()
    else:
        out["TEAM"] = ""
    if "POS" not in out.columns:
        out["POS"] = "P"
    for col in NUMERIC_PITCHING:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if "SO" in out.columns and "BB" in out.columns:
        out["K/BB"] = (out["SO"] / out["BB"].replace(0, pd.NA)).round(2)
    else:
        out["K/BB"] = pd.NA
    out["Level"] = level
    out = out.rename(columns={"PLAYER": "Player", "POS": "Pos"})
    return out


def build_url(source: dict, stat_type: str) -> str:
    suffix = "" if stat_type == "hitting" else "/pitching"
    # ALL_CURRENT is currently exposed by MiLB pages and avoids showing old affiliates/rehab noise.
    if source["kind"] == "team_page":
        return f"https://www.milb.com/{source['team_slug']}/stats{suffix}?playerPool=ALL_CURRENT"
    return f"https://www.milb.com/{source['league_slug']}/stats{suffix}?playerPool=ALL_CURRENT"


@st.cache_data(ttl=900, show_spinner=False)
def fetch_mlb_active_roster() -> set[str]:
    # Milwaukee Brewers MLB team id.
    url = "https://statsapi.mlb.com/api/v1/teams/158/roster"
    params = {"rosterType": "active"}
    try:
        resp = SESSION.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return set()

    names: set[str] = set()
    for item in data.get("roster", []):
        person = item.get("person") or {}
        full_name = person.get("fullName")
        if full_name:
            names.add(full_name.strip().lower())
    return names


@st.cache_data(ttl=900, show_spinner=False)
def load_all_data() -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str]]:
    hitters_frames: list[pd.DataFrame] = []
    pitchers_frames: list[pd.DataFrame] = []
    loaded: list[str] = []
    failed: list[str] = []

    for source in SOURCES:
        level = source["level"]
        try:
            hit_html = safe_get_text(build_url(source, "hitting"))
            pit_html = safe_get_text(build_url(source, "pitching"))

            hit_df = clean_hitting_df(find_stat_table(hit_html, "hitting"), level)
            pit_df = clean_pitching_df(find_stat_table(pit_html, "pitching"), level)

            if source["kind"] == "league_page":
                team_filter = source["team_filter"]
                if not hit_df.empty and "TEAM" in hit_df.columns:
                    hit_df = hit_df[hit_df["TEAM"].astype(str).str.strip().eq(team_filter)].copy()
                if not pit_df.empty and "TEAM" in pit_df.columns:
                    pit_df = pit_df[pit_df["TEAM"].astype(str).str.strip().eq(team_filter)].copy()
            else:
                # Team pages can still include occasional weird rows; keep only the visible affiliate team rows when present.
                if not hit_df.empty and "TEAM" in hit_df.columns:
                    # Some pages use abbreviations, some use full names. Keep non-empty rows and let the page scope do the work.
                    hit_df = hit_df[hit_df["TEAM"].astype(str).str.strip() != ""].copy()
                if not pit_df.empty and "TEAM" in pit_df.columns:
                    pit_df = pit_df[pit_df["TEAM"].astype(str).str.strip() != ""].copy()

            if hit_df.empty and pit_df.empty:
                failed.append(level)
            else:
                loaded.append(level)
                if not hit_df.empty:
                    hitters_frames.append(hit_df)
                if not pit_df.empty:
                    pitchers_frames.append(pit_df)
        except Exception:
            failed.append(level)

    hitters = pd.concat(hitters_frames, ignore_index=True) if hitters_frames else pd.DataFrame()
    pitchers = pd.concat(pitchers_frames, ignore_index=True) if pitchers_frames else pd.DataFrame()

    mlb_active = fetch_mlb_active_roster()
    if not hitters.empty:
        hitters = hitters[~hitters["Player"].str.lower().isin(mlb_active)].copy()
    if not pitchers.empty:
        pitchers = pitchers[~pitchers["Player"].str.lower().isin(mlb_active)].copy()

    return hitters, pitchers, loaded, failed


def add_favorites(df: pd.DataFrame, favorites: set[str]) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["Favorite"] = out["Player"].str.lower().isin(favorites)
    return out


st.title("Milwaukee Brewers Farm Leaderboard")
st.caption("Brewers minor leaguers only, with affiliate-specific stats by level.")

with st.sidebar:
    st.header("Favorites")
    favorite_text = st.text_area(
        "Players to pin to the top",
        placeholder="Jesús Made, Cooper Pratt, Jeferson Quero",
        help="Comma-separated names.",
    )
    show_only_favorites = st.checkbox("Show favorites only", value=False)
    min_games_hitters = st.slider("Minimum hitter games", 0, 50, 0)
    min_games_pitchers = st.slider("Minimum pitcher appearances", 0, 50, 0)

favorites = {name.strip().lower() for name in favorite_text.split(",") if name.strip()}

with st.spinner("Loading current Brewers affiliate stats..."):
    hitters, pitchers, loaded_levels, failed_levels = load_all_data()

hitters = add_favorites(hitters, favorites)
pitchers = add_favorites(pitchers, favorites)

all_levels = [source["level"] for source in SOURCES]
selected_levels = st.multiselect("Levels", all_levels, default=all_levels)

if not hitters.empty:
    hitters = hitters[hitters["Level"].isin(selected_levels)].copy()
    if "G" in hitters.columns:
        hitters = hitters[hitters["G"].fillna(0) >= min_games_hitters].copy()
if not pitchers.empty:
    pitchers = pitchers[pitchers["Level"].isin(selected_levels)].copy()
    if "G" in pitchers.columns:
        pitchers = pitchers[pitchers["G"].fillna(0) >= min_games_pitchers].copy()

if show_only_favorites:
    if not hitters.empty:
        hitters = hitters[hitters["Favorite"]].copy()
    if not pitchers.empty:
        pitchers = pitchers[pitchers["Favorite"]].copy()

c1, c2, c3 = st.columns(3)
c1.metric("Hitters", 0 if hitters.empty else len(hitters))
c2.metric("Pitchers", 0 if pitchers.empty else len(pitchers))
c3.metric("Levels loaded", len(loaded_levels))

if failed_levels:
    st.warning("These levels did not return usable data right now: " + ", ".join(failed_levels))

if hitters.empty and pitchers.empty:
    st.error("No affiliate stats loaded right now.")

h_tab, p_tab = st.tabs(["Hitters", "Pitchers"])

with h_tab:
    st.subheader("Hitter leaderboard")
    sort_hitters = st.selectbox("Sort hitters by", ["OPS", "HR", "RBI", "AVG", "OBP", "SLG", "SB", "BB", "SO"], index=0)
    if not hitters.empty:
        hitters = hitters.sort_values(["Favorite", sort_hitters, "Player"], ascending=[False, False, True]).reset_index(drop=True)
        show_cols = [c for c in ["Player", "Level", "Pos", "G", "AB", "AVG", "OBP", "SLG", "OPS", "HR", "RBI", "SB", "BB", "SO", "Favorite"] if c in hitters.columns]
        st.dataframe(
            hitters[show_cols],
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
        st.info("No hitter rows match the current filters.")

with p_tab:
    st.subheader("Pitcher leaderboard")
    sort_pitchers = st.selectbox("Sort pitchers by", ["ERA", "WHIP", "SO", "K/BB", "SV", "IP", "W"], index=0)
    if not pitchers.empty:
        asc = sort_pitchers in {"ERA", "WHIP"}
        pitchers = pitchers.sort_values(["Favorite", sort_pitchers, "Player"], ascending=[False, asc, True]).reset_index(drop=True)
        show_cols = [c for c in ["Player", "Level", "Pos", "G", "GS", "IP", "ERA", "WHIP", "SO", "BB", "K/BB", "SV", "HLD", "W", "L", "Favorite"] if c in pitchers.columns]
        st.dataframe(
            pitchers[show_cols],
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
        st.info("No pitcher rows match the current filters.")

st.caption("The app refreshes from official MiLB pages every 15 minutes. If a page changes format, that level may temporarily fail until the parser is updated.")
