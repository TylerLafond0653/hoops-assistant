# Daily Hoops checkup

Every morning it checks your ESPN team and pings you on Discord with anything to do today:
lineup swaps, IR moves, this week's category matchup, streaming pickups and waiver upgrades.
It only suggests; you make the moves in the ESPN app.

## Try it now (no league needed)
    python inseason/checkup.py --demo --dry-run     prints a sample alert
    python inseason/checkup.py --demo               sends it to your Discord

## After the draft: turn it on
1. **League settings.** Copy `config.example.json` to `config.json`. Fill in `league_id` (from your league's
   URL, `leagueId=...`) and `team_id` (from your team page, `teamId=...`).
2. **ESPN cookies.** Logged in to ESPN in Chrome, press F12 > Application > Cookies > https://fantasy.espn.com.
   Copy the values of `espn_s2` and `SWID`. Test on your laptop by adding them to `secrets.local.json` as
   `"ESPN_S2"` and `"ESPN_SWID"`, then run `python inseason/checkup.py --dry-run`.
3. **GitHub (runs with your laptop off).**
   - Create a **private** repository and upload this `fantasy-draft` folder. Never upload `secrets.local.json`;
     `.gitignore` already skips it.
   - In the repository, go to Settings > Secrets and variables > Actions > New repository secret, and add:
     `ESPN_S2`, `ESPN_SWID`, `DISCORD_WEBHOOK` and `DISCORD_USER_ID` (601804663821565952).
   - Actions tab > Hoops checkup > **Run workflow** to test. After that it runs every morning around 10 AM.

If ESPN's cookies expire (every few months), the checkup pings you to update the two ESPN secrets.
