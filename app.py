from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

import pandas as pd
import requests
import streamlit as st


st.set_page_config(page_title="Brewers Farm Board", layout="wide")


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class TeamSource:
    level: str
    team_name: str
    code: str
    hitting_url: str
    pitching_url: str


TEAM_SOURCES: list[TeamSource] = [
    TeamSource(
        level="Triple-A",
        team_name="Nashville Sounds",
        code="NAS",
        hitting_url="https://www.milb.com/nashville/stats/?playerPool=ALL",
        pitching_url="https://www.milb.com/nashville/stats/pitching/innings-pitched",
    ),
    TeamSource(
        level="Double-A",
        team_name="Biloxi Shuckers",
        code="BLX",
        hitting_url="https://www.milb.com/biloxi/stats/?playerPool=ALL",
        pitching_url="https://www.milb.com/biloxi/stats/pitching/innings-pitched",
    ),
    TeamSource(
        level="High-A",
        team_name="Wisconsin Timber Rattlers",
        code="WIS",
        hitting_url="https://www.milb.com/wisconsin/stats/?playerPool=ALL",
        pitching_url="https://www.milb.com/wisconsin/stats/pitching/innings-pitched",
    ),
    TeamSource(
        level="Single-A",
        team_name="Wilson Warbirds",
        code="WIL",
        hitting_url="https://www.milb.com/wilson/stats/?playerPool=ALL",
        pitching_url="https://www.milb.com/wilson/stats/pitching/innings-pitched",
    ),
    TeamSource(
        level="Rookie (ACL)",
        team_name="ACL Brewers",
        code="ACL",
        hitting_url="https://www.milb.com/arizona-complex/stats/acl-brewers",
        pitching_url="https://www.milb.com/arizona-complex/stats/pitching/innings-pitched",
    ),
    TeamSource(
        level="Rookie (DSL)",
        team_name="DSL Brewers Blue",
        code="DBB",
        hitting_url="https://www.milb.com/dominican-summer/stats/dsl-brewers-blue",
        pitching_url="https://www.milb.com/dominican-summer/stats/pitching/wins",
    ),
    TeamSource(
        level="Rookie (DSL)",
        team_name="DSL Brewers Gold",
        code="DBG",
        hitting_url="https://www.milb.com/dominican-summer/stats/dsl-brewers-gold",
        pitching_url="https://www.milb.com/dominican-summer/stats/pitching/wins",
    ),
]

HITTER_SORT_OPTIONS = {
    "OPS": "OPS",
    "HR": "HR",
    "AVG": "AVG",
    "OBP": "OBP",
    "SLG": "SLG",
    "RBI": "RBI",
    "SB": "SB",
    "Hits": "H",
}

