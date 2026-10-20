"""Kadunde Super League - live FPL dashboard (Streamlit)."""
from datetime import datetime, timedelta, timezone
import html as _html
import textwrap

import plotly.graph_objects as go
import streamlit as st

import chat
import settings as S
from fpl import load_league

st.set_page_config(page_title=f"{S.LEAGUE_NAME} · Dashboard", page_icon="⚽", layout="wide",
                   initial_sidebar_state="collapsed")


# ---------------------------------------------------------------- style
# Light/dark mode: chosen with the switch in the header. Kept in the URL (?theme=light) so it survives
# a browser refresh or a shared link, and in the session so it survives moving between pages.
if st.query_params.get("theme") in ("light", "dark"):
    st.session_state.theme = st.query_params["theme"]
THEME = st.session_state.get("theme", "dark")
if THEME == "light":
    st.query_params["theme"] = "light"
if THEME == "light":
    CYAN, GREEN, GOLD, PURPLE, RED, BLUE = "#0891b2", "#059669", "#b7791f", "#7c3aed", "#dc2626", "#2563eb"
    INK, MUTE, FAINT, LINE, CARD, CARD2 = "#0f1a2e", "#5b6b85", "#8c9ab2", "#d9e1ee", "#ffffff", "#f6f8fc"
    BG, BG2, SHADOW = "#eef2f8", "#e4eaf4", "0 1px 2px rgba(15,26,46,.06), 0 8px 24px rgba(15,26,46,.06)"
else:
    CYAN, GREEN, GOLD, PURPLE, RED, BLUE = "#22d3ee", "#34d399", "#fbbf24", "#a78bfa", "#f87171", "#60a5fa"
    INK, MUTE, FAINT, LINE, CARD, CARD2 = "#e8eefb", "#93a3c3", "#62739a", "#1d2b4a", "#0e1830", "#122042"
    BG, BG2, SHADOW = "#070d1a", "#0b1426", "0 10px 30px rgba(0,0,0,.35)"
HEAT = ("#f87171", "#fbbf24", "#34d399")   # heatmap red -> amber -> green, same in both modes (dark text sits on it)


def tint(c, a):
    """Hex colour -> rgba() with the given opacity."""
    return f"rgba({int(c[1:3], 16)},{int(c[3:5], 16)},{int(c[5:7], 16)},{a})"


st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stMarkdown, .stSelectbox {{font-family: Inter, system-ui, Arial, sans-serif;}}
.stApp {{background: radial-gradient(1200px 600px at 10% -10%, {BG2}, transparent 60%), {BG}; color: {INK};}}
.block-container {{padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1400px;}}
header[data-testid="stHeader"] {{background: {tint(BG, .88)}; backdrop-filter: blur(10px); border-bottom: 1px solid {LINE};}}
[data-testid="stTopNavLink"] {{border-radius: 9px;}}
[data-testid="stTopNavLink"] p {{color: {MUTE}; font-weight: 600;}}
[data-testid="stTopNavLink"]:hover, [data-testid="stTopNavLink"][aria-current="page"] {{background: {CARD2};}}
[data-testid="stTopNavLink"][aria-current="page"] p, [data-testid="stTopNavLink"]:hover p {{color: {INK};}}
footer, #MainMenu {{visibility: hidden;}}
div[data-testid="stVerticalBlockBorderWrapper"] {{background: {CARD}; border: 1px solid {LINE} !important;
  border-radius: 16px; box-shadow: {SHADOW};}}
div[data-baseweb="select"] > div {{background: {CARD2}; border-color: {LINE}; color: {INK};}}
div[data-baseweb="select"] svg {{fill: {MUTE};}}
div[data-baseweb="popover"] ul, div[data-baseweb="popover"] li {{background: {CARD}; color: {INK};}}
div[data-baseweb="popover"] li:hover, div[data-baseweb="popover"] li[aria-selected="true"] {{background: {CARD2};}}
[data-testid="stWidgetLabel"] p {{color: {MUTE};}}
.kd-top {{display:flex; align-items:center; gap:14px; flex-wrap:wrap; padding:6px 2px 14px; border-bottom:1px solid {LINE}; margin-bottom:14px}}
.kd-logo {{width:38px; height:38px; border-radius:11px; display:grid; place-items:center; font-weight:800; color:#06101f;
  background:linear-gradient(135deg,{CYAN},{GREEN}); font-size:18px}}
.kd-brand {{font-weight:800; letter-spacing:.06em; color:{INK}; font-size:17px; line-height:1.1}}
.kd-brand small {{display:block; font-weight:600; color:{MUTE}; letter-spacing:.12em; font-size:10px}}
.kd-sp {{flex:1}}
.kd-pill {{display:inline-flex; align-items:center; gap:7px; padding:6px 12px; border-radius:999px; font-size:11px; font-weight:700;
  letter-spacing:.06em; border:1px solid {LINE}; background:{CARD}; color:{INK}}}
