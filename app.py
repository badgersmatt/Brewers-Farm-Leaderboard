"""
Milwaukee Brewers Farm System Leaderboard
==========================================
Uses the MLB Stats API (statsapi.mlb.com) for structured JSON data.
"""

from __future__ import annotations

import math
from datetime import datetime, date

import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Brewers Farm Leaderboard",
    page_icon="🧀",
    layout="wide",
)

# ── Prospect rankings (MLB Pipeline, updated preseason 2026) ──────────────────
# Source: MLB Pipeline Brewers Top 30 + MLB Top 100, April 2026
# Update 2-3x per season as lists refresh.

BREWERS_TOP30: dict[str, int] = {
    "jesús made":        1,  "jesus made":        1,
    "luis peña":         2,  "luis pena":         2,
    "jett williams":     3,
    "cooper pratt":      4,
    "brandon sproat":    5,
    "logan henderson":   6,
    "andrew fischer":    7,
    "jeferson quero":    8,
    "bishop letson":     9,
    "marco dinges":     10,
    "luke adams":       11,
    "josh adamczewski": 12,
    "robert gasser":    13,
    "braylon payne":    14,
    "blake burke":      15,
    "luis lara":        16,
    "brock wilken":     17,
    "tyson hardin":     18,
    "brady ebel":       19,
    "jd thompson":      20,
    "craig yoho":       21,
    "bryce meccage":    22,
    "coleman crow":     23,
    "eric bitonti":     24,
    "ethan dorchies":   25,
    "brett wichrowski": 26,
    "mike boeve":       27,
    "josh knoth":       28,
    "manuel rodriguez": 29,
    "frank cairone":    30,
}

MLB_TOP100: dict[str, int] = {
    "jesús made":      3,  "jesus made":      3,
    "luis peña":      22,  "luis pena":      22,
    "jett williams":  38,
    "cooper pratt":   41,
    "jeferson quero": 61,
    "andrew fischer": 72,
    "logan henderson":78,
    "brandon sproat": 92,
}

PROSPECT_UPDATED = "MLB Pipeline · preseason 2026"


def prospect_badges(name: str) -> str:
    key = name.strip().lower()
    badges = []
    if key in MLB_TOP100:
        badges.append(f"🌟#{MLB_TOP100[key]}")
    if key in BREWERS_TOP30:
        badges.append(f"MIL#{BREWERS_TOP30[key]}")
    return " ".join(badges)


