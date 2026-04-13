# Milwaukee Brewers Farm Leaderboard

A Streamlit app showing current Brewers minor-league stats across all affiliate levels — sortable leaderboards, a "Who's Hot" heat index, projected MLB debut estimates, and pinnable favorites.

## What changed from v2 → v3

The original app scraped HTML tables from milb.com using `pd.read_html`. **This broke** because MiLB's stat pages are now JavaScript-rendered; `pd.read_html` returns empty results and every level shows as failed.

The new app uses the **MLB Stats API** (`statsapi.mlb.com`) — the same stable JSON API that powers the MLB app and Fangraphs. It's structured, fast, and doesn't break when MiLB redesigns their pages.

## New features

| Feature | Description |
|---|---|
| **Who's Hot tab** | Heat index ranking recent season-to-date performance |
| **Projected Debut tab** | Composite estimate (level + age + performance) with bar chart |
| **Age column** | Pulled from player birth dates via the Stats API |
| **K/BB** | Computed for pitchers |
| **Position filter** | Filter hitters by position |
| **Favorites pinning** | `⭐` column; favorites always sort to top |
| **Simpler requirements** | No lxml/html5lib/beautifulsoup4 needed |

## Deploy

1. Put `app.py` and `requirements.txt` in a GitHub repo.
2. Deploy on [Streamlit Community Cloud](https://streamlit.io/cloud).
3. Main file path: `app.py`

## How the Projected Debut estimate works

```
base_years  = league-average years from that level to MLB
             (AAA=0.8, AA=1.5, High-A=2.5, Single-A=3.5, ACL/DSL=5.0)
age_factor  = (age − 22) × 0.15   ← older prospects advance faster
perf_bonus  = 0–0.5               ← elite stats accelerate by up to 6 months
years_out   = max(0.3, base − age_factor − perf_bonus)
debut_year  = current_year + round(years_out)
```

This is a **statistical estimate**, not a scouting projection.

## Caveats

- Stats API rate limits: the app caches all calls for 15 minutes.
- ACL/DSL stats may not be available early in the season.
- Active MLB roster is excluded automatically (pulled fresh every 15 min).
