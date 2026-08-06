#!/usr/bin/env python3
"""
Builds the AnBBL statistics widget from data/teams.json and data/matches.json.

Produces TWO files in output/:
  index.html  - a full standalone HTML page. Open directly in a browser,
                no server or domain needed.
  embed.html  - just the widget itself (no <!DOCTYPE>/<html>/<head>), with
                every CSS rule scoped under #abst-root and every element id
                prefixed with "abst-". Safe to paste into the live site's
                own "raw HTML" content editor (e.g. Statistics page) without
                its styles leaking onto the rest of the site or its ids
                colliding with anything already on that page.

Usage:
    python3 build_site.py
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

# Every rule here is written as "#abst-root <selector>" (or just "#abst-root"
# for the root itself) specifically so this can be pasted into someone
# else's page without touching anything outside the widget.
STYLE = """
#abst-root { font-family: -apple-system, Segoe UI, Arial, sans-serif; background:#1a1a1a; color:#e0e0e0; padding:10px; box-sizing:border-box; font-size:13px; }
#abst-root * { box-sizing:border-box; }
#abst-root h1 { font-weight:600; margin:0 0 4px; font-size:18px; }
#abst-root .meta { color:#999; font-size:11px; margin-bottom:0.8em; line-height:1.4; }
#abst-root .controls { display:flex; gap:8px; align-items:center; margin-bottom:8px; flex-wrap:wrap; }
#abst-root input#abst-filter, #abst-root select#abst-year, #abst-root select#abst-coachSelect {
  padding:4px 6px; font-size:12px; background:#2a2a2a; border:1px solid #444; color:#eee; border-radius:4px; }
#abst-root input#abst-filter { width:180px; max-width:45vw; }
#abst-root select#abst-year, #abst-root select#abst-coachSelect { cursor:pointer; max-width:130px; }
#abst-root label.col-toggle { font-size:11px; color:#bbb; display:flex; align-items:center; gap:4px; cursor:pointer; white-space:nowrap; }
#abst-root .coach-summary { display:none; background:#242424; border:1px solid #3a3a3a; border-radius:6px;
                     padding:8px 10px; margin-bottom:8px; font-size:11px; color:#ddd; }
#abst-root .coach-summary b { color:#f0c060; }
#abst-root .coach-summary span { margin-right:12px; }
#abst-root table { border-collapse:collapse; width:100%; font-size:11px; table-layout:fixed; }
#abst-root.show-extra table { table-layout:auto; width:max-content; min-width:100%; }
#abst-root th, #abst-root td { padding:3px 4px; text-align:center; border-bottom:1px solid #333;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
#abst-root td.name { text-align:left; cursor:pointer; }
#abst-root td.name:hover { text-decoration:underline; }
#abst-root td.race { text-align:left; color:#bbb; }
#abst-root th[data-k="rank"], #abst-root td:nth-child(1) { width:5%; }
#abst-root th[data-k="name"], #abst-root td.name { width:26%; }
#abst-root th[data-k="coach"], #abst-root td.coach { width:20%; }
#abst-root th[data-k="gp"], #abst-root th[data-k="w"], #abst-root th[data-k="d"], #abst-root th[data-k="l"] { width:8%; }
#abst-root th[data-k="points"] { width:8%; }
#abst-root th[data-k="performance_pct"] { width:9%; }
#abst-root th.col-extra, #abst-root td.col-extra { display:none; }
#abst-root.show-extra th.col-extra, #abst-root.show-extra td.col-extra { display:table-cell; }
#abst-root td.coach { text-align:left; }
#abst-root .coach-link { color:#8fb4d9; cursor:pointer; }
#abst-root .coach-link:hover { text-decoration:underline; }
#abst-root td.team-link { text-align:left; color:#8fb4d9; cursor:pointer; }
#abst-root td.team-link:hover { text-decoration:underline; }
#abst-root th { cursor:pointer; background:#242424; user-select:none; }
#abst-root th:hover { background:#333; }
#abst-root th.active { color:#f0c060; }
#abst-root tr:nth-child(odd) td { background:#212121; }
#abst-root tr:hover td { background:#2c2c2c; }
#abst-root .deleted { color:#a06060; font-style:italic; }
#abst-root .pos { color:#6fbf73; }
#abst-root .neg { color:#c17b7b; }
#abst-root #abst-empty-note { color:#888; padding:14px 0; display:none; }
#abst-root .detail-panel { display:none; margin-top:22px; }
#abst-root .detail-panel h2 { font-size:15px; color:#f0c060; border-bottom:1px solid #333; padding-bottom:4px;
                       margin:26px 0 8px; }
#abst-root .info-box table { width:auto; min-width:240px; }
#abst-root .info-box th { text-align:left; background:#242424; font-weight:600; padding-right:16px; }
#abst-root .info-box td { text-align:left; }
#abst-root .info-box a { color:#8fb4d9; }
#abst-root .streak-cards { display:flex; gap:10px; flex-wrap:wrap; }
#abst-root .streak-card { background:#242424; border:1px solid #3a3a3a; border-radius:6px; padding:8px 14px;
                   min-width:120px; }
#abst-root .streak-card .num { font-size:20px; font-weight:600; color:#f0c060; }
#abst-root .streak-card .lbl { font-size:11px; color:#999; text-transform:uppercase; letter-spacing:0.03em; }
#abst-root .subtable { font-size:12px; }
#abst-root .table-scroll { overflow-x:auto; -webkit-overflow-scrolling:touch; }
#abst-root .no-data { color:#777; font-size:12px; font-style:italic; padding:6px 0; }
#abst-root .back-btn { display:none; margin-bottom:14px; padding:6px 14px; font-size:13px;
  background:#2a2a2a; border:1px solid #444; color:#eee; border-radius:4px; cursor:pointer; }
