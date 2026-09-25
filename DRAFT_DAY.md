# Draft day: how to run and update everything

## 1. Open a terminal in VS Code
Menu **Terminal → New Terminal**. Then move into this folder:

```
cd "C:\Users\tyler\OneDrive - The University of Western Ontario\Year 4\projects\fantasy-draft"
```

## 2. The morning of the draft: refresh ESPN's data (about 1 minute)

```
python pipeline/refresh_espn.py
```

This updates, inside `draft-room.html`:
- ESPN's live ADP and ESPN's category rankings (who your leaguemates will take);
- last season's stats;
- players ESPN drafts who aren't on the app's list.

It then prints a report. Check its `team:` and `injury:` lines:
- **team:** the player changed teams. Tell Claude, and the app's team for him gets fixed.
- **injury OUT:** check the news. If it's real and not already an injury note on the board, tell Claude to add it.
- **injury DAY_TO_DAY:** usually left over from last season, so it can be ignored.

## 3. Open the app
In the VS Code file list, right-click `draft-room.html` and choose **Reveal in File Explorer**. Double-click the file to open it in Chrome or Edge. It works offline, and nothing needs installing.

Check before your first pick:
- The 3 dots (**League settings**) show League site = **ESPN** and Scoring = **Head-to-head most categories**.
- The draft order is Saksham, Jattan, Cristian, Sameer, **Tyler**, Arjun, Surya, Satvik, Santosh, Pratham.
- Future seasons = **Balanced**, unless you want to win now or build for later.
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

It shows which ranking your leaguemates really followed. Tell Claude the result, and the app gets tuned for next year's keeper draft.

## If something breaks
- **"python not found":** type `py` instead of `python`.
- **Refresh fails (no internet, or ESPN is down):** the app still works with the data from Sept 25.
- **Want to go back to the previous version:** open one of the backup files, e.g. `draft-room.backup.html`.
