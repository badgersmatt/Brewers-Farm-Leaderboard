# Brewers Farm Leaderboard

A simple Streamlit app that puts Milwaukee Brewers minor leaguers in one sortable place.

## What it does

- Pulls official stats pages for Brewers affiliates
- Combines hitters and pitchers into one board
- Lets you keep a favorites list in the sidebar
- Filters by level
- Sorts by the stats you care about most
- Refreshes whenever the app reloads

## Levels included

- Triple-A: Nashville Sounds
- Double-A: Biloxi Shuckers
- High-A: Wisconsin Timber Rattlers
- Single-A: Wilson Warbirds
- Rookie: ACL Brewers
- Rookie: DSL Brewers Blue
- Rookie: DSL Brewers Gold

## Run it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy it free on Streamlit Community Cloud

1. Put these files in a GitHub repo.
2. Go to Streamlit Community Cloud.
3. Create a new app from that repo.
4. Set `app.py` as the main file.
5. Launch.

Then you will have one URL you can bookmark and check whenever you want.

## Notes

- The app uses official Brewers and MiLB pages as the source.
- The pages are cached for 30 minutes inside Streamlit so repeated refreshes are faster.
- If MiLB changes a page layout or a URL slug, the scraper may need a small tweak.
- The Rookie-level team URLs are the most likely pieces to need occasional maintenance.