# ── Theme CSS ─────────────────────────────────────────────────────────────────
BREWERS_CSS = """
<style>
/* ── Base ──────────────────────────────────────────────────────────── */
.stApp {
    background: linear-gradient(160deg, #050f24 0%, #0A2351 60%, #0d2a5e 100%);
    min-height: 100vh;
}
[data-testid="stHeader"] {
    background-color: #050f24 !important;
    border-bottom: 1px solid rgba(255,197,47,0.08) !important;
}
[data-testid="stDecoration"] { display: none !important; }
.stAppToolbar { background: transparent !important; }
.stMainBlockContainer { padding-top: 1.25rem !important; max-width: 1440px; }

/* ── Typography ─────────────────────────────────────────────────────── */
h1 {
    background: linear-gradient(90deg, #FFC52F 0%, #ffe08a 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    font-size: 2.4rem !important; font-weight: 900 !important;
    letter-spacing: -1.5px; line-height: 1.1 !important;
}
h2, h3, h4 { color: #FFC52F !important; font-weight: 700 !important; }
p, .stMarkdown p, label, span { color: rgba(255,255,255,0.88) !important; }
.stCaption p { color: rgba(255,255,255,0.42) !important; font-size: 0.75rem !important; }

/* ── Sidebar ────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #040d1f !important;
    border-right: 1px solid rgba(255,197,47,0.1);
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color: #FFC52F !important; }

/* ── Metric Cards ───────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(255,197,47,0.07) 0%, rgba(255,255,255,0.03) 100%);
    border: 1px solid rgba(255,197,47,0.18); border-radius: 14px;
    padding: 0.9rem 1.1rem !important;
    transition: border-color 0.25s, transform 0.25s, box-shadow 0.25s;
}
[data-testid="stMetric"]:hover {
    border-color: rgba(255,197,47,0.45);
    transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.35);
}
[data-testid="stMetricLabel"] {
    color: rgba(255,255,255,0.45) !important; font-size: 0.68rem !important;
    font-weight: 700 !important; text-transform: uppercase; letter-spacing: 0.1em;
}
[data-testid="stMetricValue"] {
    color: #FFC52F !important; font-weight: 800 !important;
    font-size: 1.9rem !important; line-height: 1.1 !important;
}

/* ── Tabs ───────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.04); border: 1px solid rgba(255,197,47,0.1);
    border-radius: 12px; gap: 3px; padding: 4px; margin-bottom: 0.75rem;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px; color: rgba(255,255,255,0.5) !important;
    font-weight: 600; font-size: 0.84rem; padding: 0.4rem 1rem;
    background: transparent !important; transition: all 0.2s;
}
.stTabs [data-baseweb="tab"]:hover { color: rgba(255,255,255,0.85) !important; background: rgba(255,255,255,0.06) !important; }
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #FFC52F 0%, #ffd966 100%) !important;
    color: #0A2351 !important; font-weight: 800 !important;
    box-shadow: 0 3px 10px rgba(255,197,47,0.35);
}

/* ── Buttons ────────────────────────────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #FFC52F, #e6b000) !important;
    color: #0A2351 !important; border: none !important; font-weight: 700 !important;
    border-radius: 8px !important; padding: 0.35rem 1rem !important;
    font-size: 0.82rem !important; transition: all 0.2s !important;
}
.stButton > button:hover { transform: translateY(-1px) !important; box-shadow: 0 5px 14px rgba(255,197,47,0.4) !important; }

/* ── Inputs ─────────────────────────────────────────────────────────── */
[data-baseweb="select"] > div:first-child {
    background-color: rgba(5,20,55,0.85) !important;
    border: 1px solid rgba(255,197,47,0.22) !important; border-radius: 8px !important;
}
[data-baseweb="select"] > div:first-child:hover { border-color: rgba(255,197,47,0.5) !important; }
[data-baseweb="select"] span, [data-baseweb="select"] div { color: rgba(255,255,255,0.9) !important; }
[data-baseweb="select"] svg { fill: rgba(255,197,47,0.6) !important; }
[data-baseweb="select"] input { color: white !important; background: transparent !important; }

[data-baseweb="tag"] { background: linear-gradient(135deg,#FFC52F,#e6b000) !important; border-radius: 5px !important; border: none !important; }
[data-baseweb="tag"] span { color: #0A2351 !important; font-weight: 700 !important; }
[data-baseweb="tag"] svg, [data-baseweb="tag"] button svg { fill: #0A2351 !important; }

/* Dropdowns */
[data-baseweb="popover"] {
    background-color: #0b1e4a !important; border: 1px solid rgba(255,197,47,0.2) !important;
    border-radius: 10px !important; box-shadow: 0 12px 40px rgba(0,0,0,0.6) !important; overflow: hidden !important;
}
[data-baseweb="popover"] > div, [data-baseweb="menu"], [data-baseweb="list"] { background-color: #0b1e4a !important; }
[data-baseweb="menu"] ul, [data-baseweb="list"] ul { background-color: #0b1e4a !important; }
[role="option"] {
    background-color: #0b1e4a !important; color: rgba(255,255,255,0.88) !important;
    font-size: 0.85rem !important;
}
[role="option"]:hover { background-color: rgba(255,197,47,0.14) !important; color: white !important; }
[aria-selected="true"][role="option"] { background-color: rgba(255,197,47,0.2) !important; color: #FFC52F !important; font-weight: 600 !important; }
[data-baseweb="popover"] span, [data-baseweb="popover"] p { color: rgba(255,255,255,0.88) !important; }

[data-testid="stTextInput"] input {
    background-color: rgba(5,20,55,0.85) !important; border: 1px solid rgba(255,197,47,0.22) !important;
    border-radius: 8px !important; color: white !important;
}

/* ── Slider ─────────────────────────────────────────────────────────── */
[data-testid="stSlider"] [role="slider"] { background-color: #FFC52F !important; border-color: #FFC52F !important; }

/* ── Checkbox ───────────────────────────────────────────────────────── */
[data-testid="stCheckbox"] label p { color: rgba(255,255,255,0.85) !important; }

/* ── Element toolbar (hide CSV download) ────────────────────────────── */
[data-testid="stElementToolbar"] { display: none !important; }

/* ── Dataframes ─────────────────────────────────────────────────────── */
[data-testid="stDataFrameResizable"] {
    border: 1px solid rgba(255,197,47,0.14) !important; border-radius: 12px !important;
    overflow: hidden !important; box-shadow: 0 4px 20px rgba(0,0,0,0.25);
}
.stSelectbox label { color: rgba(255,255,255,0.7) !important; }
.stSelectbox [data-baseweb="select"] span { color: white !important; font-weight: 500 !important; }

/* ── Expanders ──────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: rgba(255,255,255,0.025) !important;
    border: 1px solid rgba(255,197,47,0.18) !important; border-radius: 12px !important;
    overflow: hidden; margin-top: 0.5rem;
}
details > summary { color: #FFC52F !important; font-weight: 700 !important; padding: 0.6rem 1rem; }
details > summary:hover { background: rgba(255,197,47,0.06) !important; }
details[open] > summary { border-bottom: 1px solid rgba(255,197,47,0.1); }

/* ── Alerts ─────────────────────────────────────────────────────────── */
[data-testid="stAlert"] { border-radius: 10px !important; border-left-width: 4px !important; }

/* ── Misc ───────────────────────────────────────────────────────────── */
hr { border-color: rgba(255,197,47,0.1) !important; margin: 1.25rem 0 !important; }
[data-testid="stSpinner"] > div { border-top-color: #FFC52F !important; }
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: rgba(255,255,255,0.03); }
::-webkit-scrollbar-thumb { background: rgba(255,197,47,0.25); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,197,47,0.45); }

/* ── Prospect badge pills ───────────────────────────────────────────── */
.badge-mlb  { background:#FFC52F; color:#0A2351; font-weight:800; font-size:0.7rem; padding:1px 6px; border-radius:4px; margin-right:4px; }
.badge-mil  { background:rgba(255,197,47,0.18); color:#FFC52F; font-weight:700; font-size:0.7rem; padding:1px 6px; border-radius:4px; border:1px solid rgba(255,197,47,0.35); margin-right:4px; }
</style>
"""

