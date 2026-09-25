# In-season assistant plan

> **Status (Sept 25, 2026): built.**
> - **Done:** `inseason/checkup.py`, `inseason/notify.py`, `.github/workflows/checkup.yml` and `inseason/README.md`.
> - **Alerts:** go to Discord with an @mention (webhook plus user ID in `secrets.local.json`; ntfy didn't push reliably on his iPhone).
> - **Tested:** the demo mode works.
> - **Remaining after the draft:** `config.json` (league/team ID), ESPN cookies, a private GitHub repository with 4 secrets, then a first real run.
> - **Check the league-mode code (`load_league`) on the first real run**, since it couldn't be tested before the league existed.

> **For Claude, in a new session:** this is Tyler's plan. Read this whole file, then `DRAFT_DAY.md` and `analysis/MODEL_AUDIT.md` (§17) for context. Build what's described below. Ask Tyler for the "Needed from Tyler" items only when you reach the step that uses them, and never ask for his ESPN password.

## Context
- **League:** "GUGUGUZZLERS V2" on ESPN. 10 teams, H2H **most categories** (one weekly win/loss/tie), 9 categories: PTS, REB, AST, STL, BLK, 3PM, FG%, FT%, TO.
  - Lineup: PG, SG, SF, PF, C, G, F, 3 UTIL, 5 bench, 3 IR.
  - Keepers: up to 6, round-minus-one pricing, 3 seasons maximum.
  - The full charter is a Google Doc (ID `1VuhjFrThxXok-sLIqjmtI96-XwbDKi2FGWJLIFlcGSU`).
- **Tyler:** first-time manager. Wants plain-English alerts on his phone, and the assistant should only suggest moves (he makes them himself in the ESPN app).
- **Existing code in this folder:**
  - `draft-room.html`: the draft app.
  - `analysis/common.py`: ESPN feed loader and the stat → 9-cat z-score map (`ZMap`).
  - `pipeline/refresh_espn.py`: shows how to call ESPN's API.
  - `analysis/calibration.json`: measured weekly spread per category and projection-miss sizes. Reuse these.

## Goal
A Python script that checks Tyler's team every morning (and optionally again before evening games) and sends phone alerts through **ntfy**. It runs on **GitHub Actions**, so his laptop can be off.

## Alerts (in order of importance)
1. **Lineup:** a benched player has a game today while a starter doesn't, or an injured (OUT) player is in a starting slot. Say exactly which swap to make.
2. **IR:** a player is OUT or on IR status. "Move X to IR, then pick up Y (who plays N games this week and helps your weak categories)."
3. **Matchup check (daily):** the current score in each category against this week's opponent, the win chance per category using the calibration spreads, and which 1–2 close categories a pickup could flip.
4. **Streaming (Mon/Tue):** the games-this-week gap between the two teams, and the top 3 free agents by value this week (per-game z × games left), noting whom to drop (Tyler's lowest-value non-keeper-worthy player).
5. **Waiver upgrade (weekly):** a free agent whose season value beats Tyler's worst rostered player by a clear margin (at least 1 value point).
6. **Keeper note (after the trade deadline, Feb 8):** Tyler's current top-6 keeper candidates and their costs (round minus one).

Keep each alert to about 3 lines. Send nothing on days when there's nothing to do. Send one summary per run, not a flood.

## Data (ESPN API, private league)
- **Base URL:** `https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/2027/segments/0/leagues/<LEAGUE_ID>`
- **Views:**
  - `mRoster`, `mTeam`: rosters, lineup slots, injury status.
  - `mMatchupScore`, `mScoreboard`: this week's matchup.
  - `kona_player_info` with an `x-fantasy-filter` for free agents (filter status FREEAGENT/WAIVERS, sorted by ownership).
  - `proTeamSchedules_wl`: NBA schedule, for games per day and week.
- **Authentication:** send cookies `espn_s2` and `SWID` with every request.
- **Projections:** ESPN projections for the rest of the season (statSourceId 1). Convert them with `ZMap` (same scale as the draft app) and weight by games.

## Files to create
- `inseason/checkup.py`: fetch data, compute alerts, send to ntfy.
- `inseason/config.example.json`: league ID, team ID, alert times. No secrets in this file.
- `.github/workflows/checkup.yml`: schedule (cron, e.g. `0 13 * * *` = 9 AM Eastern) plus a manual `workflow_dispatch` button. Python 3.12. Reads secrets `ESPN_S2`, `ESPN_SWID`, `NTFY_TOPIC`.
- `inseason/README.md`: setup steps in plain English.

## Error handling
- If ESPN returns 401/403 (cookies expired), send "Your ESPN login expired: update the ESPN_S2 and ESPN_SWID secrets" with the steps.
- If the script crashes, send a short ntfy message saying the checkup failed.

## Test before scheduling
- Run it locally once with `--dry-run`, which prints the alerts instead of sending them.
- Then send one real test to ntfy.
- Then trigger the GitHub workflow by hand and confirm the phone gets the alert.

## Needed from Tyler (he'll do these himself)
1. **ntfy:** app installed, a private topic name chosen, and a test notification received.
2. **ESPN league ID:** the number after `leagueId=` in the league URL. **Team ID:** from his team page URL (`teamId=`).
3. **ESPN cookies `espn_s2` and `SWID`:** logged in to ESPN in Chrome, F12 → Application → Cookies → espn.com. He pastes these only into the GitHub Secrets, never into chat or code.
4. **A free GitHub account** with a **private** repository. Claude prepares the files; Tyler creates the repository, adds the 3 secrets (Settings → Secrets and variables → Actions), and pushes (or uploads) the files.

## Not in scope
- Automatic roster moves (against ESPN's rules).
- Trade evaluation (possible later).
- Hosting the draft app online.
