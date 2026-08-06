#!/usr/bin/env python3
"""
AnBBL Statistics Crawler
=========================

Crawls https://www.anarchy.bloodbowlleague.net/ by walking every match
report (?p=m&m=N) rather than per-team pages. This is the key design
decision: a team's row in the final standings is built ENTIRELY from the
match records it appears in, never from that team's own team page. That
means a deleted/renamed/retired team still ends up with a correct,
complete row in the standings, because every match it ever played still
exists as an independent match report referencing it by name (and, if
still alive, by id).

This directly avoids the bug Ketil hit with the old crawler, where a
deleted team's page 404ing corrupted the whole run.

Usage:
    python3 crawl.py                       # crawl everything, resume-safe
    python3 crawl.py --start 1 --end 500   # crawl a specific match-id range
    python3 crawl.py --delay 0.15          # adjust politeness delay (seconds)
    python3 crawl.py --refresh-teams       # also re-fetch ?p=te for current
                                            # race/coach/TV enrichment of teams
                                            # that are still active

Output (in ./data/):
    matches_raw/*.html   - cached raw HTML per match id (so re-runs are fast
                            and don't re-hit the site; delete to force refetch)
    matches.json         - parsed match records
    teams.json           - aggregated per-team standings
    crawl_log.txt        - every skipped/error match id with a reason

Then run `python3 build_site.py` to turn data/teams.json + matches.json
into an offline HTML statistics site (no server, no domain needed - just
open the .html file in a browser).
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import urllib.parse

BASE = "https://www.anarchy.bloodbowlleague.net/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RAW_DIR = os.path.join(DATA_DIR, "matches_raw")


def fetch(url, retries=3, timeout=20):
    """Fetch a URL as UTF-8 text (site is served as Windows-1252 despite
    claiming iso-8859-1 in its meta tag; decode leniently)."""
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                return raw.decode("windows-1252", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url} after {retries} tries: {last_err}")


def fetch_match_cached(match_id, delay):
    """Fetch (or load from cache) the raw HTML of a match report."""
    path = os.path.join(RAW_DIR, f"{match_id}.html")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    url = f"{BASE}default.asp?p=m&m={match_id}"
    html = fetch(url)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    time.sleep(delay)
    return html


TEAM_BLOCK_RE = re.compile(
    r'<a href="default\.asp\?p=tm&t=([^"]+)">(?:(?!</?a\b).)*?<b>([^<]+)</b></a>',
    re.S,
)
NO_LINK_TEAM_RE = re.compile(r'<br><b>([^<]+)</b></a>')
TD_SCORE_RE = re.compile(
    r'<td[^>]*><b>(\d+)</b></td>\s*<td[^>]*>TD score</td>\s*<td[^>]*><b>(\d+)</b></td>'
)
CAS_SCORE_RE = re.compile(
    r'<td[^>]*class="small"[^>]*>(\d+)<br><span[^>]*>&nbsp;\((\d+)\)</span></td>\s*'
    r'<td[^>]*class="small"[^>]*>cas score.*?</td>\s*'
    r'<td[^>]*class="small"[^>]*>(\d+)<br><span[^>]*>\((\d+)\)&nbsp;</span></td>',
    re.S,
)
GATE_RE = re.compile(r'gate:\s*<b>(.*?)</b>', re.S)
TOURNEY_RE = re.compile(
    r'<div[^>]*><b><a href="default\.asp\?p=ma&so=s&s=(\d+)">([^<]+)</a>,?\s*([^<]*)</b></div>'
)


def parse_match(match_id, html):
    """Parse a single match report page. Returns a dict, or None if this
    match id doesn't exist / isn't a valid result (gets logged & skipped)."""
    if "<h1>Match result</h1>" not in html:
        return None, "not a match-result page (invalid/removed id)"

    tourney = TOURNEY_RE.search(html)
    tournament_id = tourney.group(1) if tourney else None
    tournament_name = (tourney.group(2).strip() + (
        f", {tourney.group(3).strip()}" if tourney and tourney.group(3).strip() else ""
    )) if tourney else None

    # Team blocks: try linked (team page still exists) then unlinked
    # (deleted team - name-only). We need exactly two, home and away.
    linked = TEAM_BLOCK_RE.findall(html)
    teams = []
    if len(linked) >= 2:
        # Normal case: both teams have live pages
        teams = [{"id": tid, "name": name.strip()} for tid, name in linked[:2]]
    else:
        # Fallback: at least one team has no link (deleted). Grab all
        # "<br><b>Name</b></a>" occurrences in order, pairing ids where we can.
        linked_ids = {m.start(): m.groups() for m in TEAM_BLOCK_RE.finditer(html)}
        all_names = list(NO_LINK_TEAM_RE.finditer(html))
        if len(all_names) < 2:
            return None, "could not find two team names"
        # Use the first two occurrences of the name pattern in document order;
        # cross-reference with linked matches by name to recover an id if present.
        linked_by_name = {name.strip(): tid for tid, name in linked}
        for m in all_names[:2]:
            name = m.group(1).strip()
            teams.append({"id": linked_by_name.get(name), "name": name})

    if len(teams) != 2:
        return None, "did not resolve exactly two teams"

    td = TD_SCORE_RE.search(html)
    cas = CAS_SCORE_RE.search(html)
    gate = GATE_RE.search(html)

    if not td:
        return None, "no TD score found (likely a forfeit/void match)"

    td1, td2 = int(td.group(1)), int(td.group(2))
    if cas:
        cas1, kills1, cas2, kills2 = (
            int(cas.group(1)), int(cas.group(2)), int(cas.group(3)), int(cas.group(4))
        )
    else:
        cas1 = cas2 = kills1 = kills2 = 0

    gate_val = None
    if gate:
        digits = re.sub(r"<[^>]+>", "", gate.group(1))
        digits = re.sub(r"\D", "", digits)
        gate_val = int(digits) if digits else None

    return {
        "match_id": match_id,
        "tournament_id": tournament_id,
        "tournament": tournament_name,
        "gate": gate_val,
        "home": {**teams[0], "td": td1, "cas": cas1, "kills": kills1},
        "away": {**teams[1], "td": td2, "cas": cas2, "kills": kills2},
    }, None


TEAM_ROW_RE = re.compile(r'<tr class="trlist" height="30">(.*?)</tr>', re.S)
TEAM_ID_RE = re.compile(r"t=([^'\"&]+)['\"&]")
TEAM_TD_RE = re.compile(r'<td class="td1[01]"[^>]*>(.*?)</td>', re.S)
DATE_ROW_RE = re.compile(
    r'<tr title="result added ([^"]+)"\s*class="trlist" '
    r"onclick=\"self\.location\.href='default\.asp\?p=m&m=(\d+)';\""
)
YEAR_RE = re.compile(r"(\d{4})")


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s).replace("&nbsp;", " ").strip()


def fetch_team_meta():
    """Fetch ?p=te (current active team list) for id -> {name, race, coach, tv}.
    Only covers teams that are still active/undeleted."""
    html = fetch(f"{BASE}default.asp?p=te")
    meta = {}
    for block_match in TEAM_ROW_RE.finditer(html):
        block = block_match.group(1)
        id_match = TEAM_ID_RE.search(block)
        if not id_match:
            continue
        tid = id_match.group(1)
        tds = TEAM_TD_RE.findall(block)
        if len(tds) < 4:
            continue
        name = strip_tags(tds[0])
        race = strip_tags(tds[1])
        coach = strip_tags(tds[2])
        tv = strip_tags(tds[3])
        meta[tid] = {"name": name, "race": race, "coach": coach, "tv": tv}
    return meta


def fetch_team_match_dates(team_id, delay, cache_dir):
    """Fetch a single (still-active) team's match-history page and return
    {match_id: 'Month Day, Year'} for every match it played. Used purely to
    backfill dates onto match records that otherwise have none."""
    path = os.path.join(cache_dir, f"{team_id}.html")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            html = f.read()
    else:
        url = f"{BASE}default.asp?p=ma&so=t&t={urllib.parse.quote(team_id, encoding='cp1252')}"
        html = fetch(url)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        time.sleep(delay)
    return {mid: date for date, mid in DATE_ROW_RE.findall(html)}


PLAYER_ROW_RE = re.compile(
    r"<tr class=\"trlist\" height=\"23\" onclick=\"self\.location\.href='default\.asp\?p=pl&pid=(\d+)';\">(.*?)</tr>",
    re.S,
)
PLAYER_TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
PLAYER_NAME_POS_RE = re.compile(r"^(.*?)<div[^>]*>(.*?)</div>", re.S)
PLAYER_SPP_RE = re.compile(r"^(\d+)<div[^>]*>\((\d+)\)")


def fetch_team_roster(team_id, delay, cache_dir):
    """Fetch a single (still-active) team's roster page and return a list
    of its current (living) players with career stats. Dead/retired
    players live on a separate page and are naturally excluded here."""
    path = os.path.join(cache_dir, f"{team_id}.html")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            html = f.read()
    else:
        url = f"{BASE}default.asp?p=ro&t={urllib.parse.quote(team_id, encoding='cp1252')}"
        html = fetch(url)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        time.sleep(delay)

    players = []
    for pid, block in PLAYER_ROW_RE.findall(html):
        tds = PLAYER_TD_RE.findall(block)
        if len(tds) < 17:
            continue
        name_pos = PLAYER_NAME_POS_RE.match(tds[0])
        if not name_pos:
            continue
        name = strip_tags(name_pos.group(1))
        position = strip_tags(name_pos.group(2))
        try:
            interceptions = int(strip_tags(tds[10]) or 0)
            completions = int(strip_tags(tds[11]) or 0)
            touchdowns = int(strip_tags(tds[12]) or 0)
            casualties = int(strip_tags(tds[13]) or 0)
            mvps = int(strip_tags(tds[14]) or 0)
        except ValueError:
            continue
        spp_match = PLAYER_SPP_RE.match(tds[15])
        spp_total = int(spp_match.group(2)) if spp_match else 0
        value_digits = re.sub(r"\D", "", strip_tags(tds[16]))
        value = int(value_digits) * 1000 if value_digits else 0

        players.append({
            "pid": pid, "name": name, "position": position, "team_id": team_id,
            "interceptions": interceptions, "completions": completions,
            "touchdowns": touchdowns, "casualties": casualties, "mvps": mvps,
            "spp": spp_total, "value": value,
        })
    return players


def crawl_players(team_meta, delay, log_path):
    """Fetch every currently-active team's roster page and return a flat
    list of every living player in the league with career stats, for the
    league-wide "top players" leaderboards."""
    print("Player pass: fetching roster pages for every active team...")
    roster_cache_dir = os.path.join(DATA_DIR, "team_rosters_raw")
    os.makedirs(roster_cache_dir, exist_ok=True)

    all_players = []
    with open(log_path, "a", encoding="utf-8") as log:
        for i, tid in enumerate(team_meta, 1):
            try:
                players = fetch_team_roster(tid, delay, roster_cache_dir)
                all_players.extend(players)
            except Exception as e:
                log.write(f"players:{tid}\tFETCH_ERROR\t{type(e).__name__}: {e}\n")
            if i % 50 == 0:
                print(f"  ...{i}/{len(team_meta)} team rosters fetched")

    print(f"  -> {len(all_players)} living players found across {len(team_meta)} active teams")
    return all_players


TEAM_PAGE_COACH_RE = re.compile(
    r'Coach:</td>\s*<td[^>]*>&nbsp;<b><span[^>]*>([^<]*)</span></b>'
)
TEAM_PAGE_RACE_RE = re.compile(
    r'Race:</td>\s*<td[^>]*>&nbsp;<b><a[^>]*>([^<]*)</a></b>'
)


def fetch_team_page_meta(team_id, delay, cache_dir):
    """Fetch a single team's own page directly and pull Coach/Race straight
    from it. Unlike ?p=te (which only lists CURRENTLY ACTIVE teams), this
    works for any team whose page still resolves - including retired or
    inactive teams from past seasons that simply aren't competing right
    now. This is the fix for a coach who has run more than one team where
    only their current team was showing up: their older, inactive team's
    page still exists and still says who coached it, ?p=te just never
    listed it. Returns None if the page doesn't resolve to a real team
    (truly deleted/never existed)."""
    path = os.path.join(cache_dir, f"{team_id}.html")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            html = f.read()
    else:
        url = f"{BASE}default.asp?p=tm&t={urllib.parse.quote(team_id, encoding='cp1252')}"
        html = fetch(url)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        time.sleep(delay)

    coach_match = TEAM_PAGE_COACH_RE.search(html)
    if not coach_match:
        return None  # page didn't resolve to a real team - truly gone
    race_match = TEAM_PAGE_RACE_RE.search(html)
    return {
        "name": None,  # name already known from the match record itself
        "coach": strip_tags(coach_match.group(1)),
        "race": strip_tags(race_match.group(1)) if race_match else None,
        "tv": None,  # not meaningfully comparable for an inactive team
    }


COACH_SPLIT_RE = re.compile(r"\s*&\s*")


def parse_coaches(raw):
    """Split a raw coach field into individual coach names. Co-coached
    teams show as e.g. 'Kyrre& Helmelk' on the site - without this, that
    whole string gets treated as a third, separate coach identity, and
    both real people's stats fragment away from their solo-coached teams."""
    if not raw:
        return []
    return [name.strip() for name in COACH_SPLIT_RE.split(raw) if name.strip()]