PITCHER_SORT_OPTIONS = {
    "Strikeouts": "SO",
    "ERA (lowest first)": "ERA",
    "WHIP (lowest first)": "WHIP",
    "IP": "IP",
    "Saves": "SV",
    "Wins": "W",
}


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_html(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    return response.text


@st.cache_data(ttl=1800, show_spinner=False)
def read_tables(url: str) -> list[pd.DataFrame]:
    html = fetch_html(url)
    tables = pd.read_html(io.StringIO(html))
    return [normalize_columns(df) for df in tables]


@st.cache_data(ttl=1800, show_spinner=False)
def load_hitting_data() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for source in TEAM_SOURCES:
        try:
            raw = choose_stats_table(read_tables(source.hitting_url), mode="hitting")
            frame = clean_hitting_table(raw, source)
            if not frame.empty:
                frames.append(frame)
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    result = pd.concat(frames, ignore_index=True)
    return result.sort_values(["level_sort", "OPS", "HR", "RBI"], ascending=[True, False, False, False])


@st.cache_data(ttl=1800, show_spinner=False)
def load_pitching_data() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for source in TEAM_SOURCES:
        try:
            raw = choose_stats_table(read_tables(source.pitching_url), mode="pitching")
            frame = clean_pitching_table(raw, source)
            if not frame.empty:
                frames.append(frame)
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    result = pd.concat(frames, ignore_index=True)
    return result.sort_values(["level_sort", "SO", "IP"], ascending=[True, False, False])


LEVEL_ORDER = {
    "Triple-A": 1,
    "Double-A": 2,
    "High-A": 3,
    "Single-A": 4,
    "Rookie (ACL)": 5,
    "Rookie (DSL)": 6,
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    clean_cols: list[str] = []
    seen: dict[str, int] = {}
    for col in df.columns:
        if isinstance(col, tuple):
            pieces = [str(x).strip() for x in col if str(x).strip() and "Unnamed" not in str(x)]
            name = "_".join(pieces) if pieces else "col"
        else:
            name = str(col).strip()
        name = re.sub(r"\s+", " ", name)
        count = seen.get(name, 0)
        seen[name] = count + 1
        clean_cols.append(name if count == 0 else f"{name}_{count}")
    df.columns = clean_cols
    return df


def choose_stats_table(tables: Iterable[pd.DataFrame], mode: str) -> pd.DataFrame:
    tables = list(tables)
    for df in tables:
        cols = set(df.columns)
        if mode == "hitting" and {"PLAYER", "TEAM", "OPS"}.issubset(cols):
            return df
        if mode == "pitching" and {"PLAYER", "TEAM", "ERA", "SO"}.issubset(cols):
            return df
    raise ValueError(f"Could not find {mode} table")


NAME_PATTERN = re.compile(r"^\d+$")


def clean_player_name(value: object) -> str:
    text = str(value).replace("\xa0", " ").replace("‌", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if NAME_PATTERN.match(text):
        return ""
    return text


NUMERIC_COLUMNS_HITTING = [
    "G", "AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "SO", "SB", "CS", "AVG", "OBP", "SLG", "OPS",
]
NUMERIC_COLUMNS_PITCHING = [
    "W", "L", "ERA", "G", "GS", "CG", "SHO", "SV", "SVO", "IP", "H", "R", "ER", "HR", "HB", "BB", "SO", "WHIP", "AVG",
]


def to_numeric_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in cols:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace("\u200c", "", regex=False)
                .str.replace(" ", "", regex=False)
                .str.replace("—", "", regex=False)
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


TEAM_NAME_FIXES = {
    "NAS": "Nashville Sounds",
    "BLX": "Biloxi Shuckers",
    "WIS": "Wisconsin Timber Rattlers",
    "WIL": "Wilson Warbirds",
    "ACL": "ACL Brewers",
    "DBG": "DSL Brewers Gold",
    "DBB": "DSL Brewers Blue",
    "D-BWG": "DSL Brewers Gold",
    "D-BWB": "DSL Brewers Blue",
    "D-BW1": "DSL Brewers 1",
    "D-BW2": "DSL Brewers 2",
}


def clean_hitting_table(df: pd.DataFrame, source: TeamSource) -> pd.DataFrame:
    frame = df.copy()
    frame["PLAYER"] = frame.get("PLAYER", "").map(clean_player_name)
    frame = frame[frame["PLAYER"].ne("")].copy()
    keep = [c for c in ["PLAYER", "TEAM", "G", "AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "SO", "SB", "CS", "AVG", "OBP", "SLG", "OPS"] if c in frame.columns]
    frame = frame[keep]
    frame = to_numeric_columns(frame, NUMERIC_COLUMNS_HITTING)
    frame["level"] = source.level
    frame["team_name"] = source.team_name
    frame["team_code"] = frame.get("TEAM", source.code).astype(str).str.strip().replace(TEAM_NAME_FIXES)
    frame["team_display"] = frame["team_code"].replace(TEAM_NAME_FIXES).fillna(source.team_name)
    frame["level_sort"] = frame["level"].map(LEVEL_ORDER).fillna(99)
    frame["stat_group"] = "Hitter"
    return frame



def clean_pitching_table(df: pd.DataFrame, source: TeamSource) -> pd.DataFrame:
    frame = df.copy()
    frame["PLAYER"] = frame.get("PLAYER", "").map(clean_player_name)
    frame = frame[frame["PLAYER"].ne("")].copy()
    keep = [c for c in ["PLAYER", "TEAM", "W", "L", "ERA", "G", "GS", "SV", "SVO", "IP", "H", "R", "ER", "HR", "HB", "BB", "SO", "WHIP", "AVG"] if c in frame.columns]
    frame = frame[keep]
    frame = to_numeric_columns(frame, NUMERIC_COLUMNS_PITCHING)
    frame["level"] = source.level
    frame["team_name"] = source.team_name
    frame["team_code"] = frame.get("TEAM", source.code).astype(str).str.strip().replace(TEAM_NAME_FIXES)
    frame["team_display"] = frame["team_code"].replace(TEAM_NAME_FIXES).fillna(source.team_name)
    frame["level_sort"] = frame["level"].map(LEVEL_ORDER).fillna(99)
    frame["stat_group"] = "Pitcher"
    return frame



def parse_favorites(text: str) -> set[str]:
    names = [line.strip() for line in text.splitlines() if line.strip()]
    return {name.lower() for name in names}



def mark_favorites(df: pd.DataFrame, favorites: set[str]) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        out["favorite"] = pd.Series(dtype=bool)
        return out
    if "PLAYER" not in out.columns:
        out["favorite"] = False
        return out
    out["favorite"] = out["PLAYER"].astype(str).str.lower().isin(favorites)
    return out



def filter_hitters(df: pd.DataFrame, levels: list[str], min_ab: int, favorites_only: bool) -> pd.DataFrame:
    if df.empty or "level" not in df.columns:
        return df.copy()
    out = df[df["level"].isin(levels)].copy()
    if "AB" in out.columns:
        out = out[out["AB"].fillna(0) >= min_ab]
    if favorites_only and "favorite" in out.columns:
        out = out[out["favorite"]]
    return out



def filter_pitchers(df: pd.DataFrame, levels: list[str], min_ip: float, favorites_only: bool) -> pd.DataFrame:
    if df.empty or "level" not in df.columns:
        return df.copy()
    out = df[df["level"].isin(levels)].copy()
    if "IP" in out.columns:
        out = out[out["IP"].fillna(0) >= min_ip]
    if favorites_only and "favorite" in out.columns:
        out = out[out["favorite"]]
    return out



def format_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


DEFAULT_FAVORITES = """Cooper Pratt
Jesus Made
Brock Wilken
Luke Adams
Jeferson Quero
Jacob Misiorowski
Logan Henderson
Luis Pena
Brady Ebel
"""


st.title("Milwaukee Brewers Farm Leaderboard")
st.caption("All Brewers minor-league levels in one place, using official Brewers and MiLB stat pages.")

with st.sidebar:
    st.header("Filters")
    selected_levels = st.multiselect(
        "Levels",
        options=list(LEVEL_ORDER.keys()),
        default=list(LEVEL_ORDER.keys()),
    )
    favorite_text = st.text_area(
        "Favorite players (one name per line)",
        value=DEFAULT_FAVORITES,
        height=220,
        help="Leave this filled in for your own watch list, or clear it to browse everyone.",
    )
    favorites_only = st.checkbox("Show only favorites", value=False)
    min_ab = st.slider("Minimum hitter AB", min_value=0, max_value=250, value=10, step=5)
    min_ip = st.slider("Minimum pitcher IP", min_value=0.0, max_value=80.0, value=5.0, step=1.0)
    st.divider()
    st.caption("Data refreshes each time the app reloads. Results are cached for 30 minutes to avoid hammering MiLB pages.")

favorites = parse_favorites(favorite_text)

with st.spinner("Loading current stats from Brewers affiliate pages..."):
    hitters = mark_favorites(load_hitting_data(), favorites)
    pitchers = mark_favorites(load_pitching_data(), favorites)

if hitters.empty and pitchers.empty:
    st.error("No data loaded. This usually means one or more MiLB stat pages changed format.")
    st.stop()

hitters_view = filter_hitters(hitters, selected_levels, min_ab=min_ab, favorites_only=favorites_only)
pitchers_view = filter_pitchers(pitchers, selected_levels, min_ip=min_ip, favorites_only=favorites_only)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Hitters loaded", f"{len(hitters):,}")
col2.metric("Pitchers loaded", f"{len(pitchers):,}")
col3.metric("Favorites matched", f"{int(hitters['favorite'].sum() + pitchers['favorite'].sum()):,}")
col4.metric("Last refresh", format_timestamp())

if favorites:
    fav_hitters = hitters[hitters["favorite"]].sort_values(["OPS", "HR", "RBI"], ascending=[False, False, False])
    fav_pitchers = pitchers[pitchers["favorite"]].sort_values(["SO", "IP"], ascending=[False, False])
    top_left, top_right = st.columns(2)
    with top_left:
        st.subheader("Favorite hitters")
        if fav_hitters.empty:
            st.info("None of your listed favorite hitters were found in the current scraped data.")
        else:
            st.dataframe(
                fav_hitters[["PLAYER", "level", "team_display", "AB", "HR", "RBI", "SB", "AVG", "OBP", "SLG", "OPS"]],
                use_container_width=True,
                hide_index=True,
            )
    with top_right:
        st.subheader("Favorite pitchers")
        if fav_pitchers.empty:
            st.info("None of your listed favorite pitchers were found in the current scraped data.")
        else:
            st.dataframe(
                fav_pitchers[["PLAYER", "level", "team_display", "W", "L", "ERA", "IP", "BB", "SO", "WHIP", "SV"]],
                use_container_width=True,
                hide_index=True,
            )

hitters_tab, pitchers_tab = st.tabs(["Hitters", "Pitchers"])

with hitters_tab:
    st.subheader("Hitter leaderboard")
    hitter_sort_label = st.selectbox("Sort hitters by", list(HITTER_SORT_OPTIONS.keys()), index=0)
    hitter_sort_col = HITTER_SORT_OPTIONS[hitter_sort_label]
    hitter_ascending = hitter_sort_col in {"AVG"} and hitter_sort_label != "OPS"
    hitters_display = hitters_view.sort_values(
        ["favorite", hitter_sort_col, "HR", "RBI"],
        ascending=[False, hitter_ascending, False, False],
    )
    st.dataframe(
        hitters_display[["favorite", "PLAYER", "level", "team_display", "G", "AB", "H", "HR", "RBI", "SB", "AVG", "OBP", "SLG", "OPS"]],
        use_container_width=True,
        hide_index=True,
        column_config={"favorite": st.column_config.CheckboxColumn("★")},
    )

with pitchers_tab:
    st.subheader("Pitcher leaderboard")
    pitcher_sort_label = st.selectbox("Sort pitchers by", list(PITCHER_SORT_OPTIONS.keys()), index=0)
    pitcher_sort_col = PITCHER_SORT_OPTIONS[pitcher_sort_label]
    pitcher_ascending = pitcher_sort_col in {"ERA", "WHIP"}
    pitchers_display = pitchers_view.sort_values(
        ["favorite", pitcher_sort_col, "SO", "IP"],
        ascending=[False, pitcher_ascending, False, False],
    )
    st.dataframe(
        pitchers_display[["favorite", "PLAYER", "level", "team_display", "W", "L", "ERA", "G", "GS", "SV", "IP", "BB", "SO", "WHIP"]],
        use_container_width=True,
        hide_index=True,
        column_config={"favorite": st.column_config.CheckboxColumn("★")},
    )

with st.expander("Where the stats come from"):
    source_df = pd.DataFrame(
        [{
            "Level": s.level,
            "Team": s.team_name,
            "Hitting URL": s.hitting_url,
            "Pitching URL": s.pitching_url,
        } for s in TEAM_SOURCES]
    )
    st.dataframe(source_df, use_container_width=True, hide_index=True)
    st.markdown(
        "This app is a lightweight scraper of official Brewers and MiLB stats pages. "
        "If one of those pages changes its layout, the scraper may need a small adjustment."
    )