# ── Constants ─────────────────────────────────────────────────────────────────
BREWERS_ORG_ID = 158
CURRENT_YEAR   = datetime.now().year
BASE    = "https://statsapi.mlb.com/api/v1"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "BrewersFarmLeaderboard/5.0"})

LEVEL_YEARS_TO_MLB = {"AAA": 0.8, "AA": 1.5, "High-A": 2.5, "Single-A": 3.5, "ACL/DSL": 5.0}
LEVEL_KEY_TO_SPORT_ID = {"AAA": 11, "AA": 12, "High-A": 13, "Single-A": 14, "ACL/DSL": 16}

HITTING_DISPLAY  = ["Prospect", "Player", "Level", "Pos", "Age", "G", "AB", "AVG", "OBP", "SLG", "OPS", "HR", "RBI", "SB", "BB", "SO", "Debut"]
PITCHING_DISPLAY = ["Prospect", "Player", "Level", "Pos", "Age", "G", "GS", "IP", "ERA", "WHIP", "SO", "BB", "K/BB", "SV", "HLD", "W", "L", "Debut"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def safe_get(url: str, params: dict | None = None) -> dict:
    resp = SESSION.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def age_from_dob(dob_str: str | None) -> int | None:
    if not dob_str:
        return None
    try:
        dob   = datetime.strptime(dob_str[:10], "%Y-%m-%d").date()
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception:
        return None


def projected_debut(level_key: str, age: int | None, perf_score: float) -> str:
    if age is None:
        return "—"
    base  = LEVEL_YEARS_TO_MLB.get(level_key, 3.0)
    years = max(0.3, base - (age - 22) * 0.15 - perf_score)
    return str(CURRENT_YEAR + round(years))


def hitter_perf_score(row: pd.Series) -> float:
    ops = row.get("OPS", 0) or 0
    hr  = row.get("HR",  0) or 0
    ab  = row.get("AB",  1) or 1
    sb  = row.get("SB",  0) or 0
    s   = 0.0
    if   ops >= 1.000: s += 0.25
    elif ops >= 0.900: s += 0.20
    elif ops >= 0.800: s += 0.10
    hr_rate = hr / ab
    if   hr_rate >= 0.05: s += 0.15
    elif hr_rate >= 0.03: s += 0.08
    if   sb >= 15: s += 0.10
    elif sb >= 8:  s += 0.05
    return min(s, 0.5)


def pitcher_perf_score(row: pd.Series) -> float:
    era  = row.get("ERA",  99) or 99
    whip = row.get("WHIP", 99) or 99
    kbb  = row.get("K/BB",  0) or 0
    s    = 0.0
    if   era <= 2.00: s += 0.20
    elif era <= 3.00: s += 0.15
    elif era <= 4.00: s += 0.08
    if   whip <= 1.00: s += 0.15
    elif whip <= 1.20: s += 0.08
    if   kbb >= 4.0: s += 0.15
    elif kbb >= 2.5: s += 0.08
    return min(s, 0.5)


def level_key_from_sport(sport_id: int) -> str:
    return {11: "AAA", 12: "AA", 13: "High-A", 14: "Single-A", 16: "ACL/DSL"}.get(sport_id, "?")


def last_name_key(full_name: str) -> str:
    parts = full_name.strip().split()
    return parts[-1].lower() if parts else full_name.lower()


def valid_pid(pid) -> bool:
    if pid is None:
        return False
    try:
        return not pd.isna(pid)
    except (TypeError, ValueError):
        return True


def make_prospect_col(names: pd.Series) -> pd.Series:
    """Return a badge string like '🌟#3 MIL#1' for each player name."""
    return names.apply(prospect_badges)


# ── MLB Stats API ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=900, show_spinner=False)
def fetch_affiliates() -> list[dict]:
    data = safe_get(f"{BASE}/teams", params={"sportIds": "11,12,13,14,16", "season": CURRENT_YEAR})
    out  = []
    for team in data.get("teams", []):
        if team.get("parentOrgId") == BREWERS_ORG_ID and team.get("id") != BREWERS_ORG_ID:
            sport_id = team.get("sport", {}).get("id")
            lk = level_key_from_sport(sport_id)
            out.append({
                "id": team["id"], "name": team["name"],
                "sport_id": sport_id, "level_key": lk,
                "level_name": f"{lk} {team['name']}",
            })
    return out


@st.cache_data(ttl=900, show_spinner=False)
def fetch_mlb_active_roster() -> set[str]:
    try:
        data = safe_get(f"{BASE}/teams/{BREWERS_ORG_ID}/roster", params={"rosterType": "active"})
        return {p["person"]["fullName"].strip().lower()
                for p in data.get("roster", []) if p.get("person", {}).get("fullName")}
    except Exception:
        return set()


@st.cache_data(ttl=900, show_spinner=False)
def fetch_game_log(player_id: int, group: str, sport_id: int) -> pd.DataFrame:
    try:
        data   = safe_get(f"{BASE}/people/{player_id}/stats", params={
            "stats": "gameLog", "group": group, "season": CURRENT_YEAR, "sportId": sport_id,
        })
        splits = []
        for obj in data.get("stats", []):
            splits.extend(obj.get("splits", []))
        rows = []
        for split in splits:
            s        = split.get("stat", {})
            opp      = split.get("opponent", {})
            opp_name = opp.get("abbreviation") or opp.get("name", "")
            loc      = "vs" if split.get("isHome") else "@"
            if group == "hitting":
                rows.append({
                    "Date": split.get("date", ""),
                    "Opp":  f"{loc} {opp_name}",
                    "AB":   int(s.get("atBats",     0) or 0),
                    "R":    int(s.get("runs",        0) or 0),
                    "H":    int(s.get("hits",        0) or 0),
                    "2B":   int(s.get("doubles",     0) or 0),
                    "3B":   int(s.get("triples",     0) or 0),
                    "HR":   int(s.get("homeRuns",    0) or 0),
                    "RBI":  int(s.get("rbi",         0) or 0),
                    "BB":   int(s.get("baseOnBalls", 0) or 0),
                    "SO":   int(s.get("strikeOuts",  0) or 0),
                    "SB":   int(s.get("stolenBases", 0) or 0),
                    "AVG":  round(float(s.get("avg", 0) or 0), 3),
                })
            else:
                dec = ("W" if int(s.get("wins",   0) or 0) else
                       "L" if int(s.get("losses", 0) or 0) else
                       "SV" if int(s.get("saves", 0) or 0) else
                       "HLD" if int(s.get("holds",0) or 0) else "")
                rows.append({
                    "Date": split.get("date", ""),
                    "Opp":  f"{loc} {opp_name}",
                    "Dec":  dec,
                    "IP":   round(float(s.get("inningsPitched", 0) or 0), 1),
                    "H":    int(s.get("hits",        0) or 0),
                    "R":    int(s.get("runs",         0) or 0),
                    "ER":   int(s.get("earnedRuns",   0) or 0),
                    "BB":   int(s.get("baseOnBalls",  0) or 0),
                    "SO":   int(s.get("strikeOuts",   0) or 0),
                    "HR":   int(s.get("homeRuns",     0) or 0),
                    "ERA":  round(float(s.get("era",  0) or 0), 2),
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
            "stats": "season", "group": "hitting", "season": CURRENT_YEAR,
            "teamId": team_id, "sportId": sport_id, "playerPool": "All", "hydrate": "person",
        })
        rows = []
        for split in data.get("stats", [{}])[0].get("splits", []):
            p   = split.get("player", {})
            s   = split.get("stat",   {})
            dob = p.get("birthDate") or p.get("person", {}).get("birthDate")
            rows.append({
                "Player":    p.get("fullName", ""),
                "player_id": p.get("id"),
                "Pos":       split.get("position", {}).get("abbreviation", ""),
                "Age":       age_from_dob(dob),
                "G":         int(s.get("gamesPlayed",  0) or 0),
                "AB":        int(s.get("atBats",       0) or 0),
                "AVG":       round(float(s.get("avg",  0) or 0), 3),
                "OBP":       round(float(s.get("obp",  0) or 0), 3),
                "SLG":       round(float(s.get("slg",  0) or 0), 3),
                "OPS":       round(float(s.get("ops",  0) or 0), 3),
                "HR":        int(s.get("homeRuns",     0) or 0),
                "RBI":       int(s.get("rbi",          0) or 0),
                "SB":        int(s.get("stolenBases",  0) or 0),
                "BB":        int(s.get("baseOnBalls",  0) or 0),
                "SO":        int(s.get("strikeOuts",   0) or 0),
                "Level":     level_name,
                "level_key": level_key,
            })
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        df["Debut"] = df.apply(lambda r: projected_debut(r["level_key"], r["Age"], hitter_perf_score(r)), axis=1)
        df["Prospect"] = make_prospect_col(df["Player"])
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def fetch_team_pitching(team_id: int, sport_id: int, level_key: str, level_name: str) -> pd.DataFrame:
    try:
        data = safe_get(f"{BASE}/stats", params={
            "stats": "season", "group": "pitching", "season": CURRENT_YEAR,
            "teamId": team_id, "sportId": sport_id, "playerPool": "All", "hydrate": "person",
        })
        rows = []
        for split in data.get("stats", [{}])[0].get("splits", []):
            p   = split.get("player", {})
            s   = split.get("stat",   {})
            dob = p.get("birthDate") or p.get("person", {}).get("birthDate")
            so  = int(s.get("strikeOuts",  0) or 0)
            bb  = int(s.get("baseOnBalls", 0) or 0)
            rows.append({
                "Player":    p.get("fullName", ""),
                "player_id": p.get("id"),
                "Pos":       split.get("position", {}).get("abbreviation", "P"),
                "Age":       age_from_dob(dob),
                "G":         int(s.get("gamesPitched",    0) or 0),
                "GS":        int(s.get("gamesStarted",    0) or 0),
                "IP":        round(float(s.get("inningsPitched", 0) or 0), 1),
                "ERA":       round(float(s.get("era",     0) or 0), 2),
                "WHIP":      round(float(s.get("whip",    0) or 0), 2),
                "SO":        so,
                "BB":        bb,
                "K/BB":      round(so / bb, 2) if bb > 0 else None,
                "SV":        int(s.get("saves",   0) or 0),
                "HLD":       int(s.get("holds",   0) or 0),
                "W":         int(s.get("wins",    0) or 0),
                "L":         int(s.get("losses",  0) or 0),
                "Level":     level_name,
                "level_key": level_key,
            })
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        df["Debut"] = df.apply(lambda r: projected_debut(r["level_key"], r["Age"], pitcher_perf_score(r)), axis=1)
        df["Prospect"] = make_prospect_col(df["Player"])
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def load_all_data() -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str]]:
    affiliates = fetch_affiliates()
    mlb_active = fetch_mlb_active_roster()
    hf, pf, loaded, failed = [], [], [], []
    for aff in affiliates:
        hit = fetch_team_hitting( aff["id"], aff["sport_id"], aff["level_key"], aff["level_name"])
        pit = fetch_team_pitching(aff["id"], aff["sport_id"], aff["level_key"], aff["level_name"])
        if hit.empty and pit.empty:
            failed.append(aff["level_name"])
        else:
            loaded.append(aff["level_name"])
            if not hit.empty: hf.append(hit)
            if not pit.empty: pf.append(pit)
    hitters  = pd.concat(hf, ignore_index=True) if hf else pd.DataFrame()
    pitchers = pd.concat(pf, ignore_index=True) if pf else pd.DataFrame()
    if not hitters.empty:
        hitters  = hitters[ ~hitters["Player"].str.lower().isin(mlb_active)].copy()
    if not pitchers.empty:
        pitchers = pitchers[~pitchers["Player"].str.lower().isin(mlb_active)].copy()
    return hitters, pitchers, loaded, failed


