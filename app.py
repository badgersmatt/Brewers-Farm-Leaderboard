"""
Milwaukee Brewers Farm System Leaderboard
==========================================
Uses the MLB Stats API (statsapi.mlb.com) instead of scraping MiLB HTML pages.
The old HTML scraper broke because MiLB's stat tables are now JavaScript-rendered
and pd.read_html returns empty results. The Stats API is stable structured JSON.

Features
--------
- Hitter & pitcher leaderboards across all 7 affiliate levels
- "Who's Hot" tab: players ranked by recent-game performance
- Projected MLB Debut estimate (composite of age, level, performance)
- Pin favorite players to the top of any view
- Level filter, minimum games filter, position filter
- 15-minute cache (respects rate limits)
"""

from __future__ import annotations

import re
from datetime import datetime, date
from typing import Any

import pandas as pd
import requests
import streamlit as st

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Brewers Farm Leaderboard",
    page_icon="🧀",
    layout="wide",
)

# ── Brewers theme CSS ─────────────────────────────────────────────────────────
BREWERS_CSS = """
<style>
/* Background */
.stApp { background: #0A2351; }
.stApp > header { background: transparent !important; }

/* Typography */
h1 { color: #FFC52F !important; font-size: 2.4rem !important; font-weight: 800 !important; letter-spacing: -0.5px; }
h2, h3 { color: #FFC52F !important; }
p, .stMarkdown, label { color: rgba(255,255,255,0.88) !important; }
small, .stCaption p { color: rgba(255,255,255,0.5) !important; }

/* Metric cards */
[data-testid="stMetric"] {
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,197,47,0.25);
    border-radius: 12px;
    padding: 1rem 1.25rem !important;
}
[data-testid="stMetricLabel"] { color: rgba(255,255,255,0.55) !important; font-size: 0.78rem !important; }
[data-testid="stMetricValue"] { color: #FFC52F !important; font-weight: 700 !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.06);
    border-radius: 10px;
    gap: 4px;
    padding: 4px;
}
.stTabs [data-baseweb="tab"] { border-radius: 8px; color: rgba(255,255,255,0.6) !important; font-weight: 500; }
.stTabs [aria-selected="true"] { background: #FFC52F !important; color: #0A2351 !important; font-weight: 700; }

/* Sidebar */
[data-testid="stSidebar"] { background: #071838 !important; border-right: 1px solid rgba(255,197,47,0.15); }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: #FFC52F !important; }

/* Inputs & selects */
[data-testid="stTextArea"] textarea { background: rgba(255,255,255,0.08) !important; border-color: rgba(255,197,47,0.3) !important; color: white !important; }
[data-baseweb="select"] > div { background: rgba(255,255,255,0.08) !important; border-color: rgba(255,197,47,0.3) !important; }
[data-baseweb="tag"] { background: #FFC52F !important; }
[data-baseweb="tag"] span { color: #0A2351 !important; font-weight: 600 !important; }
[data-baseweb="popover"] { background: #0e2d5e !important; }
[data-baseweb="menu"] { background: #0e2d5e !important; }
li[role="option"] { color: white !important; }
li[role="option"]:hover { background: rgba(255,197,47,0.15) !important; }

/* Slider */
[data-testid="stSlider"] div[role="slider"] { background: #FFC52F !important; border-color: #FFC52F !important; }
[data-testid="stSlider"] [data-testid="stTickBar"] { color: rgba(255,255,255,0.4) !important; }

/* Dataframes */
[data-testid="stDataFrameResizable"] { border: 1px solid rgba(255,197,47,0.2) !important; border-radius: 10px; overflow: hidden; }

/* Alerts */
[data-testid="stAlert"] { border-radius: 10px; }

/* Expander */
[data-testid="stExpander"] { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,197,47,0.2) !important; border-radius: 10px; }
[data-testid="stExpander"] summary { color: #FFC52F !important; font-weight: 600; }

/* Divider */
hr { border-color: rgba(255,197,47,0.15) !important; }

/* Spinner */
[data-testid="stSpinner"] { color: #FFC52F !important; }

/* Checkbox */
[data-testid="stCheckbox"] span { color: rgba(255,255,255,0.85) !important; }

/* Multiselect selected tag */
[data-baseweb="tag"] svg { fill: #0A2351 !important; }
</style>
"""