def format_coaches(raw):
    """Tidy up the raw 'Kyrre& Helmelk' display string to 'Kyrre & Helmelk'."""
    names = parse_coaches(raw)
    return " & ".join(names) if names else raw


def enrich(matches, delay, log_path):
    """Second pass: backfill date/year onto matches, and attach current
    race/coach/tv onto teams, using data only available from currently-live
    team pages. Matches between two now-deleted teams simply won't get a
    date - that's a hard limit of the source site, not a bug here."""
    print("Enrichment pass: fetching current team list (?p=te)...")
    team_meta = fetch_team_meta()
    print(f"  -> {len(team_meta)} active teams found")

    date_cache_dir = os.path.join(DATA_DIR, "team_dates_raw")
    os.makedirs(date_cache_dir, exist_ok=True)

    match_dates = {}
    with open(log_path, "a", encoding="utf-8") as log:
        for i, tid in enumerate(team_meta, 1):
            try:
                dates = fetch_team_match_dates(tid, delay, date_cache_dir)
                match_dates.update(dates)
            except Exception as e:
                log.write(f"enrich:{tid}\tFETCH_ERROR\t{type(e).__name__}: {e}\n")
            if i % 50 == 0:
                print(f"  ...{i}/{len(team_meta)} teams' match histories fetched")

    n_dated = 0

    # Third pass: any team_id that shows up in a match but wasn't in the
    # ?p=te active list (i.e. it's retired/inactive, not truly deleted -
    # its own page still resolves) still deserves a shot at coach/race,
    # fetched directly from that team's own page. Without this, a coach
    # who has run more than one team over the years would only show up
    # attached to whichever of their teams happens to still be active.
    missing_ids = set()
    for m in matches:
        for side in ("home", "away"):
            tid = m[side]["id"]
            if tid and tid not in team_meta:
                missing_ids.add(tid)

    if missing_ids:
        print(f"Fallback pass: {len(missing_ids)} teams not in the active list, "
              f"fetching their own pages directly for coach/race...")
        fallback_cache_dir = os.path.join(DATA_DIR, "team_pages_raw")
        os.makedirs(fallback_cache_dir, exist_ok=True)
        n_recovered = 0
        with open(log_path, "a", encoding="utf-8") as log:
            for i, tid in enumerate(sorted(missing_ids), 1):
                try:
                    meta = fetch_team_page_meta(tid, delay, fallback_cache_dir)
                    if meta:
                        team_meta[tid] = meta
                        n_recovered += 1
                    else:
                        log.write(f"fallback:{tid}\tNO_MATCH\tpage did not resolve to a team\n")
                except Exception as e:
                    log.write(f"fallback:{tid}\tFETCH_ERROR\t{type(e).__name__}: {e}\n")
                if i % 50 == 0:
                    print(f"  ...{i}/{len(missing_ids)} fallback team pages fetched")
        print(f"  -> recovered coach/race for {n_recovered}/{len(missing_ids)} "
              f"inactive-but-resolvable teams")

    for m in matches:
        mid = str(m["match_id"])
        date = match_dates.get(mid)
        if date:
            m["date"] = date
            year_match = YEAR_RE.search(date)
            m["year"] = year_match.group(1) if year_match else None
            n_dated += 1
        else:
            m["date"] = None
            m["year"] = None
        for side in ("home", "away"):
            meta = team_meta.get(m[side]["id"]) if m[side]["id"] else None
            if meta:
                m[side]["coach"] = meta["coach"]
                m[side]["coaches"] = parse_coaches(meta["coach"])
                m[side]["race"] = meta["race"]
            else:
                m[side]["coach"] = None
                m[side]["coaches"] = []
                m[side]["race"] = None

    print(f"  -> backfilled dates on {n_dated}/{len(matches)} matches "
          f"({len(matches) - n_dated} involve two now-deleted teams, no date available)")
    return matches, team_meta


