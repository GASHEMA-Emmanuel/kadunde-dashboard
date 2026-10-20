"""Data layer: everything comes from the official Fantasy Premier League API."""
import concurrent.futures as cf
import requests
import streamlit as st

BASE = "https://fantasy.premierleague.com/api/"
_session = requests.Session()
_session.headers.update({"User-Agent": "Mozilla/5.0 (Kadunde dashboard)"})


def get(path):
    r = _session.get(BASE + path, timeout=25)
    r.raise_for_status()
    return r.json()


def _pmap(fn, items, workers=10):
    with cf.ThreadPoolExecutor(workers) as ex:
        return list(ex.map(fn, items))


def live_scores(gw, bs, entries, fixtures):
    """Live points for a gameweek in progress: provisional bonus + auto-subs + vice-captain.
    Same method LiveFPL uses; official FPL only adds these after matches are confirmed."""
    pos = {p["id"]: p["element_type"] for p in bs["elements"]}
    team = {p["id"]: p["team"] for p in bs["elements"]}
    live = {e["id"]: e["stats"] for e in get(f"event/{gw}/live/")["elements"]}

    prov, tstat = {}, {}
    for f in fixtures:
        for t in (f["team_h"], f["team_a"]):
            s = tstat.setdefault(t, {"n": 0, "done": 0})
            s["n"] += 1
            s["done"] += 1 if (f["finished"] or f["finished_provisional"]) else 0
        if not f["started"]:
            continue
        stats = {s["identifier"]: s for s in f["stats"]}
        if stats.get("bonus") and (stats["bonus"]["a"] or stats["bonus"]["h"]):
            continue  # official bonus already included
        bps = stats.get("bps")
        if not bps:
            continue
        rows = sorted(bps["a"] + bps["h"], key=lambda x: -x["value"])
        given = 0
        for v in sorted({r["value"] for r in rows}, reverse=True):
            if given >= 3:
                break
            tied = [r for r in rows if r["value"] == v]
            for r in tied:
                prov[r["element"]] = prov.get(r["element"], 0) + [3, 2, 1][given]
            given += len(tied)

    def done(el):
        s = tstat.get(team.get(el))
        return s is None or s["done"] == s["n"]

    def mins(el):
        return live[el]["minutes"] if el in live else 0

    def pts(el):
        return (live[el]["total_points"] if el in live else 0) + prov.get(el, 0)

    def one(entry):
        try:
            pk = get(f"entry/{entry}/event/{gw}/picks/")
        except Exception:
            return entry, None
        chip, picks = pk["active_chip"], pk["picks"]
        xi = [p for p in picks if p["position"] <= 11]
        bench = [p for p in picks if p["position"] > 11]
        if chip == "bboost":
            side = xi + bench
        else:
            used = set()
            for i, p in enumerate(list(xi)):
                if mins(p["element"]) > 0 or not done(p["element"]):
                    continue
                for b in bench:
                    if b["element"] in used or mins(b["element"]) == 0:
                        continue
                    if (pos[b["element"]] == 1) != (pos[p["element"]] == 1):
                        continue
                    trial = [q for q in xi if q is not xi[i]] + [b]
                    c = lambda t: sum(1 for q in trial if pos[q["element"]] == t)
                    if c(1) == 1 and c(2) >= 3 and c(3) >= 2 and c(4) >= 1:
                        used.add(b["element"])
                        xi[i] = b
                        break
            side = xi
        cap = next((p for p in picks if p["is_captain"]), None)
        vc = next((p for p in picks if p["is_vice_captain"]), None)
        cap_el = cap["element"] if cap else None
        if cap_el and mins(cap_el) == 0 and done(cap_el) and vc:
            cap_el = vc["element"]
        mult = 3 if chip == "3xc" else 2
        total = sum(pts(p["element"]) * (mult if p["element"] == cap_el else 1) for p in side)
        eh = pk["entry_history"]
        return entry, {"live": total, "official": eh["points"], "hits": eh["event_transfers_cost"]}

    return {e: v for e, v in _pmap(one, entries) if v}


@st.cache_data(ttl=110, show_spinner="Fetching the latest FPL data...")
def load_league(league_id):
    bs = get("bootstrap-static/")
    events = bs["events"][:38]
    results, page = [], 1
    while True:
        d = get(f"leagues-classic/{league_id}/standings/?page_standings={page}")
        results += d["standings"]["results"]
        if not d["standings"]["has_next"]:
            break
        page += 1
    histories = _pmap(lambda r: get(f"entry/{r['entry']}/history/"), results)

    managers = []
    for r, h in zip(results, histories):
        p, hits = [None] * 38, [0] * 38
        for c in h["current"]:
            if 1 <= c["event"] <= 38:
                p[c["event"] - 1] = c["points"]
                hits[c["event"] - 1] = c["event_transfers_cost"]
        managers.append({
            "entry": r["entry"], "fpl": r["player_name"],
            "team": r["entry_name"].replace("\ufffd", "").strip(),
            "rank": r["rank"], "total": r["total"], "pts": p, "hits": hits,
            "chips": [{"chip": c["name"], "gw": c["event"]} for c in h["chips"]],
        })

    cur = next((e for e in events if e["is_current"]), None)
    nxt = next((e for e in events if e["is_next"]), None)
    live_ok = False
    cur_done = bool(cur["finished"]) if cur else True
    if cur and not cur["finished"]:
        # FPL only marks a gameweek finished after its final processing, often a day after the last match.
        # Treat it as finished as soon as every match has ended with bonus points confirmed.
        try:
            fixtures = get(f"fixtures/?event={cur['id']}")
            cur_done = bool(fixtures) and all(f["finished"] for f in fixtures)
            lv = live_scores(cur["id"], bs, [m["entry"] for m in managers], fixtures)
            g = cur["id"] - 1
            for m in managers:
                l = lv.get(m["entry"])
                if l:
                    m["total"] = m["total"] - l["official"] + l["live"]
                    m["pts"][g], m["hits"][g] = l["live"], l["hits"]
            managers.sort(key=lambda m: (-m["total"], m["rank"]))
            for i, m in enumerate(managers):
                m["rank"] = i + 1
            live_ok = True
        except Exception:
            pass  # fall back to official points

    return {
        "managers": managers,
        "finished": [bool(e["finished"]) or (cur_done and e["id"] == cur["id"]) for e in events],
        "current_gw": cur["id"] if cur else 0,
        "current_finished": cur_done,
        "next_gw": nxt["id"] if nxt else None,
        "deadline": nxt["deadline_time"] if nxt else None,
        "live_calc": live_ok,
    }