# ── Constants ──────────────────────────────────────────────────────────────────
BREWERS_ORG_ID = 158          # MLB team ID for Milwaukee Brewers
CURRENT_YEAR   = datetime.now().year

BASE = "https://statsapi.mlb.com/api/v1"
HEADERS = {"User-Agent": "BrewersFarmLeaderboard/3.0"}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# Sport IDs used by the MLB Stats API
# 1=MLB, 11=AAA, 12=AA, 13=High-A, 14=Single-A, 16=ROK(ACL/DSL)
SPORT_IDS = {
    "AAA":      11,
    "AA":       12,
    "High-A":   13,
    "Single-A": 14,
    "ACL/DSL":  16,
}

# Projected debut parameters (tweak as desired)
# For each level, average years remaining to MLB:
LEVEL_YEARS_TO_MLB = {
    "AAA":      0.8,
    "AA":       1.5,
    "High-A":   2.5,
    "Single-A": 3.5,
    "ACL/DSL":  5.0,
}

HITTING_DISPLAY  = ["Player", "Level", "Pos", "Age", "G", "AB", "AVG", "OBP", "SLG", "OPS", "HR", "RBI", "SB", "BB", "SO", "Proj Debut"]
PITCHING_DISPLAY = ["Player", "Level", "Pos", "Age", "G", "GS", "IP", "ERA", "WHIP", "SO", "BB", "K/BB", "SV", "HLD", "W", "L", "Proj Debut"]


# ── Helpers ────────────────────────────────────────────────────────────────────

def safe_get(url: str, params: dict | None = None) -> dict:
    resp = SESSION.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def age_from_dob(dob_str: str | None) -> int | None:
    if not dob_str:
        return None
    try:
        dob = datetime.strptime(dob_str[:10], "%Y-%m-%d").date()
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception:
        return None


def projected_debut(level_key: str, age: int | None, perf_score: float) -> str:
    """
    Estimate MLB debut year.

    Formula:
      base_years  = league-average years from that level to MLB
      age_factor  = (age - 22) * 0.15   → older prospects take less time
      perf_bonus  = perf_score           → high-performers accelerate 0–0.5 yrs
      years_out   = max(0.3, base - age_factor - perf_bonus)

    perf_score is 0–0.5, supplied by caller.
    Returns a year string or "Unknown".
    """
    if age is None:
        return "Unknown"
    base   = LEVEL_YEARS_TO_MLB.get(level_key, 3.0)
    age_f  = (age - 22) * 0.15
    years  = max(0.3, base - age_f - perf_score)
    debut_year = CURRENT_YEAR + round(years)
    return str(debut_year)


def hitter_perf_score(row: pd.Series) -> float:
    """0–0.5 composite from OPS, HR rate, SB."""
    ops = row.get("OPS", 0) or 0
    hr  = row.get("HR", 0)  or 0
    ab  = row.get("AB", 1)  or 1
    sb  = row.get("SB", 0)  or 0
    score = 0.0
    if ops >= 1.000: score += 0.25
    elif ops >= 0.900: score += 0.20
    elif ops >= 0.800: score += 0.10
    hr_rate = hr / ab
    if hr_rate >= 0.05: score += 0.15
    elif hr_rate >= 0.03: score += 0.08
    if sb >= 15: score += 0.10
    elif sb >= 8: score += 0.05
    return min(score, 0.5)


def pitcher_perf_score(row: pd.Series) -> float:
    """0–0.5 composite from ERA, WHIP, K/BB."""
    era  = row.get("ERA", 99) or 99
    whip = row.get("WHIP", 99) or 99
    kbb  = row.get("K/BB", 0) or 0
    score = 0.0
    if era <= 2.00: score += 0.20
    elif era <= 3.00: score += 0.15
    elif era <= 4.00: score += 0.08
    if whip <= 1.00: score += 0.15
    elif whip <= 1.20: score += 0.08
    if kbb >= 4.0: score += 0.15
    elif kbb >= 2.5: score += 0.08
    return min(score, 0.5)


def level_key_from_sport(sport_id: int, level_name: str) -> str:
    mapping = {11: "AAA", 12: "AA", 13: "High-A", 14: "Single-A", 16: "ACL/DSL"}
    return mapping.get(sport_id, level_name)