def discover_max_match_id():
    """Look at the homepage's 'latest matches' list to find the current
    highest match id, so we know where to stop."""
    html = fetch(BASE)
    ids = [int(m) for m in re.findall(r"p=m&m=(\d+)", html)]
    if not ids:
        raise RuntimeError("Could not discover any match ids from homepage")
    return max(ids)


def crawl(start, end, delay, log_path):
    os.makedirs(RAW_DIR, exist_ok=True)
    matches = []
    skipped = 0
    with open(log_path, "a", encoding="utf-8") as log:
        for match_id in range(start, end + 1):
            try:
                html = fetch_match_cached(match_id, delay)
            except RuntimeError as e:
                log.write(f"{match_id}\tFETCH_ERROR\t{e}\n")
                skipped += 1
                continue
            record, err = parse_match(match_id, html)
            if err:
                log.write(f"{match_id}\tSKIPPED\t{err}\n")
                skipped += 1
                continue
            matches.append(record)
            if match_id % 50 == 0:
                print(f"  ...match {match_id}/{end} ({len(matches)} parsed, {skipped} skipped)")
    return matches


def _blank_totals():
    return {
        "gp": 0, "w": 0, "d": 0, "l": 0,
        "td_for": 0, "td_against": 0,
        "cas_for": 0, "cas_against": 0,
        "kills_for": 0,
    }


