"""League chatbot: Google Gemini (free tier) answers from the league data; a simple built-in bot answers if
there is no API key or the free daily limit has run out."""
import re

import requests
import streamlit as st

import settings as S

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
FALLBACK_NOTE = "<small>"   # start of the note added under answers from the simple bot (kept out of the AI's history)


def api_key():
    try:
        k = st.secrets.get("GEMINI_API_KEY")
    except Exception:  # no secrets file at all
        return None
    return str(k).strip().strip('"').strip() or None if k else None


def fmt(n):
    return f"{n:,.0f}"


# ---------------------------------------------------------------- league data as text for the AI
def league_text(c):
    M, P, H, L, LV, live, fin = c["M"], c["P"], c["H"], c["L"], c["LV"], c["live"], c["fin"]
    D = c["D"]
    out = [f"League: {S.LEAGUE_NAME}, FPL season {S.SEASON}, {c['N']} managers.",
           f"Finished gameweeks: {L} of 38." + (f" GW{LV} is in progress (live points, can still change)." if live else ""),
           f"Next deadline: GW{D['next_gw']} at {D['deadline']} (UTC)." if D["deadline"] else "",
           f"Rules: each gameweek the highest score (before transfer hits) wins {fmt(S.GW_PRIZE)} RWF, shared equally on a tie. "
           f"At season end ranks 1-4 win {', '.join(fmt(p) for p in S.CLASSIC_PRIZES)} RWF. Total pot {fmt(S.POT_TOTAL)} RWF. "
           f"Gameweek prizes already paid: {', '.join(f'GW{g}' for g in S.PAID_GAMEWEEKS) or 'none yet'}. "
           "League total points are after hits. 'Kwikatisha' means taking transfer hits.",
           "",
           "STANDINGS (rank | nickname | FPL name | team | total pts | places moved this GW | GW wins | hits total | chips | prize money now if season ended today):"]
    for m in c["order"]:
        mv = c["r_prev"][m] - c["r_now"][m]
        chips = ", ".join(c["chip_pts"][m]["used"]) or "none"
        out.append(f"{M[m]['rank']} | {M[m]['nick']} | {M[m]['fpl']} | {M[m]['team']} | {M[m]['total']} | "
                   f"{mv:+d} | {c['wins'][m]:g} | -{c['hit_tot'][m]} | {chips} | {fmt(c['earn'][m])} RWF")
    out += ["", "POINTS PER GAMEWEEK (before hits; hits in brackets):"]
    for m in c["order"]:
        gws = []
        for g in range(1, LV + 1):
            p = P(m, g)
            if p is None:
                continue
            gws.append(f"GW{g}={p}" + (f"(-{H(m, g)})" if H(m, g) else "") + ("[live]" if live and g == LV else ""))
        out.append(f"{M[m]['nick']}: {', '.join(gws) or 'no points yet'}")
    out += ["", "GAMEWEEK WINNERS:"]
    for g in range(1, LV + 1):
        w = c["winners"][g - 1]
        if not w:
            continue
        state = "live, provisional" if live and g == LV else ("paid" if g in S.PAID_GAMEWEEKS else "unpaid")
        out.append(f"GW{g}: {', '.join(M[m]['nick'] for m in w)} with {c['top'][g - 1]} pts "
                   f"(league average {c['avg'][g - 1]}) - {state}")
    return "\n".join(x for x in out if x is not None)


SYSTEM = """You are the friendly assistant of the {league} fantasy football (FPL) league dashboard.
Answer questions using ONLY the league data below. If the answer is not in the data, say you don't know.
Keep answers short (a few sentences, a small list or a small markdown table). Call managers by their nickname.
Money is in RWF. Reply in the same language as the question (for example English, Kinyarwanda or French).
Light banter about the league is fine, but stay kind.

{data}"""