#abst-root .back-btn:hover { background:#333; }
#abst-root .nav-btn { margin-left:auto; padding:6px 14px; font-size:13px;
  background:#33291a; border:1px solid #6b4f1f; color:#f0c060; border-radius:4px; cursor:pointer; }
#abst-root .nav-btn:hover { background:#3d3120; }
#abst-root #abst-topPlayers { display:none; }
"""

BODY_TEMPLATE = """<div id="abst-root">
<h1>AnBBL &mdash; Team Statistics</h1>
<div class="meta">
  {n_teams} teams &middot; {n_matches} matches parsed &middot; built from live match reports
  (deleted/retired teams included, shown <span class="deleted">in italics</span>).
  Dates/coach/race are backfilled from currently-active teams only, so matches
  between two now-deleted teams still count in All-time but can't be placed in
  a specific year.
</div>
<div class="controls">
  <select id="abst-year"></select>
  <select id="abst-coachSelect"></select>
  <input id="abst-filter" placeholder="Filter by team, coach or race...">
  <label class="col-toggle"><input type="checkbox" id="abst-showExtra"> More columns</label>
  <button id="abst-topPlayersBtn" class="nav-btn">Top Players</button>
</div>
<div id="abst-listView">
<div id="abst-coachSummary" class="coach-summary"></div>
<div class="table-scroll">
<table id="abst-tbl">
<thead>
<tr>
  <th data-k="rank">#</th>
  <th data-k="name">Team</th>
  <th data-k="coach">Coach</th>
  <th data-k="race" class="col-extra">Race</th>
  <th data-k="gp">GP</th>
  <th data-k="w">W</th>
  <th data-k="d">D</th>
  <th data-k="l">L</th>
  <th data-k="points">Pts</th>
  <th data-k="performance_pct">Perf%</th>
  <th data-k="td_for" class="col-extra">TD+</th>
  <th data-k="td_against" class="col-extra">TD-</th>
  <th data-k="td_diff" class="col-extra">TD&Delta;</th>
  <th data-k="cas_for" class="col-extra">Cas+</th>
  <th data-k="cas_against" class="col-extra">Cas-</th>
  <th data-k="cas_diff" class="col-extra">Cas&Delta;</th>
  <th data-k="kills_for" class="col-extra">Kills</th>
</tr>
</thead>
<tbody></tbody>
</table>
</div>
<div id="abst-empty-note">No teams played in this period.</div>
</div>

<button id="abst-backBtn" class="back-btn">&larr; Back to list</button>

<div id="abst-topPlayers">
  <h1>AnBBL &mdash; All-time Top Players</h1>
  <div class="meta">
    {n_players} living players across every active team &middot; dead/retired players aren't included,
    since they no longer appear on any team's roster.
  </div>
</div>

<div id="abst-coachDetail" class="detail-panel">
  <h2>Streaks</h2>
  <div id="abst-streakCards" class="streak-cards"></div>

  <h2>Performance with race</h2>
  <div id="abst-withRaceTable"></div>

  <h2>Performance against race</h2>
  <div id="abst-againstRaceTable"></div>

  <h2>Performance against coach</h2>
  <div id="abst-againstCoachTable"></div>

  <h2>Games by weekday</h2>
  <div id="abst-weekdayTable"></div>

  <h2 id="abst-lastGamesHeading">Last games played</h2>
  <div id="abst-lastGamesTable"></div>
</div>

<div id="abst-teamDetail" class="detail-panel">
  <div id="abst-teamInfo" class="info-box"></div>

  <h2>Statistics</h2>
  <div id="abst-teamStats"></div>

  <h2>Streaks</h2>
  <div id="abst-teamStreakCards" class="streak-cards"></div>

  <h2 id="abst-teamGamesHeading">All games played</h2>
  <div id="abst-teamGamesTable"></div>
