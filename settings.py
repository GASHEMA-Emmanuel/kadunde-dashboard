"""
Kadunde Super League - settings.
This is the only file you normally need to edit (you can do it directly on GitHub).
"""

LEAGUE_ID = 68704                 # FPL classic league ID
LEAGUE_NAME = "Kadunde Super League"
SEASON = "2026/27"

# FPL team ID -> nickname shown on the dashboard
NICKNAMES = {
    5420458: "Landry",      # Landry Sugira
    336495: "Arsene",      # Arsene Zimana
    5143386: "Fidele",      # Rwangalinde Fidele
    68270: "Rutambi",     # Rutambi .
    5026211: "Alex",        # Ganza Axel
    5347788: "Pacifique",   # Basha Pacific
    1948256: "Philly",      # Philly Mugisha
    806071: "Tresor",      # Jean tresor Yvan
    1093035: "Patrick",     # Patrick Niyongabo
    4982515: "Amitie",      # R. TheAmo-
    4640117: "Salomon",     # Salomon Beza
    6994188: "Juvens",      # Juvens Muhire
    8633558: "Chris",       # Chris Gunner
    158217: "Emmy",        # Emmy -
    5691475: "Mughaby",     # Cyiza Mughabhy
    488288: "Manzi",       # Manzi Prime
    2249393: "Narcisse",    # Narcisse Izabayo
    8582557: "Otto",        # Otto K
    5314293: "Yvan",        # Yvan UWIDUHAYE
    4520222: "Shukuru",     # Shukuru Ovuvuevuevue
}

# Prize money (RWF)
GW_PRIZE = 17_000                                   # per gameweek, shared equally on a tie
CLASSIC_PRIZES = [120_000, 90_000, 75_000, 50_000]  # 1st, 2nd, 3rd, 4th
POT_TOTAL = 1_000_000                               # 20 x 50,000

# Gameweek prizes already paid out - add the GW number when you pay, e.g. [1, 2, 3]
PAID_GAMEWEEKS = []

# How often the page reloads data from FPL (seconds)
REFRESH_SECONDS = 120