# ── MLB Stats API calls ────────────────────────────────────────────────────────

@st.cache_data(ttl=900, show_spinner=False)
def fetch_affiliates() -> list[dict]:
    """Return list of Brewers affiliate team dicts with id, name, sport."""
    data = safe_get(f"{BASE}/teams", params={
        "sportIds": "11,12,13,14,16",
        "season":   CURRENT_YEAR,
    })
    affiliates = []
    for team in data.get("teams", []):
        if team.get("parentOrgId") == BREWERS_ORG_ID and team.get("id") != BREWERS_ORG_ID:
            sport    = team.get("sport", {})
            sport_id = sport.get("id")
            affiliates.append({
                "id":         team["id"],
                "name":       team["name"],
                "sport_id":   sport_id,
                "level_key":  level_key_from_sport(sport_id, sport.get("name", "?")),
                "level_name": f"{level_key_from_sport(sport_id, '')} {team['name']}",
            })
    return affiliates


@st.cache_data(ttl=900, show_spinner=False)
def fetch_mlb_active_roster() -> set[str]:
    try:
        data = safe_get(f"{BASE}/teams/{BREWERS_ORG_ID}/roster",
                        params={"rosterType": "active"})
        return {p["person"]["fullName"].strip().lower()
                for p in data.get("roster", [])
                if p.get("person", {}).get("fullName")}
    except Exception:
        return set()