a.kd-pill {{color:{INK} !important; text-decoration:none; cursor:pointer}}
a.kd-pill:hover {{border-color:{CYAN}}}
.kd-live {{color:{GREEN}; border-color:{tint(GREEN, .4)}; background:{tint(GREEN, .12)}}}
.kd-dot {{width:7px; height:7px; border-radius:50%; background:{GREEN}; display:inline-block; animation:kdp 2s infinite}}
@keyframes kdp {{0%{{box-shadow:0 0 0 0 {tint(GREEN, .6)}}}70%{{box-shadow:0 0 0 8px transparent}}100%{{box-shadow:0 0 0 0 transparent}}}}
@media (max-width: 700px) {{.kd-top .kd-season, .kd-top .kd-live {{display:none}}}}
.kd-kpi .lab {{font-size:10.5px; letter-spacing:.11em; text-transform:uppercase; color:{MUTE}; font-weight:700}}
.kd-kpi .val {{font-size:26px; font-weight:800; margin:6px 0 2px; letter-spacing:-.02em; white-space:nowrap; overflow:hidden; text-overflow:ellipsis}}
.kd-kpi .big {{font-size:46px; font-weight:800; letter-spacing:-.03em; line-height:1; margin-top:8px; color:{INK}}}
.kd-kpi .note {{font-size:12px; color:{MUTE}}}
.kd-bar {{height:4px; border-radius:4px; background:{LINE}; margin-top:10px; overflow:hidden}}
.kd-bar i {{display:block; height:100%; border-radius:4px}}
.kd-tag {{font-size:11px; font-weight:700; padding:4px 8px; border-radius:7px; margin-right:6px; display:inline-block; margin-top:10px}}
.kd-h3 {{margin:0; font-size:12px; letter-spacing:.1em; text-transform:uppercase; color:{INK}; font-weight:700}}
.kd-sub {{color:{MUTE}; font-size:12px; margin:2px 0 10px}}
.kd-tbl {{overflow-x:auto}}
.kd-tbl table {{width:100%; border-collapse:collapse; font-size:13px; color:{INK}}}
.kd-tbl th {{font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; color:{FAINT}; font-weight:700; text-align:left;
  padding:8px; border-bottom:1px solid {LINE}; white-space:nowrap}}