def hot_hitters(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    if df.empty: return df
    d = df[df["G"] >= 5].copy()
    d["Heat"] = d.apply(lambda r: (r["OPS"] or 0) * math.log1p(r["G"]) - 0.003 * (r["SO"] or 0), axis=1)
    return d.sort_values("Heat", ascending=False).head(top_n)


def hot_pitchers(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    if df.empty: return df
    d = df[(df["G"] >= 3) & (df["IP"] >= 5)].copy()
    d["Heat"] = d.apply(lambda r: (
        -(r["ERA"]  or 9.0) * 0.40 - (r["WHIP"] or 2.0) * 2.00
        + (r["K/BB"] or 0) * 0.30  + math.log1p(r["SO"] or 0) * 0.20
    ), axis=1)
    return d.sort_values("Heat", ascending=False).head(top_n)


def render_game_log(pid, pname: str, group: str, sport_id: int) -> None:
    if not valid_pid(pid):
        st.warning("Player ID unavailable.")
        return
    with st.expander(f"📊 {pname} — {CURRENT_YEAR} Game Log", expanded=True):
        with st.spinner("Loading…"):
            log = fetch_game_log(int(pid), group, sport_id)
        if log.empty:
            st.info("No game log available yet.")
            return
        if group == "hitting":
            ab, h = log["AB"].sum(), log["H"].sum()
            avg   = f"{h/ab:.3f}" if ab > 0 else ".000"
            c1,c2,c3,c4,c5 = st.columns(5)
            c1.metric("G",   len(log)); c2.metric("AVG", avg)
            c3.metric("HR",  log["HR"].sum()); c4.metric("RBI", log["RBI"].sum())
            c5.metric("SB",  log["SB"].sum())
            st.dataframe(log, use_container_width=True, hide_index=True,
                         column_config={"AVG": st.column_config.NumberColumn(format="%.3f")})
            cd = log[["Date","H"]].set_index("Date").sort_index()
            if len(cd) > 1:
                st.caption("Hits per game (chronological)")
                st.bar_chart(cd, color="#FFC52F", height=150)
        else:
            c1,c2,c3,c4,c5 = st.columns(5)
            c1.metric("Apps", len(log)); c2.metric("IP", f"{log['IP'].sum():.1f}")
            c3.metric("ERA",  f"{log['ERA'].iloc[0]:.2f}" if len(log) else "—")
            c4.metric("SO",   log["SO"].sum()); c5.metric("BB", log["BB"].sum())
            st.dataframe(log, use_container_width=True, hide_index=True,
                         column_config={
                             "IP":  st.column_config.NumberColumn(format="%.1f"),
                             "ERA": st.column_config.NumberColumn(format="%.2f"),
                         })
            cd = log[["Date","SO"]].set_index("Date").sort_index()
            if len(cd) > 1:
                st.caption("Strikeouts per appearance (chronological)")
                st.bar_chart(cd, color="#FFC52F", height=150)


# ══════════════════════════════════════════════════════════════════════════════
# Session state
# ══════════════════════════════════════════════════════════════════════════════
for key in ("sel_hitter", "sel_pitcher"):
    if key not in st.session_state:
        st.session_state[key] = None


def last_name_sort(df: pd.DataFrame, stat_col: str | None, ascending: bool = False) -> pd.DataFrame:
    df = df.copy()
    df["_last"] = df["Player"].apply(last_name_key)
    if stat_col:
        df = df.sort_values([stat_col, "_last"], ascending=[ascending, True])
    else:
        df = df.sort_values(["_last", "Player"], ascending=[True, True])
    return df.drop(columns=["_last"]).reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(BREWERS_CSS, unsafe_allow_html=True)

st.markdown(f"""
<div style="display:flex;align-items:center;gap:1rem;margin-bottom:0.5rem">
  <span style="font-size:2.6rem;line-height:1">🧀</span>
  <div>
    <div style="font-size:0.68rem;font-weight:700;letter-spacing:0.18em;
                color:rgba(255,197,47,0.55);text-transform:uppercase">Milwaukee Brewers</div>
    <h1 style="margin:0;padding:0">Farm System Leaderboard</h1>
  </div>
</div>
<div style="color:rgba(255,255,255,0.35);font-size:0.72rem;margin-bottom:0.5rem">
  🌟 = MLB top-100 rank &nbsp;·&nbsp; MIL# = Brewers org rank &nbsp;·&nbsp; {PROSPECT_UPDATED}
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center;padding:0.75rem 0 0.25rem">
      <div style="font-size:2.2rem">🧀</div>
      <div style="color:#FFC52F;font-weight:800;font-size:0.95rem">Brewers Farm Tracker</div>
      <div style="color:rgba(255,255,255,0.3);font-size:0.68rem;margin-top:2px">{CURRENT_YEAR} season · live data</div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()
    st.markdown("**🔍 Filters**")
    min_games_h = st.slider("Min hitter games", 0, 60, 0)
    min_games_p = st.slider("Min pitcher apps", 0, 30, 0)
    st.divider()
    st.caption("Data via MLB Stats API · 15-min cache\nActive MLB roster excluded automatically")

# ── Load ──────────────────────────────────────────────────────────────────────
with st.spinner("Loading Brewers affiliate stats…"):
    hitters, pitchers, loaded_levels, failed_levels = load_all_data()

# ── Level filter ──────────────────────────────────────────────────────────────
all_levels = sorted(set(
    list(hitters["Level"].unique()  if not hitters.empty  else []) +
    list(pitchers["Level"].unique() if not pitchers.empty else [])
))
selected_levels = st.multiselect("Levels to include", all_levels, default=all_levels)


def apply_filters(df: pd.DataFrame, min_g: int) -> pd.DataFrame:
    if df.empty: return df
    df = df[df["Level"].isin(selected_levels)].copy()
    return df[df["G"].fillna(0) >= min_g].copy()


hitters  = apply_filters(hitters,  min_games_h)
pitchers = apply_filters(pitchers, min_games_p)

# ── Metrics ───────────────────────────────────────────────────────────────────
st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Hitters",         0 if hitters.empty  else len(hitters))
c2.metric("Pitchers",        0 if pitchers.empty else len(pitchers))
c3.metric("Active affiliates", len(loaded_levels))
if failed_levels:
    acl_only = all("ACL" in l or "DSL" in l for l in failed_levels)
    c4.metric("Pending levels", len(failed_levels))
    if acl_only:
        st.info("**ACL & DSL** rookie leagues open June–July. Data will appear automatically.")
    else:
        st.warning("No data for: " + ", ".join(failed_levels))

if hitters.empty and pitchers.empty:
    st.error("No affiliate stats returned. The MLB Stats API may be unavailable.")
    st.stop()

# ── Column configs ────────────────────────────────────────────────────────────
_s = "small"
HIT_CFG = {
    "Prospect": st.column_config.TextColumn("Prospect", width=_s),
    "Player":   st.column_config.TextColumn(width="medium"),
    "Level":    st.column_config.TextColumn(width="medium"),
    "Pos":      st.column_config.TextColumn("Pos", width=_s),
    "Age":      st.column_config.NumberColumn("Age", width=_s),
    "G":        st.column_config.NumberColumn("G",   width=_s),
    "AB":       st.column_config.NumberColumn("AB",  width=_s),
    "HR":       st.column_config.NumberColumn("HR",  width=_s),
    "RBI":      st.column_config.NumberColumn("RBI", width=_s),
    "SB":       st.column_config.NumberColumn("SB",  width=_s),
    "BB":       st.column_config.NumberColumn("BB",  width=_s),
    "SO":       st.column_config.NumberColumn("SO",  width=_s),
    "AVG":      st.column_config.NumberColumn("AVG", format="%.3f", width=_s),
    "OBP":      st.column_config.NumberColumn("OBP", format="%.3f", width=_s),
    "SLG":      st.column_config.NumberColumn("SLG", format="%.3f", width=_s),
    "OPS":      st.column_config.ProgressColumn("OPS", format="%.3f", min_value=0, max_value=1.2),
    "Debut":    st.column_config.TextColumn("Debut", width=_s),
}
PIT_CFG = {
    "Prospect": st.column_config.TextColumn("Prospect", width=_s),
    "Player":   st.column_config.TextColumn(width="medium"),
    "Level":    st.column_config.TextColumn(width="medium"),
    "Pos":      st.column_config.TextColumn("Pos",  width=_s),
    "Age":      st.column_config.NumberColumn("Age", width=_s),
    "G":        st.column_config.NumberColumn("G",   width=_s),
    "GS":       st.column_config.NumberColumn("GS",  width=_s),
    "W":        st.column_config.NumberColumn("W",   width=_s),
    "L":        st.column_config.NumberColumn("L",   width=_s),
    "SV":       st.column_config.NumberColumn("SV",  width=_s),
    "HLD":      st.column_config.NumberColumn("HLD", width=_s),
    "SO":       st.column_config.NumberColumn("SO",  width=_s),
    "BB":       st.column_config.NumberColumn("BB",  width=_s),
    "IP":       st.column_config.NumberColumn("IP",  format="%.1f", width=_s),
    "ERA":      st.column_config.NumberColumn("ERA", format="%.2f", width=_s),
    "WHIP":     st.column_config.NumberColumn("WHIP",format="%.2f", width=_s),
    "K/BB":     st.column_config.NumberColumn("K/BB",format="%.2f", width=_s),
    "Debut":    st.column_config.TextColumn("Debut", width=_s),
}

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_h, tab_p, tab_hot, tab_debut = st.tabs(
    ["🏏  Hitters", "⚾  Pitchers", "🔥  Who's Hot", "📅  Proj. Debuts"]
)

# ══════════════════════════════════════════════════════════════════════════════
# Hitters tab
# ══════════════════════════════════════════════════════════════════════════════
with tab_h:
    c1, c2, c3 = st.columns([2, 2, 3])
    sort_h   = c1.selectbox("Sort by", ["OPS","HR","RBI","AVG","OBP","SLG","SB","BB","SO","Name"], key="sort_h")
    pos_opts = sorted(hitters["Pos"].dropna().unique()) if not hitters.empty else []
    pos_filt = c2.multiselect("Position", pos_opts, key="pos_h")
    search_h = c3.text_input("🔎 Search", key="search_h", placeholder="player name…")

    view = hitters.copy()
    if pos_filt:
        view = view[view["Pos"].isin(pos_filt)]
    if search_h:
        view = view[view["Player"].str.contains(search_h, case=False, na=False)]

    if not view.empty:
        stat_col = None if sort_h == "Name" else sort_h
        view = last_name_sort(view, stat_col, ascending=False)
        cols = [c for c in HITTING_DISPLAY if c in view.columns]

        st.caption("Click any row to load that player's game-by-game log.")
        ev = st.dataframe(
            view[cols], use_container_width=True, hide_index=True,
            column_config=HIT_CFG, on_select="rerun", selection_mode="single-row",
            key="hitter_table",
        )
        sel = ev.selection.rows
        if sel:
            row = view.iloc[sel[0]]
            st.session_state.sel_hitter = {
                "player_id": row.get("player_id"), "name": row["Player"],
                "sport_id":  LEVEL_KEY_TO_SPORT_ID.get(row.get("level_key", ""), 1),
            }
        if st.session_state.sel_hitter:
            info = st.session_state.sel_hitter
            render_game_log(info["player_id"], info["name"], "hitting", info["sport_id"])
    else:
        st.info("No hitters match the current filters.")

# ══════════════════════════════════════════════════════════════════════════════
# Pitchers tab
# ══════════════════════════════════════════════════════════════════════════════
with tab_p:
    c1, c2 = st.columns([2, 3])
    sort_p   = c1.selectbox("Sort by", ["ERA","WHIP","SO","K/BB","SV","IP","W","Name"], key="sort_p")
    search_p = c2.text_input("🔎 Search", key="search_p", placeholder="player name…")
    asc_p    = sort_p in {"ERA", "WHIP"}

    view = pitchers.copy()
    if search_p:
        view = view[view["Player"].str.contains(search_p, case=False, na=False)]

    if not view.empty:
        stat_col = None if sort_p == "Name" else sort_p
        view = last_name_sort(view, stat_col, ascending=asc_p)
        cols = [c for c in PITCHING_DISPLAY if c in view.columns]

        st.caption("Click any row to load that player's game-by-game log.")
        ev = st.dataframe(
            view[cols], use_container_width=True, hide_index=True,
            column_config=PIT_CFG, on_select="rerun", selection_mode="single-row",
            key="pitcher_table",
        )
        sel = ev.selection.rows
        if sel:
            row = view.iloc[sel[0]]
            st.session_state.sel_pitcher = {
                "player_id": row.get("player_id"), "name": row["Player"],
                "sport_id":  LEVEL_KEY_TO_SPORT_ID.get(row.get("level_key", ""), 1),
            }
        if st.session_state.sel_pitcher:
            info = st.session_state.sel_pitcher
            render_game_log(info["player_id"], info["name"], "pitching", info["sport_id"])
    else:
        st.info("No pitchers match the current filters.")

# ══════════════════════════════════════════════════════════════════════════════
# Who's Hot tab
# ══════════════════════════════════════════════════════════════════════════════
with tab_hot:
    st.info(
        "**Heat Index** ranks by season-to-date stats (API returns cumulative totals only, not rolling splits).  "
        "**Hitters:** `OPS × log(G+1) − 0.003×SO` — rewards on-base + power, weights for sample size, penalises Ks.  "
        "**Pitchers:** `−ERA×0.4 − WHIP×2 + K/BB×0.3 + log(SO+1)×0.2` — lower ERA/WHIP and higher K rate score higher.  "
        "Minimums: 5 G (hitters) · 3 G + 5 IP (pitchers).",
        icon="ℹ️",
    )
    hh = hot_hitters(hitters)
    hp = hot_pitchers(pitchers)
    ch, cp = st.columns(2)
    with ch:
        st.markdown("#### 🔥 Hottest Hitters")
        if not hh.empty:
            dc = [c for c in ["Prospect","Player","Level","Pos","G","OPS","HR","RBI","SB"] if c in hh.columns]
            st.dataframe(hh[dc].reset_index(drop=True), use_container_width=True, hide_index=True,
                         column_config={"OPS": st.column_config.ProgressColumn("OPS", format="%.3f", min_value=0, max_value=1.2)})
        else:
            st.info("Not enough games played yet.")
    with cp:
        st.markdown("#### 🔥 Hottest Pitchers")
        if not hp.empty:
            dc = [c for c in ["Prospect","Player","Level","Pos","G","ERA","WHIP","SO","K/BB"] if c in hp.columns]
            st.dataframe(hp[dc].reset_index(drop=True), use_container_width=True, hide_index=True,
                         column_config={
                             "ERA":  st.column_config.NumberColumn(format="%.2f"),
                             "WHIP": st.column_config.NumberColumn(format="%.2f"),
                             "K/BB": st.column_config.NumberColumn(format="%.2f"),
                         })
        else:
            st.info("Not enough games played yet.")

# ══════════════════════════════════════════════════════════════════════════════
# Projected Debuts tab
# ══════════════════════════════════════════════════════════════════════════════
with tab_debut:
    st.caption(
        "Estimates from current level, age, and performance — not a scout forecast. "
        "Level baseline adjusted for age (older = faster) and elite stats (up to +6 months)."
    )
    frames = []
    if not hitters.empty:
        frames.append(hitters[["Prospect","Player","Level","Pos","Age","OPS","Debut"]].assign(Type="Hitter"))
    if not pitchers.empty:
        frames.append(pitchers[["Prospect","Player","Level","Pos","Age","ERA","Debut"]].assign(Type="Pitcher"))

    if frames:
        ap = pd.concat(frames, ignore_index=True)
        ap["Debut Year"] = pd.to_numeric(ap["Debut"].replace("—", pd.NA), errors="coerce")
        ap = ap.sort_values(["Debut Year", "Player"], ascending=[True, True]).reset_index(drop=True)
        cols = [c for c in ["Prospect","Player","Type","Level","Pos","Age","Debut"] if c in ap.columns]
        st.dataframe(ap[cols], use_container_width=True, hide_index=True)

        by_year = ap.dropna(subset=["Debut Year"]).groupby("Debut Year").size().reset_index(name="Prospects")
        if not by_year.empty:
            st.markdown("#### Pipeline by Projected Debut Year")
            st.bar_chart(by_year.set_index("Debut Year"), color="#FFC52F", height=200)
    else:
        st.info("No data available.")

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    f"Milwaukee Brewers Farm System Leaderboard · {CURRENT_YEAR} · "
    "Data: MLB Stats API · Refreshed every 15 min · Active MLB roster excluded · "
    f"Prospect rankings: {PROSPECT_UPDATED}"
)