@st.cache_data(ttl=900, show_spinner=False)
def fetch_game_log(player_id: int, group: str) -> pd.DataFrame:
    """Fetch per-game stats for a single player. group = 'hitting' or 'pitching'."""
    try:
        data = safe_get(f"{BASE}/people/{player_id}/stats", params={
            "stats":    "gameLog",
            "group":    group,
            "season":   CURRENT_YEAR,
            "gameType": "R",
        })
        splits = data.get("stats", [{}])[0].get("splits", [])
        rows = []
        for split in splits:
            s   = split.get("stat", {})
            opp = split.get("opponent", {}).get("abbreviation", split.get("opponent", {}).get("name", ""))
            dt  = split.get("date", "")
            loc = "vs" if split.get("isHome") else "@"

            if group == "hitting":
                rows.append({
                    "Date": dt,
                    "Opp":  f"{loc} {opp}",
                    "AB":   int(s.get("atBats", 0) or 0),
                    "R":    int(s.get("runs", 0) or 0),
                    "H":    int(s.get("hits", 0) or 0),
                    "2B":   int(s.get("doubles", 0) or 0),
                    "3B":   int(s.get("triples", 0) or 0),
                    "HR":   int(s.get("homeRuns", 0) or 0),
                    "RBI":  int(s.get("rbi", 0) or 0),
                    "BB":   int(s.get("baseOnBalls", 0) or 0),
                    "SO":   int(s.get("strikeOuts", 0) or 0),
                    "SB":   int(s.get("stolenBases", 0) or 0),
                    "AVG":  round(float(s.get("avg", 0) or 0), 3),
                })
            else:
                dec = ""
                if int(s.get("wins", 0) or 0):   dec = "W"
                elif int(s.get("losses", 0) or 0): dec = "L"
                elif int(s.get("saves", 0) or 0):  dec = "SV"
                elif int(s.get("holds", 0) or 0):  dec = "HLD"
                rows.append({
                    "Date": dt,
                    "Opp":  f"{loc} {opp}",
                    "Dec":  dec,
                    "IP":   round(float(s.get("inningsPitched", 0) or 0), 1),
                    "H":    int(s.get("hits", 0) or 0),
                    "R":    int(s.get("runs", 0) or 0),
                    "ER":   int(s.get("earnedRuns", 0) or 0),
                    "BB":   int(s.get("baseOnBalls", 0) or 0),
                    "SO":   int(s.get("strikeOuts", 0) or 0),
                    "HR":   int(s.get("homeRuns", 0) or 0),
                    "ERA":  round(float(s.get("era", 0) or 0), 2),
                })
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("Date", ascending=False).reset_index(drop=True)
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def fetch_team_hitting(team_id: int, sport_id: int, level_key: str, level_name: str) -> pd.DataFrame:
    try:
        data = safe_get(f"{BASE}/stats", params={
            "stats":    "season",
            "group":    "hitting",
            "gameType": "R",
            "season":   CURRENT_YEAR,
            "teamId":   team_id,
            "sportId":  sport_id,
            "hydrate":  "person",
        })
        rows = []
        for split in data.get("stats", [{}])[0].get("splits", []):
            p    = split.get("player", {})
            pos  = split.get("position", {}).get("abbreviation", "")
            s    = split.get("stat", {})
            dob  = p.get("birthDate") or p.get("person", {}).get("birthDate")
            a    = age_from_dob(dob)

            avg  = float(s.get("avg", 0) or 0)
            obp  = float(s.get("obp", 0) or 0)
            slg  = float(s.get("slg", 0) or 0)
            ops  = float(s.get("ops", 0) or 0)

            rows.append({
                "Player":    p.get("fullName", ""),
                "player_id": p.get("id"),
                "Pos":       pos,
                "Age":       a,
                "G":         int(s.get("gamesPlayed", 0) or 0),
                "AB":        int(s.get("atBats", 0) or 0),
                "AVG":       round(avg, 3),
                "OBP":       round(obp, 3),
                "SLG":       round(slg, 3),
                "OPS":       round(ops, 3),
                "HR":        int(s.get("homeRuns", 0) or 0),
                "RBI":       int(s.get("rbi", 0) or 0),
                "SB":        int(s.get("stolenBases", 0) or 0),
                "BB":        int(s.get("baseOnBalls", 0) or 0),
                "SO":        int(s.get("strikeOuts", 0) or 0),
                "Level":     level_name,
                "level_key": level_key,
            })
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        # Compute projected debut
        df["Proj Debut"] = df.apply(
            lambda r: projected_debut(r["level_key"], r["Age"], hitter_perf_score(r)), axis=1
        )
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def fetch_team_pitching(team_id: int, sport_id: int, level_key: str, level_name: str) -> pd.DataFrame:
    try:
        data = safe_get(f"{BASE}/stats", params={
            "stats":    "season",
            "group":    "pitching",
            "gameType": "R",
            "season":   CURRENT_YEAR,
            "teamId":   team_id,
            "sportId":  sport_id,
            "hydrate":  "person",
        })
        rows = []
        for split in data.get("stats", [{}])[0].get("splits", []):
            p    = split.get("player", {})
            pos  = split.get("position", {}).get("abbreviation", "P")
            s    = split.get("stat", {})
            dob  = p.get("birthDate") or p.get("person", {}).get("birthDate")
            a    = age_from_dob(dob)

            era  = float(s.get("era", 0) or 0)
            whip = float(s.get("whip", 0) or 0)
            ip   = float(s.get("inningsPitched", 0) or 0)
            so   = int(s.get("strikeOuts", 0) or 0)
            bb   = int(s.get("baseOnBalls", 0) or 0)
            kbb  = round(so / bb, 2) if bb > 0 else None

            rows.append({
                "Player":    p.get("fullName", ""),
                "player_id": p.get("id"),
                "Pos":       pos,
                "Age":       a,
                "G":         int(s.get("gamesPitched", 0) or 0),
                "GS":        int(s.get("gamesStarted", 0) or 0),
                "IP":        round(ip, 1),
                "ERA":       round(era, 2),
                "WHIP":      round(whip, 2),
                "SO":        so,
                "BB":        bb,
                "K/BB":      kbb,
                "SV":        int(s.get("saves", 0) or 0),
                "HLD":       int(s.get("holds", 0) or 0),
                "W":         int(s.get("wins", 0) or 0),
                "L":         int(s.get("losses", 0) or 0),
                "Level":     level_name,
                "level_key": level_key,
            })
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        df["Proj Debut"] = df.apply(
            lambda r: projected_debut(r["level_key"], r["Age"], pitcher_perf_score(r)), axis=1
        )
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def load_all_data() -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str]]:
    affiliates = fetch_affiliates()
    mlb_active = fetch_mlb_active_roster()

    hitter_frames:  list[pd.DataFrame] = []
    pitcher_frames: list[pd.DataFrame] = []
    loaded: list[str] = []
    failed: list[str] = []

    for aff in affiliates:
        tid   = aff["id"]
        lk    = aff["level_key"]
        ln    = aff["level_name"]
        hit   = fetch_team_hitting(tid, aff["sport_id"], lk, ln)
        pit   = fetch_team_pitching(tid, aff["sport_id"], lk, ln)

        if hit.empty and pit.empty:
            failed.append(ln)
        else:
            loaded.append(ln)
            if not hit.empty:
                hitter_frames.append(hit)
            if not pit.empty:
                pitcher_frames.append(pit)

    hitters  = pd.concat(hitter_frames,  ignore_index=True) if hitter_frames  else pd.DataFrame()
    pitchers = pd.concat(pitcher_frames, ignore_index=True) if pitcher_frames else pd.DataFrame()

    # Remove players on MLB active roster
    if not hitters.empty:
        hitters  = hitters[~hitters["Player"].str.lower().isin(mlb_active)].copy()
    if not pitchers.empty:
        pitchers = pitchers[~pitchers["Player"].str.lower().isin(mlb_active)].copy()

    return hitters, pitchers, loaded, failed


