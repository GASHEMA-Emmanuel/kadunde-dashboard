"""Kadunde Super League - live FPL dashboard (Streamlit)."""
from datetime import datetime, timedelta, timezone
import html as _html
import textwrap

import plotly.graph_objects as go
import streamlit as st

import settings as S
from fpl import load_league

st.set_page_config(page_title=f"{S.LEAGUE_NAME} · Dashboard", page_icon="⚽", layout="wide",
                   initial_sidebar_state="collapsed")

# ---------------------------------------------------------------- style
CYAN, GREEN, GOLD, PURPLE, RED, BLUE = "#22d3ee", "#34d399", "#fbbf24", "#a78bfa", "#f87171", "#60a5fa"
INK, MUTE, FAINT, LINE, CARD, CARD2 = "#e8eefb", "#93a3c3", "#62739a", "#1d2b4a", "#0e1830", "#122042"

st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stMarkdown, .stSelectbox {{font-family: Inter, system-ui, Arial, sans-serif;}}
.stApp {{background: radial-gradient(1200px 600px at 10% -10%, #0b1426, transparent 60%), #070d1a;}}
.block-container {{padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1400px;}}
header[data-testid="stHeader"] {{background: transparent;}}
footer, #MainMenu {{visibility: hidden;}}
div[data-testid="stVerticalBlockBorderWrapper"] {{background: {CARD}; border: 1px solid {LINE} !important;
  border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,.35);}}
.kd-top {{display:flex; align-items:center; gap:14px; flex-wrap:wrap; padding:6px 2px 14px; border-bottom:1px solid {LINE}; margin-bottom:14px}}
.kd-logo {{width:38px; height:38px; border-radius:11px; display:grid; place-items:center; font-weight:800; color:#06101f;
  background:linear-gradient(135deg,{CYAN},{GREEN}); font-size:18px}}
.kd-brand {{font-weight:800; letter-spacing:.06em; color:{INK}; font-size:17px; line-height:1.1}}
.kd-brand small {{display:block; font-weight:600; color:{MUTE}; letter-spacing:.12em; font-size:10px}}
.kd-sp {{flex:1}}
.kd-pill {{display:inline-flex; align-items:center; gap:7px; padding:6px 12px; border-radius:999px; font-size:11px; font-weight:700;
  letter-spacing:.06em; border:1px solid {LINE}; background:{CARD}; color:{INK}}}
.kd-live {{color:{GREEN}; border-color:rgba(52,211,153,.4); background:rgba(52,211,153,.12)}}
.kd-dot {{width:7px; height:7px; border-radius:50%; background:{GREEN}; display:inline-block; animation:kdp 2s infinite}}
@keyframes kdp {{0%{{box-shadow:0 0 0 0 rgba(52,211,153,.6)}}70%{{box-shadow:0 0 0 8px transparent}}100%{{box-shadow:0 0 0 0 transparent}}}}
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


def card_title(title, sub=""):
    html(f'<div class="kd-h3">{title}</div><div class="kd-sub">{sub}</div>')


def plot(fig, h=270):
    fig.update_layout(height=h, margin=dict(l=8, r=8, t=8, b=8), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter, Arial", color=MUTE, size=12),
                      legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center"),
                      hoverlabel=dict(bgcolor=CARD2, bordercolor=LINE, font_color=INK))
    fig.update_xaxes(showgrid=False, linecolor=LINE)
    fig.update_yaxes(gridcolor=LINE, zeroline=False)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


# ---------------------------------------------------------------- dashboard
@st.fragment(run_every=S.REFRESH_SECONDS)
def dashboard():
    try:
        D = load_league(S.LEAGUE_ID)
    except Exception as e:
        st.error(f"Could not reach the FPL website right now ({e}). It retries automatically.")
        return

    M = D["managers"]
    for m in M:
        m["nick"] = S.NICKNAMES.get(m["entry"], m["fpl"].split(" ")[0])
    N, fin = len(M), D["finished"]
    L = max([i + 1 for i, f in enumerate(fin) if f], default=0)              # last finished GW
    LV = max(L, D["current_gw"] if not D["current_finished"] else L)          # latest GW with points
    live = LV > L
    idx = range(N)
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

    r_now, r_prev = ranks(cum(LV)), (ranks(cum(LV - 1)) if LV > 1 else ranks(cum(LV)))
    order = sorted(idx, key=lambda m: M[m]["rank"])
    leader, second = order[0], order[1]

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
            o["used"].append(f"{c['chip']} GW{c['gw']}")
            if c["chip"] in ("bboost", "freehit", "3xc"):
                o[c["chip"]] += P(m, c["gw"]) or 0
        o["total"] = o["bboost"] + o["freehit"] + o["3xc"]
        chip_pts.append(o)
    fin_scores = [P(m, g) for m in idx for g in range(1, 39) if fin[g - 1] and P(m, g) is not None]
    lo, hi = (min(fin_scores), max(fin_scores)) if fin_scores else (0, 100)

    # ---------------- header
    html(f'''<div class="kd-top"><div class="kd-logo">K</div>
    <div class="kd-brand">KADUNDE<small>SUPER LEAGUE · FPL</small></div><div class="kd-sp"></div>
    <span class="kd-pill kd-live"><span class="kd-dot"></span>AUTO-SYNC · FPL LIVE</span>
    <span class="kd-pill">SEASON {esc(S.SEASON)} · {"GW" + str(LV) + " LIVE" if live else "GW " + str(L) + "/38"}</span></div>''')

    # ---------------- KPIs
    pct = L / 38 * 100
    lw = ", ".join(M[m]["nick"] for m in winners[LV - 1]) if LV else "-"
    hiv, hig = 0, 0
    for g in range(1, L + 1):
        if fin[g - 1] and (top[g - 1] or 0) > hiv:
            hiv, hig = top[g - 1], g
    hiw = ", ".join(M[m]["nick"] for m in winners[hig - 1]) if hig else "-"
    gw_pot = S.GW_PRIZE * 38
    gw_paid = sum(wins) * S.GW_PRIZE
    if D["deadline"]:
        dl = datetime.fromisoformat(D["deadline"].replace("Z", "+00:00"))
        left = dl - datetime.now(timezone.utc)
        secs = max(0, int(left.total_seconds()))
        cd = f"{secs // 86400}d {secs % 86400 // 3600}h {secs % 3600 // 60}m" if secs else "Deadline passed"
        kigali = dl.astimezone(timezone(timedelta(hours=2)))
        cdn = f"GW{D['next_gw']} · " + kigali.strftime("%a %d %b, %H:%M") + " Kigali"
    else:
        cd, cdn = "-", "Season complete"

    k = st.columns([1.5, 1, 1, 1, 1, 1])
    blocks = [
        f'''<div class="kd-kpi" style="border-left:3px solid {CYAN}; padding-left:12px"><div class="lab">Season progress · {esc(S.LEAGUE_NAME)}</div>
        <div class="big">{pct:.1f}%</div><div class="note">{L} of 38 gameweeks finished · {38 - L} to go</div>
        <div class="kd-bar"><i style="width:{pct}%;background:linear-gradient(90deg,{CYAN},{GREEN})"></i></div>
        <span class="kd-tag" style="background:rgba(52,211,153,.14);color:{GREEN}">{N} MANAGERS</span><span class="kd-tag" style="background:rgba(251,191,36,.15);color:{GOLD}">{fmt(S.POT_TOTAL)} RWF POT</span></div>''',
        f'''<div class="kd-kpi"><div class="lab">League leader</div><div class="val c-gold">{esc(M[leader]["nick"])}</div>
        <div class="note">{M[leader]["total"]} pts · +{M[leader]["total"] - M[second]["total"]} on {esc(M[second]["nick"])}</div>
        <div class="kd-bar"><i style="width:100%;background:{GOLD}"></i></div></div>''',
        f'''<div class="kd-kpi"><div class="lab">{('<span class="kd-dot"></span> GW' + str(LV) + ' live leader') if live else 'Latest GW winner'}</div>
        <div class="val c-cyan">{esc(lw)}</div><div class="note">GW{LV} · {top[LV - 1] if LV else 0} pts{" so far" if live else ""}</div>
        <div class="kd-bar"><i style="width:{min(100, (top[LV - 1] or 0) / 1.4) if LV else 0}%;background:{CYAN}"></i></div></div>''',
        f'''<div class="kd-kpi"><div class="lab">Season-high GW</div><div class="val c-purple">{hiv} pts</div>
        <div class="note">{esc(hiw)} · GW{hig or "-"}</div><div class="kd-bar"><i style="width:{min(100, hiv / 1.4)}%;background:{PURPLE}"></i></div></div>''',
        f'''<div class="kd-kpi"><div class="lab">Next deadline</div><div class="val c-green">{cd}</div>
        <div class="note">{cdn}</div><div class="kd-bar"><i style="width:60%;background:{GREEN}"></i></div></div>''',
        f'''<div class="kd-kpi"><div class="lab">GW prizes awarded</div><div class="val" style="color:{INK}">{fmt(gw_paid)}</div>
        <div class="note">RWF of {fmt(gw_pot)} · {fmt(S.GW_PRIZE)} per GW</div>
        <div class="kd-bar"><i style="width:{gw_paid / gw_pot * 100}%;background:linear-gradient(90deg,{GOLD},{GREEN})"></i></div></div>''',
    ]
    for col, b in zip(k, blocks):
        with col:
            with st.container(border=True):
                html(b)

    # ---------------- charts row
    c1, c2, c3 = st.columns([1, 1.5, 1.2])
    with c1:
        with st.container(border=True):
            card_title("Prize pot", f"Where the {N} × {fmt(S.POT_TOTAL / max(N, 1))} RWF contributions go")
            cl = sum(S.CLASSIC_PRIZES)
            parts = [("Gameweek prizes", gw_pot, CYAN), ("Classic top 4", cl, GOLD),
                     ("Transfer charges & treasurer", max(0, S.POT_TOTAL - gw_pot - cl), PURPLE)]
            fig = go.Figure(go.Pie(labels=[p[0] for p in parts], values=[p[1] for p in parts], hole=.72,
                                   marker=dict(colors=[p[2] for p in parts], line=dict(color=CARD, width=3)),
                                   textinfo="none", hovertemplate="%{label}<br>%{value:,} RWF<extra></extra>", sort=False))
            fig.add_annotation(text=f"<b style='font-size:22px;color:{INK}'>{S.POT_TOTAL / 1e6:.2f}M</b><br>RWF POT",
                               showarrow=False, font=dict(color=MUTE, size=11))
            fig.update_layout(showlegend=False)
            plot(fig, 200)
            html("".join(f'<div style="display:flex;font-size:13px;color:{INK};margin:6px 0"><span><i style="width:10px;height:10px;border-radius:3px;display:inline-block;background:{c};margin-right:8px"></i>{n}</span><b style="margin-left:auto;color:{MUTE};font-weight:600">{fmt(v)}</b></div>' for n, v, c in parts)
                 + "".join(f'<div style="display:flex;font-size:12px;color:{MUTE};margin:4px 0 4px 18px"><span>{p} place</span><b style="margin-left:auto;font-weight:600">{fmt(v)}</b></div>' for p, v in zip(["1st", "2nd", "3rd", "4th"], S.CLASSIC_PRIZES)))
    with c2:
        with st.container(border=True):
            card_title("Gameweek scores", "League average vs winning score per gameweek")
            upto = max(LV, min(38, LV + 4))
            labs, avg, win, wn = [], [], [], []
            for g in range(1, upto + 1):
                labs.append(f"GW{g}" + (" (live)" if live and g == LV else ""))
                if fin[g - 1] or (live and g == LV):
                    v = [P(m, g) for m in idx if P(m, g) is not None]
                    avg.append(round(sum(v) / len(v), 1) if v else None)
                    win.append(top[g - 1])
                    wn.append(", ".join(M[m]["nick"] for m in winners[g - 1]))
                else:
                    avg.append(None); win.append(None); wn.append("")
            fig = go.Figure()
            fig.add_bar(x=labs, y=avg, name="League average", marker_color=GREEN, marker_cornerradius=6)
            fig.add_scatter(x=labs, y=win, name="Winning score", mode="lines+markers", line=dict(color=CYAN, width=3, shape="spline"),
                            marker=dict(size=8), customdata=wn, hovertemplate="%{y} pts · %{customdata}<extra>Winner</extra>")
            fig.update_layout(bargap=.35)
            plot(fig, 330)
    with c3:
        with st.container(border=True):
            card_title("Title race", "Running total of the current top 5")
            pal = [GOLD, CYAN, GREEN, PURPLE, BLUE]
            fig = go.Figure()
            xs = [f"GW{g}" + (" (live)" if live and g == LV else "") for g in range(1, LV + 1)]
            for k_, m in enumerate(order[:5]):
                s, ys = 0, []
                for g in range(1, LV + 1):
                    s += (P(m, g) or 0) - H(m, g)
                    ys.append(s)
                fig.add_scatter(x=xs, y=ys, name=M[m]["nick"], mode="lines+markers",
                                line=dict(color=pal[k_], width=2.5, shape="spline"), marker=dict(size=5))
            plot(fig, 330)

    # ---------------- standings + right column
    left, right = st.columns([1.7, 1])
    with left:
        with st.container(border=True):
            card_title("Live standings & form", "Gold = classic prize places · arrows = places moved this gameweek · dashed = live score")
            medal = ["#fbbf24", "#cbd5e1", "#d6a77a"]
            rows = []
            for pos_, m in enumerate(order):
                r = M[m]["rank"]
                mv = r_prev[m] - r_now[m]
                mvh = f'<span class="c-green">▲{mv}</span>' if mv > 0 else (f'<span class="c-red">▼{-mv}</span>' if mv < 0 else f'<span style="color:{FAINT}">-</span>')
                form = ""
                for g in range(max(1, LV - 4), LV + 1):
                    p = P(m, g)
                    if live and g == LV:
                        form += f'<span style="background:transparent;color:{CYAN};outline:1.5px dashed {CYAN};outline-offset:-1.5px">{p if p is not None else "-"}</span>'
                    else:
                        form += f'<span style="background:{heat_color(p, lo, hi)}">{p if p is not None else "-"}</span>'
                stt = (f'<span class="kd-st" style="background:rgba(251,191,36,.15);color:{GOLD}">PRIZE ZONE · {classic(m) // 1000}K</span>' if r <= 4 else
                       f'<span class="kd-st" style="background:rgba(34,211,238,.14);color:{CYAN}">CHASING</span>' if r <= 8 else
                       f'<span class="kd-st" style="background:{CARD2};color:{MUTE}">MIDFIELD</span>')
                rk = f'<span class="kd-medal" style="background:{medal[r - 1]}">{r}</span>' if r <= 3 else f'<b style="color:{MUTE}">{r}</b>'
                bg = ' style="background:rgba(251,191,36,.08)"' if r <= 4 else ""
                gap = "-" if pos_ == 0 else M[m]["total"] - M[leader]["total"]
                ht = f'<span class="c-red">-{hit_tot[m]}</span>' if hit_tot[m] else "0"
                rows.append(f'<tr{bg}><td>{rk}</td><td style="font-size:11px;font-weight:800">{mvh}</td>'
                            f'<td class="kd-nm"><b>{esc(M[m]["nick"])}</b><small>{esc(M[m]["team"])}</small></td>'
                            f'<td><div class="kd-form">{form}</div></td><td class="kd-num"><b>{M[m]["total"]}</b></td>'
                            f'<td class="kd-num" style="color:{MUTE}">{gap}</td><td class="kd-num">{ht}</td><td>{stt}</td></tr>')
            html('<div class="kd-tbl"><table><thead><tr><th>#</th><th></th><th>Manager</th><th>Form (last 5)</th>'
                 '<th class="kd-num">Total</th><th class="kd-num">Gap</th><th class="kd-num">Hits</th><th>Status</th></tr></thead><tbody>'
                 + "".join(rows) + "</tbody></table></div>")
    with right:
        if live:
            with st.container(border=True):
                card_title(f'<span class="kd-dot"></span> GW{LV} live scores',
                           "Points so far incl. provisional bonus & auto-subs · winner decided before hits")
                ls = sorted([m for m in idx if P(m, LV) is not None], key=lambda m: -P(m, LV))
                mx = max([P(m, LV) for m in ls] + [1])
                html("".join(f'<div class="kd-li"><div class="r">{i + 1}</div><div><div class="t"><span>{esc(M[m]["nick"])}'
                             + (f' <small class="c-red">(-{H(m, LV)} hit)</small>' if H(m, LV) else "")
                             + f'</span><span class="c-cyan">{P(m, LV)} pts</span></div><div class="tr"><i style="width:{P(m, LV) / mx * 100}%;background:{GOLD if i == 0 else CYAN}"></i></div></div></div>'
                             for i, m in enumerate(ls)))
        with st.container(border=True):
            card_title("Gameweek winners", f"{fmt(S.GW_PRIZE)} RWF each · ties share the prize")
            rows = []
            if live:
                rows.append(f'<tr style="background:rgba(34,211,238,.1)"><td><b style="color:{MUTE}">{LV}</b></td><td class="kd-nm"><b>{esc(lw)}</b><small>Leading right now · provisional</small></td>'
                            f'<td class="kd-num"><b>{top[LV - 1]}</b></td><td><span class="kd-st" style="background:rgba(34,211,238,.14);color:{CYAN}">LIVE</span></td></tr>')
            for g in range(L, 0, -1):
                if not fin[g - 1]:
                    continue
                w = winners[g - 1]
                share = S.GW_PRIZE / max(1, len(w))
                paid = g in S.PAID_GAMEWEEKS
                rows.append(f'<tr><td><b style="color:{MUTE}">{g}</b></td><td class="kd-nm"><b>{esc(", ".join(M[m]["nick"] for m in w))}</b>'
                            f'<small>{"Shared · " + fmt(share) + " RWF each" if len(w) > 1 else fmt(share) + " RWF"}</small></td>'
                            f'<td class="kd-num"><b>{top[g - 1]}</b></td><td>'
                            + (f'<span class="kd-st" style="background:rgba(52,211,153,.14);color:{GREEN}">PAID</span>' if paid else
                               f'<span class="kd-st" style="background:rgba(248,113,113,.15);color:{RED}">UNPAID</span>') + "</td></tr>")
            html('<div class="kd-tbl"><table><thead><tr><th>GW</th><th>Winner</th><th class="kd-num">Pts</th><th>Status</th></tr></thead><tbody>'
                 + ("".join(rows) or f'<tr><td colspan="4" style="color:{MUTE}">No finished gameweeks yet</td></tr>') + "</tbody></table></div>")
        with st.container(border=True):
            card_title("Prize money board", "GW prizes won + classic prize if the season ended today")
            earn = [wins[m] * S.GW_PRIZE + classic(m) for m in idx]
            ms = sorted([m for m in idx if earn[m] > 0], key=lambda m: -earn[m])
            mx = max(earn + [1])
            html("".join(f'<div class="kd-li"><div class="r">{i + 1}</div><div><div class="t"><span>{esc(M[m]["nick"])}</span><span class="c-gold">{fmt(earn[m])} RWF</span></div>'
                         f'<div class="tr"><i style="width:{wins[m] * S.GW_PRIZE / mx * 100}%;background:{CYAN}"></i><i style="width:{classic(m) / mx * 100}%;background:{GOLD}"></i></div></div></div>'
                         for i, m in enumerate(ms))
                 + f'<div class="kd-leg"><span><i style="background:{CYAN}"></i>GW prizes</span><span><i style="background:{GOLD}"></i>Classic (provisional)</span></div>')

    # ---------------- heatmap
    with st.container(border=True):
        card_title("Form heatmap", "Every gameweek score for every manager, in league order")
        names = [M[m]["nick"] for m in order]
        z, txt = [], []
        for m in order:
            zr, tr = [], []
            for g in range(1, 39):
                p = P(m, g)
                ok = p is not None and (fin[g - 1] or (live and g == LV))
                zr.append(p if ok else None)
                tr.append(str(p) if ok else "")
            z.append(zr); txt.append(tr)
        fig = go.Figure(go.Heatmap(z=z, x=[str(g) for g in range(1, 39)], y=names, text=txt, texttemplate="%{text}",
                                   textfont=dict(size=10, color="#0b1220"), xgap=3, ygap=3, zmin=lo, zmax=hi,
                                   colorscale=[[0, RED], [.5, GOLD], [1, GREEN]], showscale=False,
                                   hovertemplate="%{y} · GW%{x}: %{z}<extra></extra>"))
        fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
        fig.update_xaxes(side="top", gridcolor="rgba(0,0,0,0)", dtick=1, tickfont=dict(size=10))
        plot(fig, 560)

    # ---------------- awards row
    a1, a2, a3 = st.columns([1, 1, 1.1])
    with a1:
        with st.container(border=True):
            card_title("Kwikatisha", "Points lost to transfer hits")
            hs = sorted(idx, key=lambda m: (-hit_tot[m], M[m]["nick"]))
            clean = [m for m in idx if hit_tot[m] == 0]
            mh = max(hit_tot + [1])
            best = (f"{len(clean)} tied on 0" if len(clean) > 1 else (M[clean[0]]["nick"] if clean else M[hs[-1]]["nick"]))
            html(f'<div class="kd-spot" style="margin-bottom:10px"><div><span>Uwikatishije macye</span><b class="c-green">{esc(best)}</b></div>'
                 f'<div><span>Uwikatishije menshi</span><b class="c-red">{esc(M[hs[0]]["nick"])} · {hit_tot[hs[0]]}</b></div></div>'
                 + "".join(f'<div class="kd-li"><div class="r">{i + 1}</div><div><div class="t"><span>{esc(M[m]["nick"])}</span><span class="c-red">-{hit_tot[m]} pts</span></div>'
                           f'<div class="tr"><i style="width:{hit_tot[m] / mh * 100}%;background:{RED}"></i></div></div></div>'
                           for i, m in enumerate([m for m in hs if hit_tot[m] > 0][:9]))
                 + (f'<div class="kd-sub" style="margin-top:4px">No hits yet: {esc(", ".join(M[m]["nick"] for m in clean))}</div>' if clean else ""))
    with a2:
        with st.container(border=True):
            card_title("Best chips usage", "Bench Boost + Free Hit + Triple Captain gameweek points")
            cs = sorted(idx, key=lambda m: -chip_pts[m]["total"])
            mc = max([c["total"] for c in chip_pts] + [1])
            html("".join(f'<div class="kd-li"><div class="r">{i + 1}</div><div><div class="t"><span>{esc(M[m]["nick"])}</span><span class="c-gold">{chip_pts[m]["total"]} pts</span></div>'
                         f'<div class="tr"><i style="width:{chip_pts[m]["bboost"] / mc * 100}%;background:{CYAN}"></i><i style="width:{chip_pts[m]["freehit"] / mc * 100}%;background:{PURPLE}"></i>'
                         f'<i style="width:{chip_pts[m]["3xc"] / mc * 100}%;background:{GOLD}"></i></div></div></div>' for i, m in enumerate(cs[:8]))
                 + f'<div class="kd-leg"><span><i style="background:{CYAN}"></i>Bench Boost</span><span><i style="background:{PURPLE}"></i>Free Hit</span><span><i style="background:{GOLD}"></i>Triple Captain</span></div>')
    with a3:
        with st.container(border=True):
            card_title("Manager spotlight", "Pick anyone in the league")
            pick = st.selectbox("Manager", [M[m]["nick"] for m in order], label_visibility="collapsed", key="spot")
            m = next(i for i in idx if M[i]["nick"] == pick)
            done_pts = [(g, P(m, g)) for g in range(1, L + 1) if fin[g - 1] and P(m, g) is not None]
            bst = max(done_pts, key=lambda x: x[1]) if done_pts else None
            wst = min(done_pts, key=lambda x: x[1]) if done_pts else None
            items = [("League rank", f"#{M[m]['rank']}"), ("Total points", M[m]["total"]),
                     ("Avg per GW", f"{sum(p for _, p in done_pts) / len(done_pts):.1f}" if done_pts else "-"),
                     ("GW wins", f"{wins[m]:g}"), ("Best GW", f"{bst[1]} · GW{bst[0]}" if bst else "-"),
                     ("Worst GW", f"{wst[1]} · GW{wst[0]}" if wst else "-"), ("Hits taken", f"{hit_tot[m]} pts"),
                     ("Chips played", f"{len(chip_pts[m]['used'])} played" if chip_pts[m]["used"] else "None yet"),
                     ("Prize money now", f"{fmt(wins[m] * S.GW_PRIZE + classic(m))} RWF"), ("Team", M[m]["team"])]
            html('<div class="kd-spot">' + "".join(f'<div><span>{a}</span><b>{esc(b)}</b></div>' for a, b in items) + "</div>")

    note = "live bonus & auto-subs included" if D["live_calc"] else "official FPL points"
    html(f'<div class="kd-foot"><span>System status: synced · {datetime.now(timezone.utc).strftime("%d %b %H:%M UTC")} · {note} · refreshes every {S.REFRESH_SECONDS // 60} min</span>'
         f'<span>{esc(S.LEAGUE_NAME)} · Data: Fantasy Premier League</span></div>')


dashboard()
