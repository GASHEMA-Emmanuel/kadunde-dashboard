# Kadunde Super League – Live FPL Dashboard

A live dashboard for the Kadunde Super League (FPL league 68704), built with Streamlit.
It reads everything straight from the official Fantasy Premier League API, so it never needs manual updates.

**Features:** live gameweek scores (provisional bonus + auto-subs, like LiveFPL), live standings with movement
arrows, gameweek winners (highest points before hits, ties share the prize), prize money board, form heatmap,
Kwikatisha (transfer hits), best chips usage, manager spotlight, next-deadline countdown.
The page refreshes itself every 2 minutes.

## Files
| File | What it is |
|---|---|
| `app.py` | The dashboard |
| `fpl.py` | Gets data from FPL and works out live points |
| `settings.py` | **The only file you edit**: nicknames, prize amounts, paid gameweeks |
| `requirements.txt` | Python packages Streamlit Cloud installs |
| `.streamlit/config.toml` | Dark theme |
| `google_sheets_version/` | The Google Sheets script + HTML (not used by Streamlit, kept for reference) |

## Deploy on Streamlit Community Cloud (free)
1. Create a free account on **github.com**.
2. Click **+ → New repository**, name it `kadunde-dashboard`, choose **Public**, tick **Add a README**, click **Create**.
3. Click **Add file → Upload files** and drag in `app.py`, `fpl.py`, `settings.py`, `requirements.txt`. Commit.
4. Click **Add file → Create new file**, type the name `.streamlit/config.toml`, paste the contents of that file, commit.
5. Go to **share.streamlit.io**, sign in with GitHub, click **Create app → Deploy a public app from GitHub**.
6. Repository: `your-name/kadunde-dashboard`, Branch: `main`, Main file path: `app.py`. Optionally choose a custom URL
   such as `kadunde`. Click **Deploy**.
7. After 1–2 minutes you get a link like `https://kadunde.streamlit.app` – share it in the group.

## Everyday changes (edit `settings.py` on GitHub, the app updates within a minute)
- **Mark a gameweek prize as paid:** `PAID_GAMEWEEKS = [1, 2, 3]`
- **Change a nickname:** edit the name next to the FPL team ID in `NICKNAMES`
- **Change prize amounts:** `GW_PRIZE`, `CLASSIC_PRIZES`, `POT_TOTAL`

## Run on your own computer (optional)
```
pip install -r requirements.txt
streamlit run app.py
```