def _apply_result(totals, side, opp, is_home):
    totals["gp"] += 1
    totals["td_for"] += side["td"]; totals["td_against"] += opp["td"]
    totals["cas_for"] += side["cas"]; totals["cas_against"] += opp["cas"]
    totals["kills_for"] += side["kills"]
    if side["td"] > opp["td"]:
        totals["w"] += 1
    elif side["td"] < opp["td"]:
        totals["l"] += 1
    else:
        totals["d"] += 1


def _finalize(totals):
    gp = totals["gp"]
    perf = (totals["w"] + 0.5 * totals["d"]) / gp * 100 if gp else 0.0
    points = 5 * totals["w"] + 3 * totals["d"] + 1 * totals["l"]
    return {
        **totals,
        "points": points,
        "performance_pct": round(perf, 2),
        "td_diff": totals["td_for"] - totals["td_against"],
        "cas_diff": totals["cas_for"] - totals["cas_against"],
    }


def aggregate_teams(matches, team_meta=None):
    """Build a per-team-id (falling back to name for id-less/deleted teams)
    standings table purely from match records, plus a year-by-year
    breakdown of the same, for every match that has a backfilled date."""
    team_meta = team_meta or {}
    teams = {}

    def key_for(side):
        return side["id"] if side["id"] else f"name:{side['name']}"

    def ensure(side):
        k = key_for(side)
        if k not in teams:
            teams[k] = {
                "id": side["id"],
                "name": side["name"],
                "coach": None,
                "race": None,
                "deleted": side["id"] is None,
                "tournaments": set(),
                "all": _blank_totals(),
                "by_year": {},
            }
        teams[k]["name"] = side["name"]  # keep most recently seen name
        if side.get("coach"):
            teams[k]["coach"] = side["coach"]
        if side.get("race"):
            teams[k]["race"] = side["race"]
        return teams[k]

    for m in matches:
        home, away = m["home"], m["away"]
        th, ta = ensure(home), ensure(away)
        _apply_result(th["all"], home, away, True)
        _apply_result(ta["all"], away, home, False)
        if m.get("year"):
            y = m["year"]
            th["by_year"].setdefault(y, _blank_totals())
            ta["by_year"].setdefault(y, _blank_totals())
            _apply_result(th["by_year"][y], home, away, True)
            _apply_result(ta["by_year"][y], away, home, False)
        if m["tournament"]:
            th["tournaments"].add(m["tournament"])
            ta["tournaments"].add(m["tournament"])

    out = []
    for k, t in teams.items():
        # Fall back onto the live ?p=te listing for coach/race if a team
        # never had it attached via a match side (shouldn't normally
        # happen, but belt-and-braces for active teams with 0 dated matches)
        meta = team_meta.get(t["id"]) if t["id"] else None
        coach = t["coach"] or (meta["coach"] if meta else None)
        race = t["race"] or (meta["race"] if meta else None)
        tv = meta["tv"] if meta else None  # only known for currently-active teams
        out.append({
            "id": t["id"],
            "name": t["name"],
            "coach": coach,
            "coaches": parse_coaches(coach),
            "race": race,
            "tv": tv,
            "deleted": t["deleted"],
            "tournaments": sorted(t["tournaments"]),
            "all": _finalize(t["all"]),
            "by_year": {y: _finalize(v) for y, v in t["by_year"].items()},
        })
    out.sort(key=lambda r: (-r["all"]["points"], -r["all"]["performance_pct"], -r["all"]["gp"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=None,
                     help="Defaults to auto-discovered current max match id")
    ap.add_argument("--delay", type=float, default=0.2,
                     help="Seconds to sleep between fresh (non-cached) requests")
    ap.add_argument("--skip-enrich", action="store_true",
                     help="Skip the date/coach/race backfill pass (faster, but no year "
                          "breakdown or coach info in the output)")
    ap.add_argument("--skip-players", action="store_true",
                     help="Skip crawling every active team's roster page for player "
                          "stats (faster, but no 'top players' leaderboards in the output)")
    args = ap.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    log_path = os.path.join(DATA_DIR, "crawl_log.txt")
    open(log_path, "w").close()  # truncate

    end = args.end
    if end is None:
        print("Discovering current max match id from homepage...")
        end = discover_max_match_id()
        print(f"  -> crawling matches {args.start}..{end}")

    matches = crawl(args.start, end, args.delay, log_path)
    print(f"Parsed {len(matches)} matches ({end - args.start + 1 - len(matches)} skipped, see crawl_log.txt)")

    team_meta = {}
    if not args.skip_enrich:
        matches, team_meta = enrich(matches, args.delay, log_path)
    else:
        for m in matches:
            m["date"] = None
            m["year"] = None
            for side in ("home", "away"):
                m[side]["coach"] = None
                m[side]["coaches"] = []
                m[side]["race"] = None

    with open(os.path.join(DATA_DIR, "matches.json"), "w", encoding="utf-8") as f:
        json.dump(matches, f, ensure_ascii=False, indent=1)

    teams = aggregate_teams(matches, team_meta)
    with open(os.path.join(DATA_DIR, "teams.json"), "w", encoding="utf-8") as f:
        json.dump(teams, f, ensure_ascii=False, indent=1)

    print(f"Aggregated {len(teams)} teams -> data/teams.json")

    if not args.skip_players:
        if not team_meta:
            # need the active team list even if --skip-enrich was passed
            team_meta = fetch_team_meta()
        players = crawl_players(team_meta, args.delay, log_path)
        with open(os.path.join(DATA_DIR, "players.json"), "w", encoding="utf-8") as f:
            json.dump(players, f, ensure_ascii=False, indent=1)
        print(f"Wrote {len(players)} players -> data/players.json")

    print("Now run: python3 build_site.py")


if __name__ == "__main__":
    main()
