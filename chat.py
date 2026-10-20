"""League chatbot: Google Gemini (free tier) answers from the league data; a simple built-in bot answers if
there is no API key or the free daily limit has run out."""
import re

import requests
import streamlit as st

import settings as S

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"


def api_key():
    try:
        return st.secrets.get("GEMINI_API_KEY")
    except Exception:  # no secrets file at all
        return None


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
Keep answers short (a few sentences or a small list). Call managers by their nickname. Money is in RWF.
Reply in the same language as the question (for example English, Kinyarwanda or French).
Light banter about the league is fine, but stay kind.

{data}"""


def ask_gemini(question, history, c):
    """Returns the answer text, or None if Gemini can't be used right now (no key, limit reached, error)."""
    key = api_key()
    if not key:
        return None
    contents = [{"role": "user" if r == "user" else "model", "parts": [{"text": t}]} for r, t in history[-8:]]
    contents.append({"role": "user", "parts": [{"text": question}]})
    body = {"system_instruction": {"parts": [{"text": SYSTEM.format(league=S.LEAGUE_NAME, data=league_text(c))}]},
            "contents": contents}
    for model in S.CHAT_MODELS:   # each model has its own free daily limit, so try the next one if one is used up
        try:
            r = requests.post(GEMINI_URL.format(model), json=body, headers={"x-goog-api-key": key}, timeout=40)
            if r.status_code != 200:
                continue
            parts = r.json()["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
            if text:
                return text
        except Exception:
            continue
    return None


# ---------------------------------------------------------------- simple built-in bot (no AI, always free)
def find_managers(q, c):
    M = c["M"]
    found = []
    for m in c["order"]:
        words = {M[m]["nick"].lower()} | {w.lower() for w in M[m]["fpl"].split() if len(w) > 2}
        if any(re.search(rf"\b{re.escape(w)}\b", q) for w in words):
            found.append(m)
    return found


def simple_answer(question, c):
    q = question.lower()
    M, P, L, LV, live = c["M"], c["P"], c["L"], c["LV"], c["live"]
    nick = lambda m: M[m]["nick"]
    who = find_managers(q, c)
    gw = re.search(r"\b(?:gw|gameweek|game week)\s*(\d{1,2})\b", q)
    gw = int(gw.group(1)) if gw and 1 <= int(gw.group(1)) <= 38 else None
    has = lambda *ws: any(w in q for w in ws)

    if gw and who:
        lines = [f"**{nick(m)}** scored **{P(m, gw)}** pts in GW{gw}" if P(m, gw) is not None else f"{nick(m)} has no score for GW{gw} yet"
                 for m in who]
        return "\n\n".join(lines)
    if gw or has("won", "winner", "win ") and has("gw", "gameweek", "week"):
        g = gw or LV
        w = c["winners"][g - 1] if g else []
        if not w:
            return f"GW{g} has no scores yet."
        tag = " (live, can still change)" if live and g == LV else ""
        return f"GW{g} winner{'s' if len(w) > 1 else ''}: **{', '.join(nick(m) for m in w)}** with {c['top'][g - 1]} pts{tag}."
    if who and has("prize", "money", "rwf", "earn", "won"):
        return "\n\n".join(f"**{nick(m)}** would have **{fmt(c['earn'][m])} RWF** if the season ended today "
                           f"({c['wins'][m]:g} GW win(s))." for m in who)
    if who and has("chip"):
        return "\n\n".join(f"**{nick(m)}** chips: {', '.join(c['chip_pts'][m]['used']) or 'none played yet'}." for m in who)
    if who and has("hit", "kwikatisha"):
        return "\n\n".join(f"**{nick(m)}** has lost **{c['hit_tot'][m]}** pts to hits." for m in who)
    if who:
        return "\n\n".join(f"**{nick(m)}** ({M[m]['team']}) is **#{M[m]['rank']}** with **{M[m]['total']}** pts, "
                           f"{c['wins'][m]:g} GW win(s), {fmt(c['earn'][m])} RWF in prizes so far." for m in who)
    if has("hit", "kwikatisha"):
        hs = sorted(c["idx"], key=lambda m: -c["hit_tot"][m])[:5]
        return "Most points lost to hits:\n\n" + "\n".join(f"- {nick(m)}: -{c['hit_tot'][m]}" for m in hs if c["hit_tot"][m]) \
            if c["hit_tot"][hs[0]] else "Nobody has taken a hit yet."
    if has("chip"):
        cs = sorted(c["idx"], key=lambda m: -c["chip_pts"][m]["total"])[:5]
        return "Best chips (Bench Boost + Free Hit + Triple Captain points):\n\n" + "\n".join(
            f"- {nick(m)}: {c['chip_pts'][m]['total']} pts" for m in cs)
    if has("prize", "money", "rwf", "pot"):
        es = sorted(c["idx"], key=lambda m: -c["earn"][m])[:5]
        return f"Pot: {fmt(S.POT_TOTAL)} RWF. Prize money if the season ended today:\n\n" + "\n".join(
            f"- {nick(m)}: {fmt(c['earn'][m])} RWF" for m in es if c["earn"][m])
    if has("deadline"):
        d = c["D"]
        return f"Next deadline: GW{d['next_gw']} at {d['deadline'].replace('T', ' ').replace('Z', '')} UTC." if d["deadline"] else "No upcoming deadline."
    if has("standing", "table", "ranking", "top", "lead", "first", "1st", "winning"):
        return "Current standings:\n\n" + "\n".join(f"{M[m]['rank']}. {nick(m)} - {M[m]['total']} pts" for m in c["order"][:10])
    return ("I'm the simple bot, so I only understand a few kinds of questions. Try:\n\n"
            "- *Who is leading?*\n- *Who won GW5?*\n- *How is Axel doing?*\n- *Philly GW3*\n"
            "- *Who took the most hits?*\n- *Best chips*\n- *Prize money*\n- *Next deadline*")