def add_favorites(df: pd.DataFrame, favorites: set[str]) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["⭐"] = out["Player"].str.lower().isin(favorites)
    return out


def hot_hitters(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """
    'Who's Hot' for hitters.
    We don't have rolling game logs from cached season data, so we use OPS
    as the primary signal, weighted by games played (to avoid tiny-sample noise).
    Players with G < 5 are excluded.
    """
    if df.empty:
        return df
    d = df[df["G"] >= 5].copy()
    # Heat index: OPS * log(G+1) – penalise excessive Ks
    import math
    d["Heat"] = d.apply(
        lambda r: (r["OPS"] or 0) * math.log1p(r["G"]) - 0.003 * (r["SO"] or 0),
        axis=1,
    )
    return d.sort_values("Heat", ascending=False).head(top_n)


def hot_pitchers(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    if df.empty:
        return df
    d = df[(df["G"] >= 3) & (df["IP"] >= 5)].copy()
    import math
    # Lower ERA + WHIP = hotter; K/BB bonus
    d["Heat"] = d.apply(
        lambda r: (
            -(r["ERA"] or 9) * 0.4
            -(r["WHIP"] or 2) * 2
            + (r["K/BB"] or 0) * 0.3
            + math.log1p(r["SO"] or 0) * 0.2
        ),
        axis=1,
    )
    return d.sort_values("Heat", ascending=False).head(top_n)


# ══════════════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════════════

st.markdown(BREWERS_CSS, unsafe_allow_html=True)

st.title("🧀 Milwaukee Brewers Farm Leaderboard")
st.caption(f"Affiliate stats · {CURRENT_YEAR} season · refreshed every 15 minutes from MLB Stats API")

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⭐ Favorites")
    favorite_text = st.text_area(
        "Pin players to top",
        placeholder="Jackson Chourio, Sal Frelick, …",
        help="Comma-separated player names.",
    )
    show_only_favorites = st.checkbox("Show favorites only")

    st.divider()
    st.header("🔍 Filters")
    min_games_h = st.slider("Min hitter games",   0, 60, 0)
    min_games_p = st.slider("Min pitcher apps",   0, 30, 0)

favorites = {n.strip().lower() for n in favorite_text.split(",") if n.strip()}

# ── Load data ──────────────────────────────────────────────────────────────────
with st.spinner("Loading Brewers affiliate stats…"):
    hitters, pitchers, loaded_levels, failed_levels = load_all_data()

hitters  = add_favorites(hitters,  favorites)
pitchers = add_favorites(pitchers, favorites)

# ── Level filter (after load so we know what's available) ─────────────────────
all_levels = sorted(set(
    list(hitters["Level"].unique()  if not hitters.empty  else []) +
    list(pitchers["Level"].unique() if not pitchers.empty else [])
))
selected_levels = st.multiselect("Levels to include", all_levels, default=all_levels)

# Apply filters
def apply_filters(df: pd.DataFrame, min_g: int, col: str = "G") -> pd.DataFrame:
    if df.empty:
        return df
    df = df[df["Level"].isin(selected_levels)].copy()
    if col in df.columns:
        df = df[df[col].fillna(0) >= min_g].copy()
    if show_only_favorites:
        df = df[df["⭐"]].copy()
    return df

hitters  = apply_filters(hitters,  min_games_h, "G")
pitchers = apply_filters(pitchers, min_games_p, "G")

# ── Summary metrics ────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Hitters",      0 if hitters.empty  else len(hitters))
c2.metric("Pitchers",     0 if pitchers.empty else len(pitchers))
c3.metric("Levels loaded", len(loaded_levels))
if failed_levels:
    c4.metric("⚠ Failed levels", len(failed_levels))
    acl_dsl = all("ACL" in l or "DSL" in l for l in failed_levels)
    if acl_dsl:
        st.info(
            f"**{', '.join(failed_levels)}** — no data yet. "
            "The ACL and DSL rookie leagues don't start until June–July. "
            "They'll populate automatically once the season begins."
        )
    else:
        st.warning("Levels with no data: " + ", ".join(failed_levels))

if hitters.empty and pitchers.empty:
    st.error("No affiliate stats returned. The MLB Stats API may be down or rate-limiting. Try again shortly.")
    st.stop()

# ── Column format helpers ──────────────────────────────────────────────────────
HIT_FORMATS = {
    "AVG": st.column_config.NumberColumn(format="%.3f"),
    "OBP": st.column_config.NumberColumn(format="%.3f"),
    "SLG": st.column_config.NumberColumn(format="%.3f"),
    "OPS": st.column_config.NumberColumn(format="%.3f"),
    "⭐":  st.column_config.CheckboxColumn(label="Fav"),
}
PIT_FORMATS = {
    "ERA":  st.column_config.NumberColumn(format="%.2f"),
    "WHIP": st.column_config.NumberColumn(format="%.2f"),
    "IP":   st.column_config.NumberColumn(format="%.1f"),
    "K/BB": st.column_config.NumberColumn(format="%.2f"),
    "⭐":   st.column_config.CheckboxColumn(label="Fav"),
}

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_h, tab_p, tab_hot, tab_debut = st.tabs(["🏏 Hitters", "⚾ Pitchers", "🔥 Who's Hot", "📅 Projected Debuts"])

# ── Hitters tab ───────────────────────────────────────────────────────────────
with tab_h:
    st.subheader("Hitter Leaderboard")
    sort_h = st.selectbox("Sort by", ["OPS", "HR", "RBI", "AVG", "OBP", "SLG", "SB", "BB", "SO"], key="sort_h")
    pos_filter = st.multiselect("Position", sorted(hitters["Pos"].dropna().unique()) if not hitters.empty else [], key="pos_h")

    view = hitters.copy()
    if pos_filter:
        view = view[view["Pos"].isin(pos_filter)]
    if not view.empty:
        view = view.sort_values(["⭐", sort_h, "Player"], ascending=[False, False, True]).reset_index(drop=True)
        cols = [c for c in HITTING_DISPLAY + ["⭐"] if c in view.columns]
        st.caption("Click a row to see that player's game log.")
        event = st.dataframe(
            view[cols], use_container_width=True, hide_index=True,
            column_config=HIT_FORMATS,
            on_select="rerun", selection_mode="single-row",
            key="hitter_table",
        )
        sel = event.selection.rows
        if sel:
            row = view.iloc[sel[0]]
            pid, pname = row.get("player_id"), row["Player"]
            with st.expander(f"📊 {pname} — Game Log ({CURRENT_YEAR})", expanded=True):
                with st.spinner("Loading game log…"):
                    log = fetch_game_log(int(pid), "hitting")
                if log.empty:
                    st.info("No game log available yet.")
                else:
                    st.dataframe(
                        log, use_container_width=True, hide_index=True,
                        column_config={"AVG": st.column_config.NumberColumn(format="%.3f")},
                    )
    else:
        st.info("No hitter rows match the current filters.")

# ── Pitchers tab ──────────────────────────────────────────────────────────────
with tab_p:
    st.subheader("Pitcher Leaderboard")
    sort_p = st.selectbox("Sort by", ["ERA", "WHIP", "SO", "K/BB", "SV", "IP", "W"], key="sort_p")
    asc_p  = sort_p in {"ERA", "WHIP"}

    view = pitchers.copy()
    if not view.empty:
        view = view.sort_values(["⭐", sort_p, "Player"], ascending=[False, asc_p, True]).reset_index(drop=True)
        cols = [c for c in PITCHING_DISPLAY + ["⭐"] if c in view.columns]
        st.caption("Click a row to see that player's game log.")
        event = st.dataframe(
            view[cols], use_container_width=True, hide_index=True,
            column_config=PIT_FORMATS,
            on_select="rerun", selection_mode="single-row",
            key="pitcher_table",
        )
        sel = event.selection.rows
        if sel:
            row = view.iloc[sel[0]]
            pid, pname = row.get("player_id"), row["Player"]
            with st.expander(f"📊 {pname} — Game Log ({CURRENT_YEAR})", expanded=True):
                with st.spinner("Loading game log…"):
                    log = fetch_game_log(int(pid), "pitching")
                if log.empty:
                    st.info("No game log available yet.")
                else:
                    st.dataframe(
                        log, use_container_width=True, hide_index=True,
                        column_config={
                            "IP":  st.column_config.NumberColumn(format="%.1f"),
                            "ERA": st.column_config.NumberColumn(format="%.2f"),
                        },
                    )
    else:
        st.info("No pitcher rows match the current filters.")

# ── Who's Hot tab ─────────────────────────────────────────────────────────────
with tab_hot:
    st.subheader("🔥 Who's Hot")
    st.caption(
        "Heat index for hitters = OPS × log(G+1) − SO penalty. "
        "For pitchers = inverse of ERA/WHIP + K/BB bonus. "
        "Minimum 5 G (hitters) / 3 G + 5 IP (pitchers)."
    )

    hh = hot_hitters(hitters)
    hp = hot_pitchers(pitchers)

    ch, cp = st.columns(2)

    with ch:
        st.markdown("**🔥 Hot Hitters**")
        if not hh.empty:
            cols = [c for c in ["Player", "Level", "Pos", "G", "OPS", "HR", "RBI", "SB"] if c in hh.columns]
            st.dataframe(hh[cols].reset_index(drop=True), use_container_width=True, hide_index=True,
                         column_config={"OPS": st.column_config.NumberColumn(format="%.3f")})
        else:
            st.info("Not enough data yet.")

    with cp:
        st.markdown("**🔥 Hot Pitchers**")
        if not hp.empty:
            cols = [c for c in ["Player", "Level", "Pos", "G", "ERA", "WHIP", "SO", "K/BB"] if c in hp.columns]
            st.dataframe(hp[cols].reset_index(drop=True), use_container_width=True, hide_index=True,
                         column_config=PIT_FORMATS)
        else:
            st.info("Not enough data yet.")

# ── Projected Debuts tab ──────────────────────────────────────────────────────
with tab_debut:
    st.subheader("📅 Projected MLB Debut")
    st.caption(
        "Estimates only — based on current level, age, and performance. "
        "Formula: base years-to-MLB for that level, adjusted for age (older = faster) "
        "and performance (elite stats = up to 6 months faster). Not a scout's projection."
    )

    all_players = pd.concat([
        hitters[["Player", "Level", "Pos", "Age", "OPS", "Proj Debut", "⭐"]].assign(Type="Hitter")  if not hitters.empty  else pd.DataFrame(),
        pitchers[["Player", "Level", "Pos", "Age", "ERA", "Proj Debut", "⭐"]].assign(Type="Pitcher") if not pitchers.empty else pd.DataFrame(),
    ], ignore_index=True)

    if not all_players.empty:
        all_players["Proj Debut Year"] = pd.to_numeric(
            all_players["Proj Debut"].replace("Unknown", pd.NA), errors="coerce"
        )
        all_players = all_players.sort_values(["⭐", "Proj Debut Year", "Player"],
                                               ascending=[False, True, True]).reset_index(drop=True)

        cols = [c for c in ["Player", "Type", "Level", "Pos", "Age", "Proj Debut", "⭐"] if c in all_players.columns]
        st.dataframe(all_players[cols], use_container_width=True, hide_index=True,
                     column_config={"⭐": st.column_config.CheckboxColumn(label="Fav")})

        # Debut distribution chart
        by_year = (
            all_players.dropna(subset=["Proj Debut Year"])
            .groupby("Proj Debut Year")
            .size()
            .reset_index(name="Count")
        )
        if not by_year.empty:
            st.bar_chart(by_year.set_index("Proj Debut Year"))
    else:
        st.info("No data available.")

# ── Footer ─────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Data: MLB Stats API (statsapi.mlb.com) · "
    "Refreshed every 15 min · "
    "Active MLB roster excluded · "
    "Projected debut is an estimate, not a scout forecast."
)