.kd-tbl td {{padding:8px; border-bottom:1px solid {LINE}; white-space:nowrap; vertical-align:middle}}
.kd-tbl tr:last-child td {{border-bottom:0}}
.kd-num {{text-align:right; font-variant-numeric:tabular-nums}}
.kd-nm b {{display:block; font-weight:700}} .kd-nm small {{color:{MUTE}; font-size:11.5px}}
.kd-form {{display:flex; gap:3px}}
.kd-form span {{min-width:28px; text-align:center; font-size:11px; font-weight:700; padding:3px 4px; border-radius:6px; color:#0b1220}}
.kd-st {{font-size:10px; font-weight:800; letter-spacing:.08em; padding:4px 8px; border-radius:6px; display:inline-block}}
.kd-medal {{display:inline-grid; place-items:center; width:22px; height:22px; border-radius:50%; font-size:11px; font-weight:800; color:#1b1300}}
.kd-li {{display:grid; grid-template-columns:22px 1fr; gap:10px; align-items:center; margin-bottom:9px}}
.kd-li .r {{font-size:11px; color:{FAINT}; font-weight:800}}
.kd-li .t {{font-size:13px; font-weight:600; display:flex; justify-content:space-between; gap:8px; color:{INK}}}
.kd-li .tr {{height:6px; background:{LINE}; border-radius:6px; overflow:hidden; margin-top:5px; display:flex}}
.kd-li .tr i {{display:block; height:100%}}
.kd-leg {{display:flex; gap:14px; flex-wrap:wrap; font-size:12px; color:{MUTE}; margin-top:6px}}
.kd-leg i {{width:10px; height:10px; border-radius:3px; display:inline-block; margin-right:6px; vertical-align:-1px}}
.kd-spot {{display:grid; grid-template-columns:1fr 1fr; gap:10px}}
.kd-spot div {{background:{CARD2}; border:1px solid {LINE}; border-radius:12px; padding:10px 12px}}
.kd-spot span {{display:block; font-size:10px; letter-spacing:.1em; text-transform:uppercase; color:{MUTE}; font-weight:700}}
.kd-spot b {{font-size:17px; display:block; margin-top:4px; color:{INK}}}
.kd-foot {{display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-top:14px; font-size:11px; color:{FAINT};
  letter-spacing:.06em; text-transform:uppercase}}
.c-cyan{{color:{CYAN}}} .c-green{{color:{GREEN}}} .c-gold{{color:{GOLD}}} .c-red{{color:{RED}}} .c-purple{{color:{PURPLE}}}
</style>""", unsafe_allow_html=True)


def html(s):
    """Render raw HTML (lines are de-indented so Markdown never treats them as code)."""
    st.markdown("\n".join(line.strip() for line in textwrap.dedent(s).splitlines()), unsafe_allow_html=True)


def esc(x):
    return _html.escape(str(x))


def fmt(n):
    return f"{round(n):,}"


def heat_color(v, lo, hi):
    if v is None:
        return CARD2
    t = (v - lo) / (hi - lo) if hi > lo else 0.5
    a, b, c = (248, 113, 113), (251, 191, 36), (52, 211, 153)
    mix = lambda x, y, k: tuple(round(x[i] + (y[i] - x[i]) * k) for i in range(3))
    col = mix(a, b, t * 2) if t < 0.5 else mix(b, c, (t - 0.5) * 2)
    return "rgb(%d,%d,%d)" % col


def card_title(title, sub="", anchor=None):
    aid = f' id="{anchor}"' if anchor else ""
    html(f'<div class="kd-h3"{aid}>{title}</div><div class="kd-sub">{sub}</div>')


def plot(fig, h=270):
    fig.update_layout(template="plotly_white" if THEME == "light" else "plotly_dark",
                      height=h, margin=dict(l=8, r=8, t=8, b=8), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter, Arial", color=MUTE, size=12),
                      legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center"),
                      hoverlabel=dict(bgcolor=CARD2, bordercolor=LINE, font_color=INK))
    fig.update_xaxes(showgrid=False, linecolor=LINE)
    fig.update_yaxes(gridcolor=LINE, zeroline=False)
    st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})


# ---------------------------------------------------------------- extra style for navigation
st.markdown(f"""<style>
div[data-testid="stPageLink"] a {{background:{CARD2}; border:1px solid {LINE}; border-radius:12px; padding:10px 14px;}}
div[data-testid="stPageLink"] a:hover {{border-color:{CYAN};}}
div[data-testid="stPageLink"] p {{font-weight:700; color:{INK};}}
.kd-pagetitle {{font-size:22px; font-weight:800; color:{INK}; margin:2px 0 2px}}
.kd-pagesub {{color:{MUTE}; font-size:13px; margin-bottom:12px}}
[data-testid="stChatMessage"] {{background:{CARD}; border:1px solid {LINE}; border-radius:14px; padding:12px 14px;}}
[data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li {{color:{INK};}}
[data-testid="stChatInput"] {{background:{CARD2}; border:1px solid {LINE}; border-radius:14px;}}
.st-key-kd-bubble {{position:fixed; right:22px; bottom:calc(60px + env(safe-area-inset-bottom, 0px)); z-index:1000; width:auto !important;}}
.st-key-kd-bubble button {{border-radius:999px; padding:10px 18px; border:none; color:#06101f;
  background:linear-gradient(135deg,{CYAN},{GREEN}); box-shadow:0 8px 24px {tint(CYAN, .35)}; font-weight:700;}}
.st-key-kd-bubble button p {{color:#06101f; font-weight:700;}}
.st-key-kd-bubble button:hover {{filter:brightness(1.08);}}
div[data-testid="stPopoverBody"] {{width:min(440px, calc(100vw - 32px)); max-width:none; background:{CARD};
  border:1px solid {LINE}; border-radius:16px;}}
div[data-testid="stPopoverBody"] [data-testid="stChatMessage"] {{padding:8px 10px;}}
div[data-testid="stPopoverBody"] [data-testid="stChatMessage"] p, div[data-testid="stPopoverBody"] li {{font-size:13.5px;}}
div[data-testid="stPopoverBody"] table {{display:block; overflow-x:auto; font-size:12px; margin:4px 0;}}
div[data-testid="stPopoverBody"] th, div[data-testid="stPopoverBody"] td {{padding:4px 8px; white-space:nowrap; color:{INK};}}
div[data-testid="stPopoverBody"] th {{color:{MUTE}; font-weight:700;}}
div[data-testid="stPopoverBody"] p, div[data-testid="stPopoverBody"] small {{color:{INK};}}
div[data-testid="stPopoverBody"] button p {{color:{MUTE};}}
[data-testid="stChatInput"] > div, [data-testid="stChatInput"] textarea {{background:{CARD2} !important;}}
[data-testid="stChatInput"] textarea::placeholder {{color:{FAINT};}}
[data-testid="stChatInput"] textarea {{color:{INK}; caret-color:{INK};}}
</style>""", unsafe_allow_html=True)


CHIP_NAMES = {"bboost": "Bench Boost", "freehit": "Free Hit", "3xc": "Triple Captain", "wildcard": "Wildcard", "manager": "Assistant Manager"}

# ---------------------------------------------------------------- data + calculations (shared by all pages)
def build_ctx():
    D = load_league(S.LEAGUE_ID)
    M = D["managers"]
    for m in M:
        m["nick"] = S.NICKNAMES.get(m["entry"], m["fpl"].split(" ")[0])
    N, fin = len(M), D["finished"]
    L = max([i + 1 for i, f in enumerate(fin) if f], default=0)
    LV = max(L, D["current_gw"] if not D["current_finished"] else L)
    live = LV > L
    idx = list(range(N))
    P = lambda m, g: M[m]["pts"][g - 1]
    H = lambda m, g: M[m]["hits"][g - 1] or 0
    top, winners = [], []
    for g in range(1, 39):
        vals = [P(m, g) for m in idx if P(m, g) is not None]
        mx = max(vals) if vals else None
        top.append(mx)
        winners.append([m for m in idx if mx is not None and P(m, g) == mx])

    def cum(g):
        return [sum((P(m, k) or 0) - H(m, k) for k in range(1, g + 1)) for m in idx]

    def ranks(arr):
        return [1 + sum(1 for x in arr if x > v) for v in arr]

    r_now = ranks(cum(LV))
    r_prev = ranks(cum(LV - 1)) if LV > 1 else r_now
    order = sorted(idx, key=lambda m: M[m]["rank"])
    wins = [0.0] * N
    for g in range(1, L + 1):
        if fin[g - 1] and winners[g - 1] and (top[g - 1] or 0) > 0:
            for m in winners[g - 1]:
                wins[m] += 1 / len(winners[g - 1])
    classic = lambda m: S.CLASSIC_PRIZES[M[m]["rank"] - 1] if 1 <= M[m]["rank"] <= len(S.CLASSIC_PRIZES) else 0
    hit_tot = [sum(M[m]["hits"]) for m in idx]
    chip_pts = []
    for m in idx:
        o = {"bboost": 0, "freehit": 0, "3xc": 0, "used": []}
        for c in M[m]["chips"]:
            o["used"].append(f"{CHIP_NAMES.get(c['chip'], c['chip'])} GW{c['gw']}")
            if c["chip"] in ("bboost", "freehit", "3xc"):
                o[c["chip"]] += P(m, c["gw"]) or 0
        o["total"] = o["bboost"] + o["freehit"] + o["3xc"]
        chip_pts.append(o)
    fs = [P(m, g) for m in idx for g in range(1, 39) if fin[g - 1] and P(m, g) is not None]
    lo, hi = (min(fs), max(fs)) if fs else (0, 100)
    avg = []
    for g in range(1, 39):
        v = [P(m, g) for m in idx if P(m, g) is not None]
        avg.append(round(sum(v) / len(v), 1) if v and (fin[g - 1] or (live and g == LV)) else None)
    return dict(D=D, M=M, N=N, fin=fin, L=L, LV=LV, live=live, idx=idx, P=P, H=H, top=top, winners=winners,
                r_now=r_now, r_prev=r_prev, order=order, leader=order[0], second=order[1], wins=wins,
                classic=classic, hit_tot=hit_tot, chip_pts=chip_pts, lo=lo, hi=hi, avg=avg,
                earn=[wins[m] * S.GW_PRIZE + classic(m) for m in idx])


def names(c, ms):
    return ", ".join(c["M"][m]["nick"] for m in ms) or "-"


def page_head(title, sub):
    html(f'<div class="kd-pagetitle">{title}</div><div class="kd-pagesub">{sub}</div>')


def header(c):
    gw = f"GW{c['LV']} LIVE" if c["live"] else f"GW {c['L']}/38"
    other = "dark" if THEME == "light" else "light"
    switch = (f'<a class="kd-pill" href="?theme={other}" target="_self" title="Switch to {other} mode">'
              f'{"🌙 Dark" if other == "dark" else "☀️ Light"} mode</a>')
    html(f'''<div class="kd-top"><div class="kd-logo">K</div>
    <div class="kd-brand">KADUNDE<small>SUPER LEAGUE · FPL</small></div><div class="kd-sp"></div>
    <span class="kd-pill kd-live"><span class="kd-dot"></span>AUTO-SYNC · FPL LIVE</span>
    <span class="kd-pill kd-season">SEASON {esc(S.SEASON)} · {gw}</span>{switch}</div>''')


def footer(c):
    note = "live bonus & auto-subs included" if c["D"]["live_calc"] else "official FPL points"
    html(f'<div class="kd-foot"><span>Synced {datetime.now(timezone.utc).strftime("%d %b %H:%M UTC")} · {note} · '
         f'refreshes every {S.REFRESH_SECONDS // 60} min</span><span>{esc(S.LEAGUE_NAME)} · Data: Fantasy Premier League</span></div>')


# ---------------------------------------------------------------- building blocks
def kpis(c):
    M, L, LV, live, top, w = c["M"], c["L"], c["LV"], c["live"], c["top"], c["winners"]
    leader, second = c["leader"], c["second"]
    pct = L / 38 * 100
    lw = names(c, w[LV - 1]) if LV else "-"
    hiv, hig = 0, 0
    for g in range(1, L + 1):
        if c["fin"][g - 1] and (top[g - 1] or 0) > hiv:
            hiv, hig = top[g - 1], g
    gw_pot = S.GW_PRIZE * 38
    gw_paid = sum(c["wins"]) * S.GW_PRIZE
    D = c["D"]
    if D["deadline"]:
        dl = datetime.fromisoformat(D["deadline"].replace("Z", "+00:00"))
        secs = max(0, int((dl - datetime.now(timezone.utc)).total_seconds()))
        cd = f"{secs // 86400}d {secs % 86400 // 3600}h {secs % 3600 // 60}m" if secs else "Deadline passed"
        cdn = f"GW{D['next_gw']} · " + dl.astimezone(timezone(timedelta(hours=2))).strftime("%a %d %b, %H:%M") + " Kigali"
    else:
        cd, cdn = "-", "Season complete"
    blocks = [
        f'''<div class="kd-kpi" style="border-left:3px solid {CYAN}; padding-left:12px"><div class="lab">Season progress</div>
        <div class="big">{pct:.1f}%</div><div class="note">{L} of 38 gameweeks finished · {38 - L} to go</div>
        <div class="kd-bar"><i style="width:{pct}%;background:linear-gradient(90deg,{CYAN},{GREEN})"></i></div>
        <span class="kd-tag" style="background:{tint(GREEN, .14)};color:{GREEN}">{c["N"]} MANAGERS</span><span class="kd-tag" style="background:{tint(GOLD, .15)};color:{GOLD}">{fmt(S.POT_TOTAL)} RWF POT</span></div>''',
        f'''<div class="kd-kpi"><div class="lab">League leader</div><div class="val c-gold">{esc(M[leader]["nick"])}</div>
        <div class="note">{M[leader]["total"]} pts · +{M[leader]["total"] - M[second]["total"]} on {esc(M[second]["nick"])}</div>
        <div class="kd-bar"><i style="width:100%;background:{GOLD}"></i></div></div>''',
        f'''<div class="kd-kpi"><div class="lab">{('<span class="kd-dot"></span> GW' + str(LV) + ' live leader') if live else 'Latest GW winner'}</div>
        <div class="val c-cyan">{esc(lw)}</div><div class="note">GW{LV} · {top[LV - 1] if LV else 0} pts{" so far" if live else ""}</div>
        <div class="kd-bar"><i style="width:{min(100, (top[LV - 1] or 0) / 1.4) if LV else 0}%;background:{CYAN}"></i></div></div>''',
        f'''<div class="kd-kpi"><div class="lab">Season-high GW</div><div class="val c-purple">{hiv} pts</div>
        <div class="note">{esc(names(c, w[hig - 1]) if hig else "-")} · GW{hig or "-"}</div><div class="kd-bar"><i style="width:{min(100, hiv / 1.4)}%;background:{PURPLE}"></i></div></div>''',
        f'''<div class="kd-kpi"><div class="lab">Next deadline</div><div class="val c-green">{cd}</div>
        <div class="note">{cdn}</div><div class="kd-bar"><i style="width:60%;background:{GREEN}"></i></div></div>''',
        f'''<div class="kd-kpi"><div class="lab">GW prizes awarded</div><div class="val" style="color:{INK}">{fmt(gw_paid)}</div>
        <div class="note">RWF of {fmt(gw_pot)} · {fmt(S.GW_PRIZE)} per GW</div>
        <div class="kd-bar"><i style="width:{gw_paid / gw_pot * 100}%;background:linear-gradient(90deg,{GOLD},{GREEN})"></i></div></div>''',
    ]
    for col, b in zip(st.columns([1.5, 1, 1, 1, 1, 1]), blocks):
        with col:
            with st.container(border=True):
                html(b)


def donut(c):
    with st.container(border=True):
        card_title("Prize pot", f"Where the {c['N']} × {fmt(S.POT_TOTAL / max(c['N'], 1))} RWF contributions go")
        gw_pot, cl = S.GW_PRIZE * 38, sum(S.CLASSIC_PRIZES)
        parts = [("Gameweek prizes", gw_pot, CYAN), ("Classic top 4", cl, GOLD),
                 ("Transfer charges & treasurer", max(0, S.POT_TOTAL - gw_pot - cl), PURPLE)]
        fig = go.Figure(go.Pie(labels=[p[0] for p in parts], values=[p[1] for p in parts], hole=.72, sort=False,
                               marker=dict(colors=[p[2] for p in parts], line=dict(color=CARD, width=3)),
                               textinfo="none", hovertemplate="%{label}<br>%{value:,} RWF<extra></extra>"))
        fig.add_annotation(text=f"<b style='font-size:22px;color:{INK}'>{S.POT_TOTAL / 1e6:.2f}M</b><br>RWF POT",
                           showarrow=False, font=dict(color=MUTE, size=11))
        fig.update_layout(showlegend=False)
        plot(fig, 200)
        html("".join(f'<div style="display:flex;font-size:13px;color:{INK};margin:6px 0"><span><i style="width:10px;height:10px;border-radius:3px;display:inline-block;background:{col};margin-right:8px"></i>{n}</span><b style="margin-left:auto;color:{MUTE};font-weight:600">{fmt(v)}</b></div>' for n, v, col in parts)
             + "".join(f'<div style="display:flex;font-size:12px;color:{MUTE};margin:4px 0 4px 18px"><span>{p} place</span><b style="margin-left:auto;font-weight:600">{fmt(v)}</b></div>' for p, v in zip(["1st", "2nd", "3rd", "4th"], S.CLASSIC_PRIZES)))


def gw_chart(c, h=330):
    with st.container(border=True):
        card_title("Gameweek scores", "League average vs winning score per gameweek")
        LV, live = c["LV"], c["live"]
        upto = max(LV, min(38, LV + 4))
        labs = [f"GW{g}" + (" (live)" if live and g == LV else "") for g in range(1, upto + 1)]
        win = [c["top"][g - 1] if (c["fin"][g - 1] or (live and g == LV)) else None for g in range(1, upto + 1)]
        wn = [names(c, c["winners"][g - 1]) for g in range(1, upto + 1)]
        fig = go.Figure()
        fig.add_bar(x=labs, y=c["avg"][:upto], name="League average", marker_color=GREEN, marker_cornerradius=6)
        fig.add_scatter(x=labs, y=win, name="Winning score", mode="lines+markers", line=dict(color=CYAN, width=3, shape="spline"),
                        marker=dict(size=8), customdata=wn, hovertemplate="%{y} pts · %{customdata}<extra>Winner</extra>")
        fig.update_layout(bargap=.35)
        plot(fig, h)


def race(c, h=330):
    with st.container(border=True):
        card_title("Title race", "Running total of the current top 5")
        pal = [GOLD, CYAN, GREEN, PURPLE, BLUE]
        LV, live, P, H = c["LV"], c["live"], c["P"], c["H"]
        xs = [f"GW{g}" + (" (live)" if live and g == LV else "") for g in range(1, LV + 1)]
        fig = go.Figure()
        for k, m in enumerate(c["order"][:5]):
            s, ys = 0, []
            for g in range(1, LV + 1):
                s += (P(m, g) or 0) - H(m, g)
                ys.append(s)
            fig.add_scatter(x=xs, y=ys, name=c["M"][m]["nick"], mode="lines+markers",
                            line=dict(color=pal[k], width=2.5, shape="spline"), marker=dict(size=5))
        plot(fig, h)


def standings_table(c, limit=None):
    M, P, LV, live = c["M"], c["P"], c["LV"], c["live"]
    medal = ["#fbbf24", "#cbd5e1", "#d6a77a"]
    rows = []
    for pos_, m in enumerate(c["order"][:limit] if limit else c["order"]):
        r = M[m]["rank"]
        mv = c["r_prev"][m] - c["r_now"][m]
        mvh = f'<span class="c-green">▲{mv}</span>' if mv > 0 else (f'<span class="c-red">▼{-mv}</span>' if mv < 0 else f'<span style="color:{FAINT}">-</span>')
        form = ""
        for g in range(max(1, LV - 4), LV + 1):
            p = P(m, g)
            if live and g == LV:
                form += f'<span style="background:transparent;color:{CYAN};outline:1.5px dashed {CYAN};outline-offset:-1.5px">{p if p is not None else "-"}</span>'
            else:
                form += f'<span style="background:{heat_color(p, c["lo"], c["hi"])}">{p if p is not None else "-"}</span>'
        stt = (f'<span class="kd-st" style="background:{tint(GOLD, .15)};color:{GOLD}">PRIZE ZONE · {c["classic"](m) // 1000}K</span>' if r <= 4 else
               f'<span class="kd-st" style="background:{tint(CYAN, .14)};color:{CYAN}">CHASING</span>' if r <= 8 else
               f'<span class="kd-st" style="background:{CARD2};color:{MUTE}">MIDFIELD</span>')
        rk = f'<span class="kd-medal" style="background:{medal[r - 1]}">{r}</span>' if r <= 3 else f'<b style="color:{MUTE}">{r}</b>'
        bg = f' style="background:{tint(GOLD, .08)}"' if r <= 4 else ""
        gap = "-" if pos_ == 0 else M[m]["total"] - M[c["leader"]]["total"]
        ht = f'<span class="c-red">-{c["hit_tot"][m]}</span>' if c["hit_tot"][m] else "0"
        rows.append(f'<tr{bg}><td>{rk}</td><td style="font-size:11px;font-weight:800">{mvh}</td>'
                    f'<td class="kd-nm"><b>{esc(M[m]["nick"])}</b><small>{esc(M[m]["team"])}</small></td>'
                    f'<td><div class="kd-form">{form}</div></td><td class="kd-num"><b>{M[m]["total"]}</b></td>'
                    f'<td class="kd-num" style="color:{MUTE}">{gap}</td><td class="kd-num">{ht}</td><td>{stt}</td></tr>')
    html('<div class="kd-tbl"><table><thead><tr><th>#</th><th></th><th>Manager</th><th>Form (last 5)</th>'
         '<th class="kd-num">Total</th><th class="kd-num">Gap</th><th class="kd-num">Hits</th><th>Status</th></tr></thead><tbody>'
         + "".join(rows) + "</tbody></table></div>")


def live_list(c, limit=None):
    M, P, H, LV = c["M"], c["P"], c["H"], c["LV"]
    ls = sorted([m for m in c["idx"] if P(m, LV) is not None], key=lambda m: -P(m, LV))[:limit]
    mx = max([P(m, LV) for m in ls] + [1])
    html("".join(f'<div class="kd-li"><div class="r">{i + 1}</div><div><div class="t"><span>{esc(M[m]["nick"])}'
                 + (f' <small class="c-red">(-{H(m, LV)} hit)</small>' if H(m, LV) else "")
                 + f'</span><span class="c-cyan">{P(m, LV)} pts</span></div><div class="tr"><i style="width:{P(m, LV) / mx * 100}%;background:{GOLD if i == 0 else CYAN}"></i></div></div></div>'
                 for i, m in enumerate(ls)))


def winners_table(c):
    M, L, LV, top, w = c["M"], c["L"], c["LV"], c["top"], c["winners"]
    rows = []
    if c["live"]:
        rows.append(f'<tr style="background:{tint(CYAN, .1)}"><td><b style="color:{MUTE}">{LV}</b></td><td class="kd-nm"><b>{esc(names(c, w[LV - 1]))}</b><small>Leading right now · provisional</small></td>'
                    f'<td class="kd-num"><b>{top[LV - 1]}</b></td><td><span class="kd-st" style="background:{tint(CYAN, .14)};color:{CYAN}">LIVE</span></td></tr>')
    for g in range(L, 0, -1):
        if not c["fin"][g - 1]:
            continue
        share = S.GW_PRIZE / max(1, len(w[g - 1]))
        paid = g in S.PAID_GAMEWEEKS
        rows.append(f'<tr><td><b style="color:{MUTE}">{g}</b></td><td class="kd-nm"><b>{esc(names(c, w[g - 1]))}</b>'
                    f'<small>{"Shared · " + fmt(share) + " RWF each" if len(w[g - 1]) > 1 else fmt(share) + " RWF"}</small></td>'
                    f'<td class="kd-num"><b>{top[g - 1]}</b></td><td>'
                    + (f'<span class="kd-st" style="background:{tint(GREEN, .14)};color:{GREEN}">PAID</span>' if paid else
                       f'<span class="kd-st" style="background:{tint(RED, .15)};color:{RED}">UNPAID</span>') + "</td></tr>")
    html('<div class="kd-tbl"><table><thead><tr><th>GW</th><th>Winner</th><th class="kd-num">Pts</th><th>Status</th></tr></thead><tbody>'
         + ("".join(rows) or f'<tr><td colspan="4" style="color:{MUTE}">No finished gameweeks yet</td></tr>') + "</tbody></table></div>")


def money_board(c):
    M, earn, wins = c["M"], c["earn"], c["wins"]
    ms = sorted([m for m in c["idx"] if earn[m] > 0], key=lambda m: -earn[m])
    mx = max(earn + [1])
    html("".join(f'<div class="kd-li"><div class="r">{i + 1}</div><div><div class="t"><span>{esc(M[m]["nick"])}</span><span class="c-gold">{fmt(earn[m])} RWF</span></div>'
                 f'<div class="tr"><i style="width:{wins[m] * S.GW_PRIZE / mx * 100}%;background:{CYAN}"></i><i style="width:{c["classic"](m) / mx * 100}%;background:{GOLD}"></i></div></div></div>'
                 for i, m in enumerate(ms))
         + f'<div class="kd-leg"><span><i style="background:{CYAN}"></i>GW prizes</span><span><i style="background:{GOLD}"></i>Classic (provisional)</span></div>')


def heatmap(c):
    with st.container(border=True):
        card_title("Form heatmap", "Every gameweek score for every manager, in league order")
        M, P, fin, LV, live = c["M"], c["P"], c["fin"], c["LV"], c["live"]
        z, txt = [], []
        for m in c["order"]:
            zr, tr = [], []
            for g in range(1, 39):
                p = P(m, g)
                ok = p is not None and (fin[g - 1] or (live and g == LV))
                zr.append(p if ok else None)
                tr.append(str(p) if ok else "")
            z.append(zr)
            txt.append(tr)
        fig = go.Figure(go.Heatmap(z=z, x=[str(g) for g in range(1, 39)], y=[M[m]["nick"] for m in c["order"]], text=txt,
                                   texttemplate="%{text}", textfont=dict(size=10, color="#0b1220"), xgap=3, ygap=3,
                                   zmin=c["lo"], zmax=c["hi"], colorscale=[[0, HEAT[0]], [.5, HEAT[1]], [1, HEAT[2]]], showscale=False,
                                   hovertemplate="%{y} · GW%{x}: %{z}<extra></extra>"))
        fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
        fig.update_xaxes(side="top", gridcolor="rgba(0,0,0,0)", dtick=1, tickfont=dict(size=10))
        plot(fig, 560)


# ---------------------------------------------------------------- pages
def overview(c):
    kpis(c)
    if c["live"]:
        a, b = st.columns([1, 1.6])
        with a:
            with st.container(border=True):
                card_title(f'<span class="kd-dot"></span> GW{c["LV"]} live · top 5', "Including provisional bonus & auto-subs")
                live_list(c, 5)
                st.page_link(PAGES["gameweeks"], label="All live scores & winners →")
        with b:
            with st.container(border=True):
                card_title("League top 5", "Live total points")
                standings_table(c, 5)
                st.page_link(PAGES["standings"], label="Full standings →")
    else:
        with st.container(border=True):
            card_title("League top 5", "Total points")
            standings_table(c, 5)
            st.page_link(PAGES["standings"], label="Full standings →")
    c1, c2, c3 = st.columns([1, 1.5, 1.2])
    with c1:
        donut(c)
    with c2:
        gw_chart(c)
    with c3:
        race(c)


def standings_page(c):
    page_head("Standings", "Live classic league table · arrows show places moved this gameweek · dashed = live score")
    with st.container(border=True):
        standings_table(c)
    race(c, 380)


def gameweeks_page(c):
    page_head("Gameweeks", f"Gameweek winner = most points before hits · {fmt(S.GW_PRIZE)} RWF, shared equally on a tie")
    left, right = st.columns([1, 1.2])
    with left:
        if c["live"]:
            with st.container(border=True):
                card_title(f'<span class="kd-dot"></span> GW{c["LV"]} live scores', "Points so far incl. provisional bonus & auto-subs")
                live_list(c)
        with st.container(border=True):
            card_title("Gameweek winners", "Latest first")
            winners_table(c)
    with right:
        gw_chart(c, 380)
    heatmap(c)


def prizes_page(c):
    page_head("Prizes", "Where the money goes and who has earned what so far")
    a, b = st.columns([1, 1.3])
    with a:
        donut(c)
    with b:
        with st.container(border=True):
            card_title("Prize money board", "GW prizes won + classic prize if the season ended today")
            money_board(c)
        with st.container(border=True):
            card_title("Gameweek prize payments", "Mark a gameweek as paid in settings.py → PAID_GAMEWEEKS")
            winners_table(c)


def awards_page(c):
    page_head("Awards", "Kwikatisha and best chips usage")
    M, idx, hit_tot, chip_pts = c["M"], c["idx"], c["hit_tot"], c["chip_pts"]
    a1, a2 = st.columns(2)
    with a1:
        with st.container(border=True):
            card_title("Kwikatisha", "Points lost to transfer hits")
            hs = sorted(idx, key=lambda m: (-hit_tot[m], M[m]["nick"]))
            clean = [m for m in idx if hit_tot[m] == 0]
            mh = max(hit_tot + [1])
            best = f"{len(clean)} tied on 0" if len(clean) > 1 else (M[clean[0]]["nick"] if clean else M[hs[-1]]["nick"])
            html(f'<div class="kd-spot" style="margin-bottom:10px"><div><span>Uwikatishije macye</span><b class="c-green">{esc(best)}</b></div>'
                 f'<div><span>Uwikatishije menshi</span><b class="c-red">{esc(M[hs[0]]["nick"])} · {hit_tot[hs[0]]}</b></div></div>'
                 + "".join(f'<div class="kd-li"><div class="r">{i + 1}</div><div><div class="t"><span>{esc(M[m]["nick"])}</span><span class="c-red">-{hit_tot[m]} pts</span></div>'
                           f'<div class="tr"><i style="width:{hit_tot[m] / mh * 100}%;background:{RED}"></i></div></div></div>'
                           for i, m in enumerate([m for m in hs if hit_tot[m] > 0]))
                 + (f'<div class="kd-sub" style="margin-top:4px">No hits yet: {esc(", ".join(M[m]["nick"] for m in clean))}</div>' if clean else ""))
    with a2:
        with st.container(border=True):
            card_title("Best chips usage", "Bench Boost + Free Hit + Triple Captain gameweek points")
            cs = sorted(idx, key=lambda m: -chip_pts[m]["total"])
            mc = max([x["total"] for x in chip_pts] + [1])
            html("".join(f'<div class="kd-li"><div class="r">{i + 1}</div><div><div class="t"><span>{esc(M[m]["nick"])}</span><span class="c-gold">{chip_pts[m]["total"]} pts</span></div>'
                         f'<div class="tr"><i style="width:{chip_pts[m]["bboost"] / mc * 100}%;background:{CYAN}"></i><i style="width:{chip_pts[m]["freehit"] / mc * 100}%;background:{PURPLE}"></i>'
                         f'<i style="width:{chip_pts[m]["3xc"] / mc * 100}%;background:{GOLD}"></i></div></div></div>' for i, m in enumerate(cs))
                 + f'<div class="kd-leg"><span><i style="background:{CYAN}"></i>Bench Boost</span><span><i style="background:{PURPLE}"></i>Free Hit</span><span><i style="background:{GOLD}"></i>Triple Captain</span></div>')


def managers_page(c):
    page_head("Managers", "Pick a manager to see their season")
    M, P, idx, L, fin = c["M"], c["P"], c["idx"], c["L"], c["fin"]
    pick = st.selectbox("Manager", [M[m]["nick"] for m in c["order"]], key="spot")
    m = next(i for i in idx if M[i]["nick"] == pick)
    done = [(g, P(m, g)) for g in range(1, L + 1) if fin[g - 1] and P(m, g) is not None]
    bst = max(done, key=lambda x: x[1]) if done else None
    wst = min(done, key=lambda x: x[1]) if done else None
    cp = c["chip_pts"][m]
    items = [("League rank", f"#{M[m]['rank']}"), ("Total points", M[m]["total"]),
             ("Avg per GW", f"{sum(p for _, p in done) / len(done):.1f}" if done else "-"), ("GW wins", f"{c['wins'][m]:g}"),
             ("Best GW", f"{bst[1]} · GW{bst[0]}" if bst else "-"), ("Worst GW", f"{wst[1]} · GW{wst[0]}" if wst else "-"),
             ("Hits taken", f"{c['hit_tot'][m]} pts"), ("Chips played", ", ".join(cp["used"]) if cp["used"] else "None yet"),
             ("Prize money now", f"{fmt(c['earn'][m])} RWF"), ("Team", M[m]["team"])]
    a, b = st.columns([1, 1.5])
    with a:
        with st.container(border=True):
            card_title(esc(M[m]["nick"]), esc(M[m]["fpl"]))
            html('<div class="kd-spot">' + "".join(f'<div><span>{x}</span><b>{esc(y)}</b></div>' for x, y in items) + "</div>")
    with b:
        with st.container(border=True):
            card_title("Gameweek by gameweek", f"{esc(pick)} vs league average and winning score")
            LV, live = c["LV"], c["live"]
            xs = [f"GW{g}" + (" (live)" if live and g == LV else "") for g in range(1, LV + 1)]
            fig = go.Figure()
            fig.add_bar(x=xs, y=[P(m, g) for g in range(1, LV + 1)], name=pick, marker_color=CYAN, marker_cornerradius=6)
            fig.add_scatter(x=xs, y=c["avg"][:LV], name="League average", mode="lines+markers", line=dict(color=GREEN, width=2.5))
            fig.add_scatter(x=xs, y=c["top"][:LV], name="Winning score", mode="lines+markers", line=dict(color=GOLD, width=2, dash="dot"))
            plot(fig, 330)
            ranks_by_gw = []
            for g in range(1, LV + 1):
                tot = [sum((P(i, k) or 0) - c["H"](i, k) for k in range(1, g + 1)) for i in idx]
                ranks_by_gw.append(1 + sum(1 for t in tot if t > tot[m]))
            fig2 = go.Figure(go.Scatter(x=xs, y=ranks_by_gw, mode="lines+markers+text", text=ranks_by_gw, textposition="top center",
                                        line=dict(color=PURPLE, width=2.5), marker=dict(size=7), name="League rank"))
            worst = max(ranks_by_gw)
            fig2.update_yaxes(range=[worst + 1.5, 0.4], title="League rank", tickvals=list(range(1, worst + 2, 1 if worst <= 10 else 2)))
            card_title("League rank over time", "")
            plot(fig2, 240)


def chat_bubble():
    """Chat window that opens from a floating button in the bottom-right corner of every page.
    The conversation is kept in the session, so it carries on when moving between pages."""
    try:
        c = build_ctx()
    except Exception:
        return
    ai = bool(chat.api_key())
    hist = st.session_state.setdefault("chat", [])
    with st.container(key="kd-bubble"), st.popover("Ask the league", icon="💬", key="kd_chat"):
        top = st.container(horizontal=True, vertical_alignment="center")
        top.markdown("**Kadunde assistant**" + ("" if ai else " · <small>simple mode</small>"), unsafe_allow_html=True)
        if hist and top.button("Clear", type="tertiary"):
            st.session_state.chat = hist = []
        box = st.container(height=420, autoscroll=True, border=False)
        q = st.chat_input("Ask about the league...", key="kd_chat_q")
        with box:
            chat_messages(c, ai, hist, q)


def chat_messages(c, ai, hist, q):
    with st.chat_message("assistant"):
        st.markdown("Muraho! 👋 " + chat.HELP)
    for role, text in hist:
        with st.chat_message(role):
            st.markdown(text, unsafe_allow_html=role == "assistant")
    if q:
        with st.chat_message("user"):
            st.markdown(q)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                a, why = chat.ask_gemini(q, hist, c) if ai else (None, None)
                if a is None:
                    a = chat.simple_answer(q, c)
                    if ai:
                        a += f"\n\n{chat.FALLBACK_NOTE}(The AI assistant couldn't answer, so the simple bot did. Reason: {esc(why)})</small>"
            st.markdown(a, unsafe_allow_html=True)
        hist += [("user", q), ("assistant", a)]


# ---------------------------------------------------------------- navigation
def make_page(fn):
    def run():
        @st.fragment(run_every=S.REFRESH_SECONDS)
        def body():
            try:
                c = build_ctx()
            except Exception as e:
                st.error(f"Could not reach the FPL website right now ({e}). It retries automatically.")
                return
            header(c)
            fn(c)
            footer(c)
        body()
        chat_bubble()   # outside the auto-refreshing part, so a refresh never interrupts a chat
    run.__name__ = fn.__name__
    return run


PAGES = {
    "overview": st.Page(make_page(overview), title="Overview", icon="🏠", default=True),
    "standings": st.Page(make_page(standings_page), title="Standings", icon="🏆", url_path="standings"),
    "gameweeks": st.Page(make_page(gameweeks_page), title="Gameweeks", icon="📅", url_path="gameweeks"),
    "prizes": st.Page(make_page(prizes_page), title="Prizes", icon="💰", url_path="prizes"),
    "awards": st.Page(make_page(awards_page), title="Awards", icon="🎖️", url_path="awards"),
    "managers": st.Page(make_page(managers_page), title="Managers", icon="👤", url_path="managers"),
}
st.navigation(list(PAGES.values()), position="top").run()