</div>
</div>
<script>
(function() {{
// periods: {{ "all": [rows...], "2024": [rows...], ... }} - each row is a
// flat object with all the sortable fields already computed in Python.
const periods = {periods_json};
const profiles = {profiles_json};
const root = document.getElementById('abst-root');
const yearSelect = document.getElementById('abst-year');
const years = Object.keys(periods).filter(k => k !== 'all').sort((a,b) => b.localeCompare(a));
const optAll = document.createElement('option');
optAll.value = 'all'; optAll.textContent = 'All-time'; yearSelect.appendChild(optAll);
years.forEach(y => {{
  const o = document.createElement('option');
  o.value = y; o.textContent = y === 'unknown' ? 'Unknown year' : y;
  yearSelect.appendChild(o);
}});

let sortState = {{k:'points', dir:-1}};
let currentPeriod = 'all';
let currentCoach = '';
let currentTeamKey = '';
let showTopPlayers = false;
const teamProfiles = {team_profiles_json};
const leaderboards = {leaderboards_json};
const leaderboardSpecs = {leaderboard_specs_json};

const coachSelect = document.getElementById('abst-coachSelect');
function rebuildCoachOptions() {{
  const coaches = Array.from(new Set(
    (periods[currentPeriod] || []).flatMap(r => r.coaches || [])
  )).sort((a, b) => a.localeCompare(b));
  coachSelect.innerHTML = '';
  const optAllC = document.createElement('option');
  optAllC.value = ''; optAllC.textContent = 'All coaches'; coachSelect.appendChild(optAllC);
  coaches.forEach(c => {{
    const o = document.createElement('option');
    o.value = c; o.textContent = c;
    coachSelect.appendChild(o);
  }});
  coachSelect.value = currentCoach && coaches.includes(currentCoach) ? currentCoach : '';
  currentCoach = coachSelect.value;
}}

function updateCoachSummary(rowsForCoach) {{
  const box = document.getElementById('abst-coachSummary');
  if (!currentCoach || !rowsForCoach.length) {{
    box.style.display = 'none';
    return;
  }}
  const sum = (k) => rowsForCoach.reduce((a, r) => a + r[k], 0);
  const gp = sum('gp'), w = sum('w'), d = sum('d'), l = sum('l');
  const perf = gp ? ((w + 0.5 * d) / gp * 100).toFixed(1) : '0.0';
  box.innerHTML = `<b>${{currentCoach}}</b> &mdash; `
    + `<span>${{rowsForCoach.length}} team(s)</span>`
    + `<span>GP ${{gp}}</span><span>W ${{w}}</span><span>D ${{d}}</span><span>L ${{l}}</span>`
    + `<span>Perf ${{perf}}%</span><span>Pts ${{sum('points')}}</span>`
    + `<span>TD ${{sum('td_for')}}-${{sum('td_against')}}</span>`
    + `<span>Cas ${{sum('cas_for')}}-${{sum('cas_against')}}</span>`
    + `<span>Kills ${{sum('kills_for')}}</span>`;
  box.style.display = 'block';
}}

function fmtCoach(raw) {{
  return raw ? raw.replace(/\\s*&\\s*/g, ' & ') : raw;
}}

function fmtDelta(v) {{
  return `<span class="${{v >= 0 ? 'pos' : 'neg'}}">${{v >= 0 ? '+' : ''}}${{v}}</span>`;
}}

function renderGroupTable(containerId, groups, labelHeader) {{
  const el = document.getElementById(containerId);
  const keys = Object.keys(groups);
  if (!keys.length) {{ el.innerHTML = '<div class="no-data">No data available.</div>'; return; }}
  const rows = keys.map(k => ({{label: k, ...groups[k]}})).sort((a, b) => b.gp - a.gp);
  let html = `<div class="table-scroll"><table class="subtable"><thead><tr>
    <th>${{labelHeader}}</th><th>GP</th><th>W</th><th>D</th><th>L</th><th>Perf%</th>
    <th>TD+</th><th>TD-</th><th>TD&Delta;</th><th>Cas+</th><th>Cas-</th><th>Cas&Delta;</th><th>Pts</th>
  </tr></thead><tbody>`;
  rows.forEach(r => {{
    html += `<tr><td style="text-align:left">${{r.label}}</td><td>${{r.gp}}</td><td>${{r.w}}</td>
      <td>${{r.d}}</td><td>${{r.l}}</td><td>${{r.performance_pct.toFixed(1)}}%</td>
      <td>${{r.td_for}}</td><td>${{r.td_against}}</td><td>${{fmtDelta(r.td_diff)}}</td>
      <td>${{r.cas_for}}</td><td>${{r.cas_against}}</td><td>${{fmtDelta(r.cas_diff)}}</td>
      <td>${{r.points}}</td></tr>`;
  }});
  html += '</tbody></table></div>';
  el.innerHTML = html;
}}

function renderStreaks(s, gamesDated) {{
  const el = document.getElementById('abst-streakCards');
  if (!gamesDated) {{ el.innerHTML = '<div class="no-data">No dated games available for this coach.</div>'; return; }}
  const typeName = {{W: 'win', D: 'draw', L: 'loss'}}[s.current_type] || '-';
  el.innerHTML = `
    <div class="streak-card"><div class="num">${{s.current_len}}</div><div class="lbl">Current ${{typeName}} streak</div></div>
    <div class="streak-card"><div class="num">${{s.longest_win}}</div><div class="lbl">Longest win streak</div></div>
    <div class="streak-card"><div class="num">${{s.longest_unbeaten}}</div><div class="lbl">Longest unbeaten streak</div></div>
    <div class="streak-card"><div class="num">${{s.longest_loss}}</div><div class="lbl">Longest loss streak</div></div>`;
}}

function renderLastGames(games) {{
  const el = document.getElementById('abst-lastGamesTable');
  document.getElementById('abst-lastGamesHeading').textContent =
    games.length ? `Last ${{games.length}} games played` : 'Last games played';
  if (!games.length) {{ el.innerHTML = '<div class="no-data">No dated games available for this coach.</div>'; return; }}
  let html = `<div class="table-scroll"><table class="subtable"><thead><tr>
    <th>Date</th><th>Team</th><th>Opponent</th><th>Result</th><th>Score</th><th>Cas</th><th>Tournament</th>
  </tr></thead><tbody>`;
  games.forEach(g => {{
    const res = g.own_td > g.opp_td ? 'W' : (g.own_td < g.opp_td ? 'L' : 'D');
    const cls = res === 'W' ? 'pos' : (res === 'L' ? 'neg' : '');
    html += `<tr><td>${{g.date || ''}}</td><td style="text-align:left">${{g.own_team}}</td>
      <td style="text-align:left">${{g.opp_team}}${{g.opp_coach ? ' (' + fmtCoach(g.opp_coach) + ')' : ''}}</td>
      <td class="${{cls}}">${{res}}</td><td>${{g.own_td}}-${{g.opp_td}}</td>
      <td>${{g.own_cas}}-${{g.opp_cas}}</td><td style="text-align:left">${{g.tournament || ''}}</td></tr>`;
  }});
  html += '</tbody></table></div>';
  el.innerHTML = html;
}}

function renderTeamInfo(p, row) {{
  const el = document.getElementById('abst-teamInfo');
  const rows = [
    ['Head coach', fmtCoach(row.coach) || '&mdash;'],
    ['Race', row.race || '&mdash;'],
    ['Team value', row.tv || '&mdash;'],
    ['First game', p.first_game || '&mdash;'],
    ['Last game', p.last_game || '&mdash;'],
    ['Games played', p.games_total],
  ];
  let html = '<table class="subtable"><tbody>';
  rows.forEach(([label, val]) => {{ html += `<tr><th>${{label}}</th><td>${{val}}</td></tr>`; }});
  html += '</tbody></table>';
  el.innerHTML = html;
}}

function renderTeamStats(s) {{
  const el = document.getElementById('abst-teamStats');
  if (!s.gp) {{ el.innerHTML = '<div class="no-data">No dated games available for this team.</div>'; return; }}
  const rows = [
    ['Games played', '', s.gp],
    ['Win', s.w_avg.toFixed(3), s.w],
    ['Tie', s.d_avg.toFixed(3), s.d],
    ['Loss', s.l_avg.toFixed(3), s.l],
    ['Performance', '', s.performance_pct.toFixed(2) + '%'],
    ['Touchdowns', '', (s.td_diff >= 0 ? '+' : '') + s.td_diff],
    ['&nbsp;&nbsp;For', s.td_for_avg.toFixed(2), s.td_for],
    ['&nbsp;&nbsp;Against', s.td_against_avg.toFixed(2), s.td_against],
    ['Casualties', '', (s.cas_diff >= 0 ? '+' : '') + s.cas_diff],
    ['&nbsp;&nbsp;For', s.cas_for_avg.toFixed(2), s.cas_for],
    ['&nbsp;&nbsp;Against', s.cas_against_avg.toFixed(2), s.cas_against],
    ['Kills (for-against)', `${{s.kills_for_avg.toFixed(2)}}-${{s.kills_against_avg.toFixed(2)}}`, `${{s.kills_for}}-${{s.kills_against}}`],
    ['Points', s.points_avg.toFixed(2), s.points],
  ];
  let html = '<div class="table-scroll"><table class="subtable"><thead><tr><th></th><th>Average</th><th>Total</th></tr></thead><tbody>';
  rows.forEach(([label, avg, total]) => {{
    html += `<tr><th style="text-align:left">${{label}}</th><td>${{avg}}</td><td>${{total}}</td></tr>`;
  }});
  html += '</tbody></table></div>';
  el.innerHTML = html;
}}

function renderTeamStreaks(s, gamesDated) {{
  const el = document.getElementById('abst-teamStreakCards');
  if (!gamesDated) {{ el.innerHTML = '<div class="no-data">No dated games available for this team.</div>'; return; }}
  const typeName = {{W: 'win', D: 'draw', L: 'loss'}}[s.current_type] || '-';
  el.innerHTML = `
    <div class="streak-card"><div class="num">${{s.current_len}}</div><div class="lbl">Current ${{typeName}} streak</div></div>
    <div class="streak-card"><div class="num">${{s.longest_win}}</div><div class="lbl">Win streak</div></div>
    <div class="streak-card"><div class="num">${{s.longest_loss}}</div><div class="lbl">Loss streak</div></div>
    <div class="streak-card"><div class="num">${{s.longest_kill}}</div><div class="lbl">Kill streak</div></div>`;
}}

function renderTeamGames(games) {{
  const el = document.getElementById('abst-teamGamesTable');
  document.getElementById('abst-teamGamesHeading').textContent =
    games.length ? `All ${{games.length}} games played` : 'All games played';
  if (!games.length) {{ el.innerHTML = '<div class="no-data">No dated games available for this team.</div>'; return; }}
  let html = `<div class="table-scroll"><table class="subtable"><thead><tr>
    <th>Date</th><th>Opponent</th><th>Race</th><th>Team</th><th>R</th><th>Score</th><th>Cas</th><th>Tournament</th>
  </tr></thead><tbody>`;
  games.forEach(g => {{
    const res = g.own_td > g.opp_td ? 'W' : (g.own_td < g.opp_td ? 'L' : 'D');
    const cls = res === 'W' ? 'pos' : (res === 'L' ? 'neg' : '');
    html += `<tr><td>${{g.date || ''}}</td><td style="text-align:left">${{fmtCoach(g.opp_coach) || ''}}</td>
      <td style="text-align:left">${{g.opp_race || ''}}</td><td style="text-align:left">${{g.opp_team}}</td>
      <td class="${{cls}}">${{res}}</td><td>${{g.own_td}}-${{g.opp_td}}</td>
      <td>${{g.own_cas}}-${{g.opp_cas}}</td><td style="text-align:left">${{g.tournament || ''}}</td></tr>`;
  }});
  html += '</tbody></table></div>';
  el.innerHTML = html;
}}

function renderTopPlayers() {{
  const container = document.getElementById('abst-topPlayers');
  leaderboardSpecs.forEach(([key, title, statField, label]) => {{
    const rows = leaderboards[key] || [];
    const h2 = document.createElement('h2');
    h2.textContent = title;
    container.appendChild(h2);
    const wrap = document.createElement('div');
    if (!rows.length) {{
      wrap.innerHTML = '<div class="no-data">No player data available - run the crawler\\'s player pass to populate this.</div>';
      container.appendChild(wrap);
      return;
    }}
    let html = `<div class="table-scroll"><table class="subtable"><thead><tr>
      <th>#</th><th>Player</th><th>Position</th><th>Team</th><th>${{label}}</th>
    </tr></thead><tbody>`;
    rows.forEach((p, i) => {{
      const val = key === 'most_expensive' ? p.value.toLocaleString() + ' gp' : p.value;
      html += `<tr><td>${{i + 1}}</td><td style="text-align:left">${{p.name}}</td>
        <td style="text-align:left">${{p.position}}</td>
        <td class="team-link" data-key="${{p.team_key.replace(/"/g,'&quot;')}}" style="text-align:left">${{p.team_name}}</td>
        <td>${{val}}</td></tr>`;
    }});
    html += '</tbody></table></div>';
    wrap.innerHTML = html;
    container.appendChild(wrap);
  }});
  container.querySelectorAll('td.team-link[data-key]').forEach(td => {{
    td.addEventListener('click', () => selectTeam(td.dataset.key, true));
  }});
}}

function updateViewMode() {{
  const active = !!(currentTeamKey || currentCoach || showTopPlayers);
  document.getElementById('abst-listView').style.display = active ? 'none' : '';
  document.getElementById('abst-backBtn').style.display = active ? 'inline-block' : 'none';
  document.getElementById('abst-topPlayers').style.display = showTopPlayers ? 'block' : 'none';
}}

function openTopPlayers() {{
  showTopPlayers = true;
  currentTeamKey = '';
  currentCoach = '';
  coachSelect.value = '';
  render();
  renderCoachDetail();
  renderTeamDetail();
  updateViewMode();
  window.scrollTo({{top: 0, behavior: 'smooth'}});
}}

function selectTeam(key, scroll) {{
  currentTeamKey = key;
  currentCoach = '';
  showTopPlayers = false;
  coachSelect.value = '';
  render();
  renderCoachDetail();
  renderTeamDetail();
  if (scroll) window.scrollTo({{top: 0, behavior: 'smooth'}});
}}

function renderTeamDetail() {{
  const panel = document.getElementById('abst-teamDetail');
  const p = currentTeamKey ? teamProfiles[currentTeamKey] : null;
  updateViewMode();
  if (!p) {{ panel.style.display = 'none'; return; }}
  const row = (periods['all'] || []).find(r => r.key === currentTeamKey);
  panel.style.display = 'block';
  renderTeamInfo(p, row || {{}});
  renderTeamStats(p.stats);
  renderTeamStreaks(p.streaks, p.games_dated);
  renderTeamGames(p.all_games);
}}

function renderCoachDetail() {{
  const panel = document.getElementById('abst-coachDetail');
  const p = currentCoach ? profiles[currentCoach] : null;
  updateViewMode();
  if (!p) {{ panel.style.display = 'none'; return; }}
  panel.style.display = 'block';
  renderStreaks(p.streaks, p.games_dated);
  renderGroupTable('abst-withRaceTable', p.with_race, 'Race');
  renderGroupTable('abst-againstRaceTable', p.against_race, 'Race');
  renderGroupTable('abst-againstCoachTable', p.against_coach, 'Coach');
  renderGroupTable('abst-weekdayTable', p.by_weekday, 'Day');
  renderLastGames(p.last_games);
}}

function coachCellHtml(coaches) {{
  if (!coaches || !coaches.length) return '';
  return coaches.map(c =>
    `<span class="coach-link" data-coach="${{c.replace(/"/g,'&quot;')}}">${{c}}</span>`
  ).join(' &amp; ');
}}

function render() {{
  const rows = (periods[currentPeriod] || []).slice();
  const q = document.getElementById('abst-filter').value.toLowerCase();
  let filtered = q ? rows.filter(r =>
    (r.name + ' ' + (r.coach||'') + ' ' + (r.race||'')).toLowerCase().includes(q)
  ) : rows;
  if (currentCoach) filtered = filtered.filter(r => (r.coaches || []).includes(currentCoach));

  const k = sortState.k, dir = sortState.dir;
  filtered.sort((a, b) => {{
    const av = a[k], bv = b[k];
    if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir;
    return String(av).localeCompare(String(bv)) * dir;
  }});

  updateCoachSummary(filtered);

  const tbody = document.querySelector('#abst-tbl tbody');
  tbody.innerHTML = '';
  filtered.forEach((r, i) => {{
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${{i + 1}}</td>
      <td class="name${{r.deleted ? ' deleted' : ''}}" data-key="${{r.key.replace(/"/g,'&quot;')}}" title="${{r.name}}">${{r.name}}</td>
      <td class="coach" title="${{r.coach || ''}}">${{coachCellHtml(r.coaches)}}</td>
      <td class="race col-extra">${{r.race || ''}}</td>
      <td>${{r.gp}}</td><td>${{r.w}}</td><td>${{r.d}}</td><td>${{r.l}}</td>
      <td>${{r.points}}</td>
      <td>${{r.performance_pct.toFixed(1)}}%</td>
      <td class="col-extra">${{r.td_for}}</td><td class="col-extra">${{r.td_against}}</td>
      <td class="col-extra ${{r.td_diff >= 0 ? 'pos' : 'neg'}}">${{r.td_diff >= 0 ? '+' : ''}}${{r.td_diff}}</td>
      <td class="col-extra">${{r.cas_for}}</td><td class="col-extra">${{r.cas_against}}</td>
      <td class="col-extra ${{r.cas_diff >= 0 ? 'pos' : 'neg'}}">${{r.cas_diff >= 0 ? '+' : ''}}${{r.cas_diff}}</td>
      <td class="col-extra">${{r.kills_for}}</td>`;
    tbody.appendChild(tr);
  }});
  root.querySelectorAll('#abst-tbl tbody .coach-link').forEach(span => {{
    span.addEventListener('click', () => {{
      currentCoach = span.dataset.coach;
      coachSelect.value = currentCoach;
      currentTeamKey = '';
      showTopPlayers = false;
      render();
      renderCoachDetail();
      renderTeamDetail();
      window.scrollTo({{top: 0, behavior: 'smooth'}});
    }});
  }});
  root.querySelectorAll('#abst-tbl tbody td.name').forEach(td => {{
    td.addEventListener('click', () => selectTeam(td.dataset.key, true));
  }});
  document.getElementById('abst-empty-note').style.display = filtered.length ? 'none' : 'block';
  root.querySelectorAll('th[data-k]').forEach(th => {{
    th.classList.toggle('active', th.dataset.k === sortState.k);
  }});
}}

root.querySelectorAll('th[data-k]').forEach(th => {{
  th.addEventListener('click', () => {{
    const k = th.dataset.k;
    sortState.dir = (sortState.k === k) ? -sortState.dir : -1;
    sortState.k = k;
    render();
  }});
}});
yearSelect.addEventListener('change', () => {{
  currentPeriod = yearSelect.value;
  rebuildCoachOptions();
  render();
  renderCoachDetail();
  renderTeamDetail();
}});
coachSelect.addEventListener('change', () => {{
  currentCoach = coachSelect.value; currentTeamKey = ''; showTopPlayers = false;
  render(); renderCoachDetail(); renderTeamDetail();
}});
document.getElementById('abst-filter').addEventListener('input', render);
document.getElementById('abst-showExtra').addEventListener('change', (e) => {{
  root.classList.toggle('show-extra', e.target.checked);
}});
document.getElementById('abst-backBtn').addEventListener('click', () => {{
  currentTeamKey = '';
  currentCoach = '';
  showTopPlayers = false;
  coachSelect.value = '';
  render();
  renderCoachDetail();
  renderTeamDetail();
  window.scrollTo({{top: 0, behavior: 'smooth'}});
}});
document.getElementById('abst-topPlayersBtn').addEventListener('click', openTopPlayers);

rebuildCoachOptions();
render();
renderCoachDetail();
renderTeamDetail();
renderTopPlayers();
}})();
</script>
"""

FULL_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AnBBL Team Statistics</title>
<style>
  html, body {{ margin:0; background:#1a1a1a; }}
{style}
</style>
</head>
<body>
{body}
</body>
</html>
"""

EMBED_TEMPLATE = """<style>
{style}
</style>
{body}
"""


import re
from datetime import datetime

DATE_RE = re.compile(r"(\d+)(st|nd|rd|th)")


def parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(DATE_RE.sub(r"\1", s), "%B %d, %Y")
    except ValueError:
        return None


def _blank_group():
    return {"gp": 0, "w": 0, "d": 0, "l": 0,
            "td_for": 0, "td_against": 0, "cas_for": 0, "cas_against": 0}


def _add_result(g, own_td, opp_td, own_cas, opp_cas):
    g["gp"] += 1
    g["td_for"] += own_td; g["td_against"] += opp_td
    g["cas_for"] += own_cas; g["cas_against"] += opp_cas
    if own_td > opp_td:
        g["w"] += 1
    elif own_td < opp_td:
        g["l"] += 1
    else:
        g["d"] += 1


def _finalize_group(g):
    gp = g["gp"]
    perf = (g["w"] + 0.5 * g["d"]) / gp * 100 if gp else 0.0
    points = 5 * g["w"] + 3 * g["d"] + 1 * g["l"]
    return {**g, "points": points, "performance_pct": round(perf, 2),
            "td_diff": g["td_for"] - g["td_against"], "cas_diff": g["cas_for"] - g["cas_against"]}


def build_coach_profiles(matches):
    """For every individual coach that appears on at least one match side,
    build the same breakdowns the old reference site's coach page showed:
    streaks, performance against/with race, performance against coach,
    games by weekday, and the most recent games. Only possible where a
    match has a backfilled date/coach (see crawl.py's enrichment pass).

    Co-coached teams (shown on the site as e.g. 'Kyrre& Helmelk') are
    split into their individual names here - the match counts fully
    toward BOTH people's profiles, rather than being attributed to a
    fake third coach identity called 'Kyrre& Helmelk'."""
    by_coach = {}

    for m in matches:
        for side_key, opp_key in (("home", "away"), ("away", "home")):
            side, opp = m[side_key], m[opp_key]
            coach_names = side.get("coaches") or ([side["coach"]] if side.get("coach") else [])
            opp_coach_names = opp.get("coaches") or ([opp["coach"]] if opp.get("coach") else [])
            if not coach_names:
                continue
            dt = parse_date(m.get("date"))
            weekday = dt.strftime("%A") if dt else None
            for coach in coach_names:
                entry = by_coach.setdefault(coach, {
                    "matches": [], "against_race": {}, "with_race": {},
                    "against_coach": {}, "by_weekday": {},
                })
                rec = {
                    "match_id": m["match_id"], "date": m.get("date"), "year": m.get("year"),
                    "weekday": weekday, "tournament": m.get("tournament"),
                    "own_team": side["name"], "own_race": side.get("race"),
                    "opp_team": opp["name"], "opp_race": opp.get("race"), "opp_coach": opp.get("coach"),
                    "own_td": side["td"], "opp_td": opp["td"],
                    "own_cas": side["cas"], "opp_cas": opp["cas"],
                    "_sort": dt.isoformat() if dt else "",
                }
                entry["matches"].append(rec)

                if opp.get("race"):
                    g = entry["against_race"].setdefault(opp["race"], _blank_group())
                    _add_result(g, side["td"], opp["td"], side["cas"], opp["cas"])
                if side.get("race"):
                    g = entry["with_race"].setdefault(side["race"], _blank_group())
                    _add_result(g, side["td"], opp["td"], side["cas"], opp["cas"])
                for opp_coach in opp_coach_names:
                    if opp_coach == coach:
                        continue
                    g = entry["against_coach"].setdefault(opp_coach, _blank_group())
                    _add_result(g, side["td"], opp["td"], side["cas"], opp["cas"])
                if weekday:
                    g = entry["by_weekday"].setdefault(weekday, _blank_group())
                    _add_result(g, side["td"], opp["td"], side["cas"], opp["cas"])

    profiles = {}
    for coach, e in by_coach.items():
        dated = sorted([r for r in e["matches"] if r["_sort"]], key=lambda r: r["_sort"])

        def result_of(r):
            return "W" if r["own_td"] > r["opp_td"] else ("L" if r["own_td"] < r["opp_td"] else "D")

        longest_win = longest_loss = longest_unbeaten = cur_run = 0
        cur_type = None
        for r in dated:
            res = result_of(r)
            if res == cur_type:
                cur_run += 1
            else:
                cur_type = res
                cur_run = 1
            if res == "W":
                longest_win = max(longest_win, cur_run)
            if res == "L":
                longest_loss = max(longest_loss, cur_run)
        cur_unbeaten = 0
        for r in dated:
            if result_of(r) in ("W", "D"):
                cur_unbeaten += 1
                longest_unbeaten = max(longest_unbeaten, cur_unbeaten)
            else:
                cur_unbeaten = 0

        current_streak_len = 0
        current_streak_type = None
        for r in reversed(dated):
            res = result_of(r)
            if current_streak_type is None:
                current_streak_type = res
                current_streak_len = 1
            elif res == current_streak_type:
                current_streak_len += 1
            else:
                break

        profiles[coach] = {
            "first_game": dated[0]["date"] if dated else None,
            "last_game": dated[-1]["date"] if dated else None,
            "games_dated": len(dated),
            "games_total": len(e["matches"]),
            "streaks": {
                "current_type": current_streak_type, "current_len": current_streak_len,
                "longest_win": longest_win, "longest_loss": longest_loss,
                "longest_unbeaten": longest_unbeaten,
            },
            "against_race": {k: _finalize_group(v) for k, v in e["against_race"].items()},
            "with_race": {k: _finalize_group(v) for k, v in e["with_race"].items()},
            "against_coach": {k: _finalize_group(v) for k, v in e["against_coach"].items()},
            "by_weekday": {k: _finalize_group(v) for k, v in e["by_weekday"].items()},
            "last_games": [
                {k: v for k, v in r.items() if k != "_sort"}
                for r in list(reversed(dated))[:10]
            ],
        }
    return profiles


def _team_key(side):
    return side["id"] if side["id"] else f"name:{side['name']}"


def build_team_profiles(matches):
    """For every team, build the same breakdowns the old reference site's
    team page showed: info box (coach/race/TV/first-last game), a
    statistics table with per-game averages alongside totals, streaks, and
    the full game log. Unlike coach profiles this shows ALL games (a
    team's history is naturally much shorter than a coach's combined
    history across every team they've run)."""
    by_team = {}

    for m in matches:
        for side_key, opp_key in (("home", "away"), ("away", "home")):
            side, opp = m[side_key], m[opp_key]
            key = _team_key(side)
            entry = by_team.setdefault(key, {"games": []})
            dt = parse_date(m.get("date"))
            rec = {
                "date": m.get("date"), "tournament": m.get("tournament"),
                "own_race": side.get("race"),
                "opp_team": opp["name"], "opp_race": opp.get("race"), "opp_coach": opp.get("coach"),
                "own_td": side["td"], "opp_td": opp["td"],
                "own_cas": side["cas"], "opp_cas": opp["cas"],
                "own_kills": side["kills"], "opp_kills": opp["kills"],
                "_sort": dt.isoformat() if dt else "",
            }
            entry["games"].append(rec)

    profiles = {}
    for key, e in by_team.items():
        dated = sorted([r for r in e["games"] if r["_sort"]], key=lambda r: r["_sort"])
        gp = len(dated)

        def result_of(r):
            return "W" if r["own_td"] > r["opp_td"] else ("L" if r["own_td"] < r["opp_td"] else "D")

        w = sum(1 for r in dated if result_of(r) == "W")
        d = sum(1 for r in dated if result_of(r) == "D")
        l = sum(1 for r in dated if result_of(r) == "L")
        td_for = sum(r["own_td"] for r in dated)
        td_against = sum(r["opp_td"] for r in dated)
        cas_for = sum(r["own_cas"] for r in dated)
        cas_against = sum(r["opp_cas"] for r in dated)
        kills_for = sum(r["own_kills"] for r in dated)
        kills_against = sum(r["opp_kills"] for r in dated)
        points = 5 * w + 3 * d + 1 * l
        perf = (w + 0.5 * d) / gp * 100 if gp else 0.0

        def avg(total):
            return round(total / gp, 3) if gp else 0.0

        longest_win = longest_loss = longest_kill = 0
        cur_win = cur_loss = cur_kill = 0
        for r in dated:
            res = result_of(r)
            cur_win = cur_win + 1 if res == "W" else 0
            cur_loss = cur_loss + 1 if res == "L" else 0
            cur_kill = cur_kill + 1 if r["own_kills"] > 0 else 0
            longest_win = max(longest_win, cur_win)
            longest_loss = max(longest_loss, cur_loss)
            longest_kill = max(longest_kill, cur_kill)

        current_streak_len = 0
        current_streak_type = None
        for r in reversed(dated):
            res = result_of(r)
            if current_streak_type is None:
                current_streak_type = res
                current_streak_len = 1
            elif res == current_streak_type:
                current_streak_len += 1
            else:
                break

        profiles[key] = {
            "first_game": dated[0]["date"] if dated else None,
            "last_game": dated[-1]["date"] if dated else None,
            "games_dated": gp,
            "games_total": len(e["games"]),
            "stats": {
                "gp": gp, "w": w, "d": d, "l": l,
                "w_avg": avg(w), "d_avg": avg(d), "l_avg": avg(l),
                "performance_pct": round(perf, 2),
                "td_for": td_for, "td_against": td_against, "td_diff": td_for - td_against,
                "td_for_avg": avg(td_for), "td_against_avg": avg(td_against),
                "cas_for": cas_for, "cas_against": cas_against, "cas_diff": cas_for - cas_against,
                "cas_for_avg": avg(cas_for), "cas_against_avg": avg(cas_against),
                "kills_for": kills_for, "kills_against": kills_against,
                "kills_for_avg": avg(kills_for), "kills_against_avg": avg(kills_against),
                "points": points, "points_avg": avg(points),
            },
            "streaks": {
                "current_type": current_streak_type, "current_len": current_streak_len,
                "longest_win": longest_win, "longest_loss": longest_loss, "longest_kill": longest_kill,
            },
            "all_games": [
                {k: v for k, v in r.items() if k != "_sort"}
                for r in list(reversed(dated))
            ],
        }
    return profiles


LEADERBOARD_SPECS = [
    ("top_stars", "Top stars", "spp", "SPP"),
    ("most_expensive", "Most expensive", "value", "Value"),
    ("top_scorers", "Top scorers", "touchdowns", "TDs"),
    ("top_throwers", "Top throwers", "completions", "Completions"),
    ("top_mvps", "Top MVPs", "mvps", "MVPs"),
    ("top_hitters", "Top hitters", "casualties", "Casualties"),
    ("top_interceptors", "Top interceptors", "interceptions", "Interceptions"),
]


def build_player_leaderboards(players, team_lookup, n=15):
    """Rank every currently-living player league-wide into the same
    categories the old reference site's 'All time top players' page
    showed. Only living players are included by construction, since
    dead/retired players never appear on a team's roster page at all."""
    leaderboards = {}
    for key, _title, stat_field, _label in LEADERBOARD_SPECS:
        ranked = sorted(players, key=lambda p: -p[stat_field])[:n]
        leaderboards[key] = [
            {
                "name": p["name"],
                "position": p["position"],
                "team_key": p["team_id"],
                "team_name": team_lookup.get(p["team_id"], p["team_id"]),
                "value": p[stat_field],
            }
            for p in ranked
        ]
    return leaderboards


def row_dict(t, stats):
    return {
        "key": t["id"] if t.get("id") else f"name:{t['name']}",
        "name": t["name"],
        "coach": t.get("coach") or "",
        "coaches": t.get("coaches") or ([t["coach"]] if t.get("coach") else []),
        "race": t.get("race") or "",
        "tv": t.get("tv") or "",
        "deleted": bool(t.get("deleted")),
        "gp": stats["gp"], "w": stats["w"], "d": stats["d"], "l": stats["l"],
        "points": stats["points"],
        "performance_pct": stats["performance_pct"],
        "td_for": stats["td_for"], "td_against": stats["td_against"], "td_diff": stats["td_diff"],
        "cas_for": stats["cas_for"], "cas_against": stats["cas_against"], "cas_diff": stats["cas_diff"],
        "kills_for": stats["kills_for"],
    }


def main():
    with open(os.path.join(DATA_DIR, "teams.json"), encoding="utf-8") as f:
        teams = json.load(f)
    with open(os.path.join(DATA_DIR, "matches.json"), encoding="utf-8") as f:
        matches = json.load(f)

    periods = {"all": []}
    for t in teams:
        periods["all"].append(row_dict(t, t["all"]))
        for year, stats in t.get("by_year", {}).items():
            periods.setdefault(year, []).append(row_dict(t, stats))

    undated = sum(1 for m in matches if not m.get("year"))
    coach_profiles = build_coach_profiles(matches)
    team_profiles = build_team_profiles(matches)

    players_path = os.path.join(DATA_DIR, "players.json")
    leaderboards = {}
    n_players = 0
    if os.path.exists(players_path):
        with open(players_path, encoding="utf-8") as f:
            players = json.load(f)
        n_players = len(players)
        team_lookup = {t["id"]: t["name"] for t in teams if t.get("id")}
        leaderboards = build_player_leaderboards(players, team_lookup)

    periods_json = json.dumps(periods, ensure_ascii=False)
    profiles_json = json.dumps(coach_profiles, ensure_ascii=False)
    team_profiles_json = json.dumps(team_profiles, ensure_ascii=False)
    leaderboards_json = json.dumps(leaderboards, ensure_ascii=False)
    leaderboard_specs_json = json.dumps(LEADERBOARD_SPECS, ensure_ascii=False)

    body = BODY_TEMPLATE.format(
        n_teams=len(teams), n_matches=len(matches), n_players=n_players,
        periods_json=periods_json,
        profiles_json=profiles_json, team_profiles_json=team_profiles_json,
        leaderboards_json=leaderboards_json, leaderboard_specs_json=leaderboard_specs_json,
    )

    os.makedirs(OUT_DIR, exist_ok=True)

    full_html = FULL_PAGE_TEMPLATE.format(style=STYLE, body=body)
    full_path = os.path.join(OUT_DIR, "index.html")
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(full_html)

    embed_html = EMBED_TEMPLATE.format(style=STYLE, body=body)
    embed_path = os.path.join(OUT_DIR, "embed.html")
    with open(embed_path, "w", encoding="utf-8") as f:
        f.write(embed_html)

    print(f"Wrote {full_path} ({len(teams)} teams, {len(periods) - 1} years + all-time)")
    print(f"Wrote {embed_path} - paste this into the site's raw-HTML content "
          f"editor to embed the widget there")
    if undated:
        print(f"Note: {undated} matches had no backfilled date (both sides were "
              f"already-deleted teams) - they're still counted in the All-time tab, "
              f"just not split into a specific year.")


if __name__ == "__main__":
    main()