def ask_gemini(question, history, c):
    """Returns (answer, problem). answer is None if Gemini couldn't answer; problem then says why."""
    key = api_key()
    if not key:
        return None, "no GEMINI_API_KEY secret"
    contents = []
    for r, t in history[-8:]:
        if r == "assistant" and FALLBACK_NOTE in t:   # don't feed the simple bot's notes back to the AI
            t = t.split(FALLBACK_NOTE)[0].strip()
        contents.append({"role": "user" if r == "user" else "model", "parts": [{"text": t}]})
    contents.append({"role": "user", "parts": [{"text": question}]})
    body = {"system_instruction": {"parts": [{"text": SYSTEM.format(league=S.LEAGUE_NAME, data=league_text(c))}]},
            "contents": contents}
    problems = []
    for model, level in S.CHAT_MODELS.items():   # each model has its own free daily limit, so try the next one if one is used up
        try:
            post = lambda b: requests.post(GEMINI_URL.format(model), json=b, headers={"x-goog-api-key": key}, timeout=30)
            r = post({**body, "generationConfig": {"thinkingConfig": {"thinkingLevel": level}}})
            if r.status_code == 400 and "think" in r.text.lower():   # model doesn't accept that thinking level
                r = post(body)
            if r.status_code != 200:
                try:
                    msg = r.json()["error"]["message"]
                except Exception:
                    msg = r.text[:200]
                problems.append(f"{model}: {r.status_code} {msg.split('. ')[0][:160]}")
                continue
            parts = r.json()["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
            if text:
                return text, None
            problems.append(f"{model}: empty answer")
        except Exception as e:
            problems.append(f"{model}: {type(e).__name__}")
    return None, "; ".join(problems).replace(key, "***")


# ---------------------------------------------------------------- simple built-in bot (no AI, always free)
def find_managers(q, c):
    """Managers named in the question - nicknames first, FPL names only if no nickname matches."""
    M = c["M"]
    hit = lambda words: any(re.search(rf"(?<!\w){re.escape(w)}(?!\w)", q) for w in words)
    by_nick = [m for m in c["order"] if hit([M[m]["nick"].lower()])]
    if by_nick:
        return sorted(by_nick, key=lambda m: q.find(M[m]["nick"].lower()))
    return [m for m in c["order"] if hit([w.lower() for w in M[m]["fpl"].split() if len(w) > 2])]


def find_gws(q, c):
    """Gameweeks in the question: 'gw5', 'gameweek 5', 'gw1-gw7', 'gw 1 to 7', 'this week', 'last week'."""
    LV, L = c["LV"], c["L"]
    gw = r"(?:gw|gameweek|game week|week)\s*"
    m = re.search(rf"{gw}(\d{{1,2}})\s*(?:-|–|to|until|till)\s*(?:{gw})?(\d{{1,2}})", q)
    if m:
        a, b = sorted((int(m.group(1)), int(m.group(2))))
        return [g for g in range(a, b + 1) if 1 <= g <= 38]
    gs = [int(x) for x in re.findall(rf"{gw}(\d{{1,2}})", q) if 1 <= int(x) <= 38]
    if gs:
        return gs
    if re.search(r"\b(this|current|live) (gw|gameweek|week)\b", q):
        return [LV]
    if re.search(r"\b(last|previous) (gw|gameweek|week)\b", q):
        return [L]
    return []


def simple_answer(question, c):
    q = " " + question.lower().strip() + " "
    M, P, H, L, LV, live, idx = c["M"], c["P"], c["H"], c["L"], c["LV"], c["live"], c["idx"]
    nick = lambda m: M[m]["nick"]
    has = lambda *ws: any(w in q for w in ws)
    who, gws = find_managers(q, c), find_gws(q, c)
    tag = lambda g: " *(live)*" if live and g == LV else ""
    played = lambda m: [(g, P(m, g)) for g in range(1, LV + 1) if P(m, g) is not None]
    leader = c["order"][0]

    def summary(m):
        done = [x for x in played(m) if c["fin"][x[0] - 1]]
        best = max(done, key=lambda x: x[1]) if done else None
        worst = min(done, key=lambda x: x[1]) if done else None
        gap = M[leader]["total"] - M[m]["total"]
        form = ", ".join(f"{p}" for _, p in played(m)[-5:])
        return (f"**{nick(m)}** ({M[m]['team']}) is **#{M[m]['rank']}** with **{M[m]['total']} pts**"
                + (f", {gap} behind {nick(leader)}." if gap else ", top of the league! 🏆") + "\n\n"
                + f"- Last 5 GWs: {form or '-'}\n"
                + (f"- Best GW: {best[1]} (GW{best[0]}) · Worst GW: {worst[1]} (GW{worst[0]})\n" if best else "")
                + f"- GW wins: {c['wins'][m]:g} · Hits: -{c['hit_tot'][m]} pts\n"
                + f"- Chips: {', '.join(c['chip_pts'][m]['used']) or 'none yet'}\n"
                + f"- Prize money now: {fmt(c['earn'][m])} RWF")

    def winners_list(gs):
        rows = []
        for g in gs:
            w = c["winners"][g - 1]
            if not w or c["top"][g - 1] is None:
                rows.append(f"| GW{g} | not played yet | | |")
                continue
            state = "live" if live and g == LV else ("paid" if g in S.PAID_GAMEWEEKS else "unpaid")
            rows.append(f"| GW{g} | **{', '.join(nick(m) for m in w)}** | {c['top'][g - 1]} | {state} |")
        return "| GW | Winner | Pts | Prize |\n|---|---|---|---|\n" + "\n".join(rows)

    # --- greetings / help
    if re.fullmatch(r"\s*(hi|hello|hey|muraho|mwiriwe|mwaramutse|bite|help|\?)\W*\s*", q):
        return HELP

    # --- whole-league summary
    if not who and has("summary", "summarise", "summarize", "overview", "recap", "update", "incamake", "how is the league"):
        sec = c["order"][1]
        lg = LV if c["winners"][LV - 1] else L
        hi = max(((m, g, P(m, g)) for m in idx for g in range(1, LV + 1) if P(m, g) is not None), key=lambda x: x[2], default=None)
        mw = max(c["wins"]) if c["wins"] else 0
        hs = max(idx, key=lambda m: c["hit_tot"][m])
        d = c["D"]
        zone = ", ".join(f"{nick(m)} ({M[m]['total']})" for m in c["order"][:4])
        return (f"**{S.LEAGUE_NAME}** after GW{LV}" + (" *(live)*" if live else "") + f" - {L} of 38 gameweeks finished.\n\n"
                + f"- 🏆 **{nick(leader)}** leads with {M[leader]['total']} pts, {M[leader]['total'] - M[sec]['total']} ahead of {nick(sec)}\n"
                + f"- 💰 Prize zone: {zone}\n"
                + (f"- 📅 GW{lg} winner: **{', '.join(nick(m) for m in c['winners'][lg - 1])}** with {c['top'][lg - 1]} pts{tag(lg)}\n" if lg else "")
                + (f"- 🔥 Season high: {nick(hi[0])} with {hi[2]} in GW{hi[1]}\n" if hi else "")
                + (f"- 🥇 Most GW wins: {', '.join(nick(m) for m in idx if c['wins'][m] == mw)} ({mw:g})\n" if mw else "")
                + (f"- ✂️ Most hits: {nick(hs)} (-{c['hit_tot'][hs]})\n" if c["hit_tot"][hs] else "")
                + f"- ⬇️ Bottom: {nick(c['order'][-1])} with {M[c['order'][-1]]['total']} pts\n"
                + (f"- ⏰ Next deadline: GW{d['next_gw']} at {d['deadline'].replace('T', ' ').replace('Z', '')} UTC" if d["deadline"] else ""))

    # --- questions about specific managers
    if len(who) >= 2 and not gws:
        rows = "\n".join(f"| **{nick(m)}** | #{M[m]['rank']} | {M[m]['total']} | {c['wins'][m]:g} | {-c['hit_tot'][m]} | {fmt(c['earn'][m])} |"
                         for m in who)
        a, b = who[0], who[1]
        d = M[a]["total"] - M[b]["total"]
        lead = f"**{nick(a)}** leads **{nick(b)}** by {d} pts." if d > 0 else (
            f"**{nick(b)}** leads **{nick(a)}** by {-d} pts." if d < 0 else f"{nick(a)} and {nick(b)} are level on points.")
        return lead + "\n\n| Manager | Rank | Pts | GW wins | Hits | Prize (RWF) |\n|---|---|---|---|---|---|\n" + rows
    if who and gws:
        return "\n\n".join(f"**{nick(m)}**: " + ", ".join(
            f"GW{g} **{P(m, g)}**" + (f" (-{H(m, g)} hit)" if H(m, g) else "") + tag(g) if P(m, g) is not None else f"GW{g} -"
            for g in gws) for m in who)
    if who and has("prize", "money", "rwf", "earn", "how much", "amafaranga"):
        return "\n\n".join(f"**{nick(m)}** would have **{fmt(c['earn'][m])} RWF** if the season ended today "
                           f"({c['wins'][m]:g} GW win(s) + {fmt(c['classic'](m))} RWF classic prize)." for m in who)
    if who and has("chip"):
        return "\n\n".join(f"**{nick(m)}** chips: {', '.join(c['chip_pts'][m]['used']) or 'none played yet'} "
                           f"({c['chip_pts'][m]['total']} pts from BB/FH/TC)." for m in who)
    if who and has("hit", "kwikatisha"):
        return "\n\n".join(f"**{nick(m)}** has lost **{c['hit_tot'][m]}** pts to hits." for m in who)
    if who and has("best", "highest", "top score"):
        return "\n\n".join(f"**{nick(m)}**'s best GW: **{b[1]}** in GW{b[0]}" for m in who
                           for b in [max(played(m), key=lambda x: x[1])] if played(m))
    if who and has("worst", "lowest"):
        return "\n\n".join(f"**{nick(m)}**'s worst GW: **{b[1]}** in GW{b[0]}" for m in who
                           for b in [min(played(m), key=lambda x: x[1])] if played(m))
    if who:
        return "\n\n---\n\n".join(summary(m) for m in who)

    # --- gameweek winners
    if re.search(r"\b(winners?|won|wins?)\b|yatsinze|yatwaye", q):
        if has("most", "many", "count", "how many"):
            ws = sorted([m for m in idx if c["wins"][m]], key=lambda m: -c["wins"][m])
            return "Gameweek wins so far:\n\n" + "\n".join(f"- **{nick(m)}**: {c['wins'][m]:g}" for m in ws) if ws else "No gameweek finished yet."
        return winners_list(gws or list(range(1, LV + 1)))

    # --- one or more gameweeks: top scorers
    if gws:
        out = []
        for g in gws:
            sc = sorted([m for m in idx if P(m, g) is not None], key=lambda m: -P(m, g))
            if not sc:
                out.append(f"GW{g} hasn't been played yet.")
                continue
            out.append(f"**GW{g}**{tag(g)} - average {c['avg'][g - 1]}\n\n" + "\n".join(
                f"{i + 1}. {nick(m)} - {P(m, g)}" + (f" (-{H(m, g)})" if H(m, g) else "") for i, m in enumerate(sc[:10] if len(gws) == 1 else sc[:3])))
        return "\n\n".join(out)

    # --- league-wide questions
    if has("highest", "season high", "best score", "best gw", "record"):
        b = max(((m, g, P(m, g)) for m in idx for g in range(1, LV + 1) if P(m, g) is not None), key=lambda x: x[2], default=None)
        return f"Season-high score: **{nick(b[0])}** with **{b[2]}** pts in GW{b[1]}." if b else "No scores yet."
    if has("lowest", "worst score", "worst gw"):
        b = min(((m, g, P(m, g)) for m in idx for g in range(1, L + 1) if P(m, g) is not None), key=lambda x: x[2], default=None)
        return f"Lowest score so far: **{nick(b[0])}** with **{b[2]}** pts in GW{b[1]}." if b else "No finished gameweeks yet."
    if has("last place", "bottom", "worst manager", "uwanyuma", " last "):
        return "Bottom of the table:\n\n" + "\n".join(f"{M[m]['rank']}. {nick(m)} - {M[m]['total']} pts" for m in c["order"][-3:])
    if has("climb", "rise", "riser", "mover", "moved", "fall", "drop", "fell"):
        mv = sorted(idx, key=lambda m: c["r_now"][m] - c["r_prev"][m])
        up = [m for m in mv if c["r_prev"][m] > c["r_now"][m]][:3]
        down = [m for m in mv[::-1] if c["r_prev"][m] < c["r_now"][m]][:3]
        return (f"Movers in GW{LV}:\n\n"
                + "".join(f"- ▲ **{nick(m)}** up {c['r_prev'][m] - c['r_now'][m]} to #{c['r_now'][m]}\n" for m in up)
                + "".join(f"- ▼ **{nick(m)}** down {c['r_now'][m] - c['r_prev'][m]} to #{c['r_now'][m]}\n" for m in down)) if up or down else "No changes in the table this gameweek."
    if has("average", "avg"):
        return "League average per gameweek:\n\n" + "\n".join(f"- GW{g}{tag(g)}: {c['avg'][g - 1]}" for g in range(1, LV + 1) if c["avg"][g - 1] is not None)
    if has("live", "right now", "today", "this week", "current"):
        g = LV
        sc = sorted([m for m in idx if P(m, g) is not None], key=lambda m: -P(m, g))
        return f"**GW{g}**{tag(g)} scores:\n\n" + "\n".join(f"{i + 1}. {nick(m)} - {P(m, g)}" for i, m in enumerate(sc[:10]))
    if has("hit", "kwikatisha"):
        hs = sorted(idx, key=lambda m: -c["hit_tot"][m])
        clean = [nick(m) for m in idx if not c["hit_tot"][m]]
        return ("Most points lost to hits:\n\n" + "\n".join(f"- {nick(m)}: -{c['hit_tot'][m]}" for m in hs[:5] if c["hit_tot"][m])
                + (f"\n\nNo hits yet: {', '.join(clean)}" if clean else "")) if c["hit_tot"][hs[0]] else "Nobody has taken a hit yet."
    if has("chip"):
        cs = sorted(idx, key=lambda m: -c["chip_pts"][m]["total"])[:5]
        return "Best chips (Bench Boost + Free Hit + Triple Captain points):\n\n" + "\n".join(
            f"- {nick(m)}: {c['chip_pts'][m]['total']} pts" for m in cs)
    if has("prize", "money", "rwf", "pot", "amafaranga"):
        es = sorted(idx, key=lambda m: -c["earn"][m])
        return (f"Pot: {fmt(S.POT_TOTAL)} RWF · {fmt(S.GW_PRIZE)} RWF per gameweek · top 4 at the end: "
                f"{', '.join(fmt(p) for p in S.CLASSIC_PRIZES)} RWF.\n\nPrize money if the season ended today:\n\n"
                + "\n".join(f"- {nick(m)}: {fmt(c['earn'][m])} RWF" for m in es if c["earn"][m]))
    if has("deadline"):
        d = c["D"]
        return f"Next deadline: GW{d['next_gw']} at {d['deadline'].replace('T', ' ').replace('Z', '')} UTC." if d["deadline"] else "No upcoming deadline."
    if has("standing", "table", "ranking", "rank", "top", "lead", "first", "1st", "winning", "uyoboye", "amanota", "points"):
        n = 20 if has("all", "full", "whole") else 10
        return "Current standings:\n\n" + "\n".join(
            f"{M[m]['rank']}. **{nick(m)}** - {M[m]['total']} pts" + (f" ({M[leader]['total'] - M[m]['total']} behind)" if m != leader else "")
            for m in c["order"][:n]) + ("" if n == 20 else "\n\n*Ask for the \"full table\" to see everyone.*")
    return "Sorry, I didn't get that. " + HELP


HELP = ("I can answer questions like:\n\n"
        "- *League summary* · *Who is leading?* · *Full table* · *Who is last?*\n"
        "- *All GW winners* · *Winners GW1 to GW5* · *Who has the most GW wins?*\n"
        "- *GW3 scores* · *Live scores* · *Biggest movers*\n"
        "- *How is Axel doing?* · *Philly GW3* · *Axel vs Pacifique*\n"
        "- *Most hits* · *Best chips* · *Prize money* · *Next deadline*")
