# Draft day: how to run and update everything

## 1. Open a terminal in VS Code
Menu **Terminal → New Terminal**. Then move into this folder:

```
cd "C:\Users\tyler\OneDrive - The University of Western Ontario\Year 4\projects\fantasy-draft"
```

## 2. The morning of the draft: refresh the data (about 1 minute)
One command refreshes everything: the expert consensus and ADP (FantasyPros), then ESPN's data and injury report.

```
python pipeline/refresh_espn.py
```

This updates, inside `draft-room.html`:
- the FantasyPros expert consensus for category leagues (what experienced drafters follow) and Yahoo/ESPN ADP;
- ESPN's live ADP and ESPN's category rankings (the list ESPN's draft room shows);
- every player's current team (signings and trades are applied automatically);
- the positions ESPN lets each player start at (your league's lineup rules);
- last season's stats;
- players ESPN drafts who aren't on the app's list.

It then prints an **injury check** from ESPN's official NBA injury report, compared with the app's injury notes:
- **[NEW]:** injury news the app doesn't have yet.
- **[CHECK]:** ESPN has newer news than the app's note.
- **[noted]:** already in the app, so nothing to do.

If the last line says **"Nothing new"**, you're done. Otherwise, copy the NEW and CHECK lines to Claude so the app's injury notes (and projected games, for long injuries) get updated.

Old "day-to-day" tags from last season or the summer are skipped on purpose; they aren't current injuries.

## 3. Open the app
In the VS Code file list, right-click `draft-room.html` and choose **Reveal in File Explorer**. Double-click the file to open it in Chrome or Edge. It works offline, and nothing needs installing.

Check before your first pick:
- The 3 dots (**League settings**) show League site = **ESPN** and Scoring = **Head-to-head most categories**.
- The draft order is Saksham, Jattan, Cristian, Sameer, **Tyler**, Arjun, Surya, Satvik, Santosh, Pratham.
- Future seasons = **Balanced**, unless you want to win now or build for later.
- Your leaguemates = **Sharp** (they mostly follow the expert consensus, some follow ESPN's list). Use **Casual** only if your league just drafts straight off ESPN's rankings.
- Keep the ESPN draft room and the app side by side.

## 4. During the draft
- **Someone else picks:** press `/`, type a few letters of the name, press **Enter**. That gives the player to whoever is on the clock.
- **Your pick:** take the **Recommended** card (it's also tagged on the board). The other cards say why they're second.
- **Mistake:** Undo (Ctrl+Z).
- **Don't** press "Sim to my pick" in the real draft; it's only for practice.

## 5. After the draft
1. On the Draft log card, press **Export**. It saves a file like `draft-log-2026-10-XX.csv` to Downloads.
2. Move that file into this folder, then run:

```
python analysis/fit_opponent_model.py draft-log-2026-10-XX.csv
```

It shows which ranking your leaguemates really followed: the expert consensus (keep Sharp), ESPN's list (switch to Casual or Mixed), or a mix. Tell Claude the result, and the app gets tuned for next year's keeper draft.

## If something breaks
- **"python not found":** type `py` instead of `python`.
- **Refresh fails (no internet, or ESPN or FantasyPros is down):** the app still works with the data from the last successful refresh (Sept 29). If only one site fails, the other still updates.
- **Something looks wrong after a refresh:** every version is saved on GitHub (github.com/TylerLafond0653/hoops-assistant). Ask Claude to restore the last good one.
