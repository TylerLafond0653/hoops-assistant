# Hoops Draft Room model audit (Sept 25, 2026)

> **Reading guide:** sections 1–16 describe the model as it was audited on Sept 25. The changes made since, and the evidence behind each, are in **§17** (the audit fixes) and **§18** (the ranking sources: expert consensus as the market, FantasyPros projections, leaguemates as expert/ESPN types). The current app follows §17–18. **§19** is a stress test against leaguemates who commit to builds and make mistakes, and the simulator fixes it led to (category-aware punt plans, leaguemates who keep their plan, the "Playing as" label).

**Question audited:** given the current draft state, does the app pick the player with the highest expected value for your roster in a 10-team, 9-category head-to-head (H2H) keeper league?

**Scope and method:** the app (`draft-room.html`) is the source of truth, and no app code was changed. Every claim below is backed by one of the following:
- the code itself;
- the calibration and backtest scripts in this folder, which run on ESPN's preseason projections and 3 seasons of real box scores;
- experiments run on the live app in a browser (the pick breakdowns, simulation stability checks and stress tests).

| Script | What it does |
|---|---|
| `common.py` | Loads the app's data, the ESPN feeds (projections, actuals, box scores, ranks) and Basketball Reference tables. Pure Python. |
| `audit_calibration.py` | Projection misses, games-played bias, week-to-week noise per category, and the availability model (2025-26). |
| `audit_projection_seasons.py` | Projection misses and games bias across 2023-24, 2024-25 and 2025-26. |
| `backtest_2025.py` | Replays drafts with only preseason information and scores the teams on real weekly H2H results. Set `BT_SEASON=2024/2025/2026`. |
| `backtest_robustness.py` | The same strategies, with bootstrapped weeks, 3 draft slots, 2 market models and extra variants. |
| `*_results.txt` | The saved output of those runs. |

---

## 1. Executive summary

The app's core is sound, and several of its judgment calls are supported by data:
- games-weighted value with a waiver fill for missed games;
- partly trusting the market;
- the don't-reach rule (skip a player who will likely still be there at your next pick);
- Balanced by default;
- handling FG% and FT% by volume.

The biggest problems are in the inputs and in consistency, not in the core math:

1. **The opponent model runs on the wrong ADP.** The "ESPN ADP" in the app comes from FantasyPros. It disagrees with ESPN's own live ADP by a median of 13 picks, and 67 of 149 players differ by more than 15 (for example Vučević is 40 in the app and 115 on ESPN; Zubac is 35 vs 94). That same number drives:
   - the "% still there" odds;
   - who opponents take in the simulator;
   - the market blend in player value.
2. **The app uses two different player values.** The board's Rank and Value, the pick cards, the keeper value and the practice opponents all use per-game value, which ignores games played. The simulator uses games-weighted, market-blended value. The two rank the same player up to 30 places apart; for example Haliburton is #10 on the board and #31 in the simulator. Ignoring games played was the worst strategy in the backtest: it trailed games-weighted value by about 8 points of weekly win rate on average, and by up to 23 in one draft slot.
3. **Uncertainty is understated.** Projection misses are about 2.4 value points (standard deviation) in every season tested; the app assumes 1.5. Games played are over-projected by 6–13 games every season. Weekly noise in steals, FG%, FT% and threes is 1.4–1.9 times the app's single weekly spread of 5. As a result, the displayed win percentages and "Clear favourite" labels are overconfident.
4. **A tie-break bug, added Sept 25.** Among tied players the app prefers the plan's pick even when the plan itself is only a "Close call". Players whose results are very uncertain get wide tie windows, so they win this tie-break more easily. In the win-now stress test this made Amen Thompson the pick at 2.06 over Donovan Mitchell, who had the higher expected value.

**The simulator and look-ahead add little proven value.** Backtested over three seasons, choosing players by their effect on the whole team (their matchup value) instead of by games-weighted, market-blended value alone was mixed: +7, −2 and −1 points of weekly win rate. It isn't harmful, but it doesn't justify adding more complexity.

**Recommendation:**
- Fix the ADP source and the tie-break.
- Use one valuation everywhere.
- Recalibrate uncertainty.
- Keep the architecture.
- Move the data pipeline to Python in the project; it currently lives in a temp folder.
- Don't add new model components until the backtest harness shows they help.

---

## 2. Current architecture and data flow (as implemented)

```
Sources (pulled Sept 24-25, scripts in a TEMP folder)
  FanScout top 150 + rookie/soph/3rd/4th-year pages ─┐
  ESPN 2026-27 projections (public feed) ────────────┼─> blend (50/50; ESPN 60% for our own
  Basketball Reference 2025-26 (veteran estimates) ──┘     estimates) -> stat line + 9-cat z (FanScout scale)
  FantasyPros ADP [Yahoo, "ESPN"] ── ADP ; ESPN injury news ── NEWS ; ages ── AGE ; aging curve ── AGE_STEP
                              │
                              v   DATA (357 players) hard-coded into draft-room.html
parseDefault(): z per category, rank = sum of z (per game), flags from NEWS, DISAGREE gap
                              │
   ┌──────────────────────────┼──────────────────────────────────────────────┐
   v                          v                                              v
 Board / cards           Simulator (simBuilds)                         Keeper model
 valueOf = Σz            effZ = (z + market shift)·g + R·(1-g)          keeperPlan: Σz + age step + rookie step,
 (per game, no games)    others pick by ADP + N(0, 1.5+0.12·ADP)        breakdown risk, vs next year's pick value
 chance(i,m) logistic    you pick by expected loss (build value          (per game, no games)
 expected-loss cards       + fw·keeper + position bonus)
                         each season: projection shock N(0, projSd), split evenly over 9 cats
                         lineup weights SLOT_W; weekly matchup: each cat Φ(Δ/5), win if > 4.5 cats
                         -> per plan: weekly win %, keeper value
                              │
                     rankPlans: win + fw·0.021·keeper, Hard −0.03, Balanced +0.005, chosen +0.01,
                     plan memory (switch only if ahead by max(0.02+0.002·picks, 2.5·se))
                              │
 renderAdvice (on the clock):
   quick pick = best by expected loss (rounds 1-2) or the plan's pick (40%+ share, robust)
   look-ahead: up to 6 candidates, 60 replays each, shared seed -> team EV (win + fw·0.021·keeper)
   tie = within max(0.4 pts, 1.5·se) of the best; among ties: plan's pick > quick pick > best
```

### Every place a player's value is computed

| Where | Formula | Games? | Market? | Keeper? | Used for |
|---|---|---|---|---|---|
| `valueOf` | Σ z, minus punted categories | no | no | no | Board Value, pick-card ranking (`cv`), "More players" list |
| `p.rank` | Σ z | no | no | no | Board order, replacement pool, leaguemate-sharpness setting |
| `zOf` / `bval` | Σ w·z with z capped at ±4, standardized | no | no | no | Plan fit, other teams' likely plans, practice opponents' early picks |
| `effZ` | (z + ½·(valueAtPick(ADP) − Σz)/9)·g + R·(1−g) | yes | yes | no | Simulator, look-ahead, league comparison, pick grades |
| `keeperPlan` | Σz + aging, vs next year's pick value | no | no | — | Keeper value everywhere |
| `scorePlayer` | 3·Σz + position/weak-category bonuses + 3·fw·keeper | no | no | yes | "More players" list only |
| `smartPick` (rounds 1–2) | Σ zOf + fw·keeper | no | no | yes | Practice opponents |

**Finding:** there are three substantially different valuations. The final on-the-clock decision uses `effZ` through the look-ahead, but the candidates the look-ahead considers are chosen with the per-game valuation. What you see on the board and cards is also per-game.

---

## 3. What is working well (keep)

- **Percentage categories are volume-weighted.** FanScout's FG% and FT% z-scores track makes-above-average (correlation 0.99 for FG%, 0.93 for FT%), not the raw percentage (0.90 and 0.85). This is correct for H2H: a 90% shooter on 2 attempts barely moves a team's FT%.
- **Turnovers are signed correctly.** The TO z-score has a −0.998 correlation with turnovers per game.
- **Blending FanScout and ESPN.** Averaging two independent projections reduces error, and the linear map between their scales fits within 0.3 z in every category.
- **Games weighting with a waiver fill** (the simulator's `effZ`). This was the single most valuable component in the backtest (section 10).
- **The market blend at 0.5.** On average it helped (+3.7 points of weekly win rate across 3 seasons), though it swings by season. Keep it; fix its inputs instead (see changes 1 and 4).
- **The don't-reach (expected-loss) rule.** +1.7 points on average across 3 seasons (−1.7, +2.9, +3.8).
- **Balanced by default, and not punting from pick 1.** Committing to Punt FT% from the first pick scored 28% weekly wins vs 72% for Balanced, and Punt TO scored 61% (2025-26 backtest). The small penalty on Hard plans and the Balanced bonus are consistent with this.
- **Plan memory and the look-ahead's noise-aware tie band.** The recommendation stays stable: at 1.05, Edwards won in 9 of 10 random seeds with 60 replays and 6 of 6 with 240. At 6.05, Duren won 7 of 8.
- **Aging curve.** It's measured from 1,426 Basketball Reference player-seasons, and survivor bias is acknowledged in the code.

---

## 4. Critical bugs (A: actual code/data bugs)

| # | Bug | Evidence | Effect |
|---|---|---|---|
| A1 | **Wrong "ESPN ADP" source.** It comes from FantasyPros' ESPN column, not ESPN's live `averageDraftPosition`. | Median gap 12.7 picks; 67 of 149 players more than 15 picks apart. Butler 67 vs 135 (he's out until December), Vučević 40 vs 115, Zubac 35 vs 94, Dejounte Murray 126 vs 69. | "% still there", the simulated opponents and the market blend all use a stale anchor. **High.** |
| A2 | **Tie-break prefers the plan's pick even when the plan is a "Close call"** (added Sept 25). | Win-now stress test at 2.06: the look-ahead has Mitchell best, and Amen Thompson 1.01 ± 1.98 behind. Amen counts as "tied" because his uncertainty is large, so he's recommended, for a Punt FT%+3PM plan marked "Close call" in round 2. | A lower-EV player wins because of a rule, not value. **High, easy fix.** |
| A3 | **Look-ahead cache key leaves out the leaguemate-sharpness setting (`S.savvy`), the keeper list and `TUNE`.** | `lookahead()` key = `[order, site, fw, punt, anchor, cands]`. | After changing leaguemate sharpness or keepers, the recommendation can be stale until the next pick. **Low.** |
| A4 | **Look-ahead candidates are chosen with per-game value.** They come from the cards (`valueOf`), the board rank and the plan pick. | Board rank and simulator rank differ by 15–30 places for about 12 of the top 60 (Harden board #37 vs simulator #17; Giannis #22 vs #8; Amen #36 vs #20). | A player the simulator rates highly can be missing from the 6 candidates. **Medium.** |
| A5 | **Practice opponents (`smartPick`, rounds 1–2) still use the ±4-capped z-scores.** | Wemby's blocks are capped for them but not for you. | Practice drafts only. **Low.** |

(These are separate from modeling choices, which follow.)

---

## 5. Most important modeling problems (B: mathematical/statistical)

**B1. Uncertainty is too small, and its shape is wrong.**
- **What the app does:** a season shock N(0, 1.5) on each player's total value, split evenly across the 9 categories, so the categories move together perfectly (correlation +1).
- **Evidence:**
  - ESPN preseason projections vs actual, top 200: season-value miss standard deviation 2.32 / 2.52 / 2.48 in 2023-24 / 2024-25 / 2025-26.
  - Misses in different categories are nearly independent (average correlation +0.10), not +1.
  - The FanScout+ESPN blend should be somewhat more accurate than ESPN alone; I estimate a miss sd of about 2.0–2.2, but that can't be tested because FanScout's past projections aren't available.
- **Effect:** the tie bands are too narrow, displayed win rates are too extreme, and the risk in category-specific plans (punts) is understated.

**B2. Games played are over-projected every season.**
- Projected vs actual games (top 200): 65.7 vs 59.3, 70.7 vs 59.3 and 69.9 vs 56.5.
- The correlation between projected and actual games is only 0.39–0.62.
- `gamesShare` caps at 72, so every player projected at 72 or more games counts as fully healthy, which nobody is.
- **Effect:** stars' value is overstated relative to depth, and a player projected for 72 games is rated the same as one projected for 80.

**B3. The weekly matchup model uses one spread (5) for all nine categories.**
- The spread was fitted on odd weeks, with injured games filled by a waiver player:

  | Category | PTS | REB | AST | STL | BLK | 3PM | FG% | FT% | TO |
  |---|---|---|---|---|---|---|---|---|---|
  | Measured weekly spread | 5.5 | 5.0 | 4.9 | 8.7 | 5.6 | 7.2 | 8.3 | 9.5 | 6.3 |

- 5 is about right for PTS, REB, AST and BLK, but too small for STL, FG%, FT% and 3PM.
- Without the waiver fill (a roster left untouched), the spreads are 7.6–18.4.
- **Decision effect:** unproven. Using the measured spreads changed backtest results by −0.9, +1.6 and +4.6 points (not significant). **Display effect:** real, since win percentages are overconfident.

**B4. `WIN_PER_Z = 0.021` is tied to the weekly spread of 5.**
- It converts keeper value into weekly wins, and it was measured with the old matchup model.
- If the weekly spread changes without re-measuring this constant, the balance between this season and future seasons shifts silently.

**B5. The market anchor table is per-game while ADP is a season value.**
- `valueAtPick` sorts per-game values, but ADP already reflects expected missed games. The market shift then pulls injury-prone players down again, before `gamesShare` discounts them a second time.
- Players projected for fewer than 65 games get a −0.66 average shift, vs +0.04 for the rest; the correlation of shift with projected games is +0.15. Kyrie's shift is −3.15.

**B6. Selection bias in projections.**
- The players projected highest underperform on average: the top 200 missed by −0.5 to −1.1 per season.
- It's mild and affects every team, but players 31+ underperformed more in all three seasons (−0.68 vs −0.55, −1.26 vs −0.81, −1.83 vs −1.15 for ages 25–30).
- This season's value gets no age adjustment; the aging curve is only applied to future keeper seasons.

---

## 6. Potentially overweighted factors

**Market pull on injury-prone players (B5).**
- **What it does now:** it pulls per-game value halfway toward the per-game value implied by the player's ADP.
- **Why it's a problem:** ADP already prices in missed games, and `gamesShare` discounts them again.
- **Evidence:** the market shift is correlated with projected games; the average shift is −0.66 below 65 games.
- **Effect of the fix:** injury-prone players regain about 0.3–0.7 value points.
- **How to test:** backtest a games-consistent anchor table across 3 seasons.

**Points-league signal in the market.**
- **What it does now:** the market uses ESPN ADP (FantasyPros), which is dominated by points leagues.
- **Why it's a problem:** in a category league it imports points-league value. Harden, Amen Thompson and Giannis rise; Markkanen and Murphy fall.
- **Evidence:** ESPN also publishes a category-league rank that differs from its ADP (correlation 0.88; Clingan 43 vs 83, Kel'el Ware 67 vs 109).
- **Effect of the fix:** a category-appropriate market signal.
- **How to test:** compare anchors on real draft logs (change 10). Historical rankings aren't available, so it can't be backtested.

**Confidence labels and displayed win percentages (B1, B3).**
- **What they do now:** they use spread 5 and projection sd 1.5.
- **Why it's a problem:** both are too small.
- **Evidence:** 3-season calibration.
- **Effect of the fix:** fewer "Clear favourite" labels and more honest percentages.
- **How to test:** check coverage of the intervals (see the plan).

---

## 7. Potentially underweighted factors

**Games played on the board and cards.**
- **What they do now:** the per-game Value ignores games.
- **Why it's a problem:** it is the valuation the user actually sees, and the candidates the look-ahead considers come from it.
- **Evidence:** the backtest average is +7.6 points for games-weighted value (+19.1, +4.4, −0.7 by season).
- **Effect of the fix:** the board order matches the simulator order.
- **How to test:** it's already backtested; re-run the stress tests after the change.

**Projection uncertainty (B1).** Covered in section 5.

**Age this season.**
- **What it does now:** there's no adjustment for age in the current season.
- **Why it's a problem:** players 31+ underperformed in all three seasons.
- **Evidence:** the extra miss vs prime-age players was −0.13, −0.45 and −0.68.
- **Effect of the fix:** about −0.4 for players 31+.
- **How to test:** fit on two seasons and test on the third (leave-one-season-out).

---

## 8. Double-counting check

| Suspected overlap | Verdict |
|---|---|
| ADP used both for availability and for the market blend | Not double counting (one predicts opponents, the other informs value). But both inherit the same stale source (A1), so their errors are correlated. |
| Projected games and injury risk | Partly: games lower the average value; the injury flags only add uncertainty (projSd +0.5/+0.8), which is fine. **But** the market blend also discounts injury-prone players (B5), which is **double counting**. |
| Category value and roster fit | No double counting in the final decision: the look-ahead scores the whole team once. The "More players" list (`scorePlayer`) does double-count weak categories (value ×3 plus a weak-category bonus of 1.2·z), but it's only a browsing list. |
| Scarcity and replacement level | No overlap. Replacement level is only used for missed games; category scarcity is built into FanScout's scale. |
| Keeper value | Counted once in the look-ahead value and once in plan ranking; the simulator's own pick rule also uses it, but that's the rule for making picks, not the score. **No double counting.** |
| ESPN's opinion | **Partial overlap:** ESPN projections are 50% of the blend, and the market blend pulls toward (FantasyPros') ESPN ADP. ESPN's view enters twice, once through projections and once through ranking. Moderate. |
| Simulator vs base score | The look-ahead is the final judge, and the base score only picks candidates. But the simulator's own later picks use additive value, while its evaluation uses matchups. So the look-ahead compares "take X now, then follow a different rule" — e.g., it took Haliburton at 5.06 even though he had a 100% chance of lasting, because its own later rule undervalues him. This is a mismatch between how the simulator picks and how it scores, not double counting. |

---

## 9. Simulation weaknesses

1. **Simulation count is adequate.**
   - At 1.05, the top pick was the same in 9 of 10 seeds with 60 replays and 6 of 6 with 240 (lead about 1.1 ± 0.5 points).
   - At 6.05, the top pick was the same in 7 of 8 seeds.
   - More replays wouldn't change picks much and cost 4× the time. Better: **adaptive** — run 180 replays only when the top two are within 2 standard errors.
2. **Opponents are modeled on the wrong anchor (A1), with scatter that isn't validated.**
   - The app's scatter (1.5 + 0.12·ADP) is 3–4 times smaller than the gap between Yahoo and ESPN ADP.
   - That gap isn't the same thing as draft-to-draft variation within one league, but it shows how much sources disagree.
3. **Projection uncertainty is too small and moves all categories together (B1).**
4. **Positions aren't enforced when scoring teams.** The matchup scoring ignores positions; the position bonus is only a rough stand-in (+0.8, −0.7 and +2.9 in the backtest, mostly not significant).
5. **The simulator picks with one rule and scores with another** (section 8).
6. **Its added value beyond the base score is unproven.** The whole-team approach vs value + market: +7.2, −1.6 and −0.8 across 3 seasons.

---

## 10. Backtesting

### Available historical data
The ESPN public feed has preseason projections, actual averages and every box score for 2023-24, 2024-25 and 2025-26. Basketball Reference has per-game tables for 2021-22 to 2025-26.

**Not available:** past ADP, past FanScout projections, and multi-year keeper outcomes. So the market is represented by a **proxy**: half projection, half last season's value, meaning "reputation". The keeper model can't be backtested.

### Design
- 10 teams, 15 rounds, 3rd-round reversal.
- Opponents draft off the market with the app's scatter.
- Your pick follows each strategy, using only preseason information on the app's z scale.
- Every league is scored on real week-by-week H2H: all 9 categories, percentages from makes and attempts, fewer turnovers is better, and injured games filled by a waiver player.
- Uncertainty is estimated by resampling **weeks** (resampling drafts understates it because every draft shares the same weeks).

### Results
Pick 5, reputation market; difference in weekly win rate, with 95% week-bootstrap interval:

| Comparison | 2025-26 | 2024-25 | 2023-24 | Average | Verdict |
|---|---|---|---|---|---|
| Games-weighted value vs per-game value | **+19.1** | **+4.4** | −0.7 | +7.6 | Keep; put it on the board |
| Market 0.5 vs none | **−5.2** | **+12.8** | **+3.4** | +3.7 | Keep 0.5; fix its inputs |
| Market 0.25 vs none | −0.9 | **+5.4** | +1.1 | +1.9 | 0.5 is better on average |
| Don't-reach rule vs value + market | **−1.7** | **+2.9** | **+3.8** | +1.7 | Keep |
| Position bonus | +0.8 | −0.7 | **+2.9** | +1.0 | Keep as a tiebreaker |
| Whole-team greedy vs value + market | **+7.2** | −1.6 | −0.8 | +1.6 | Mixed: don't add more complexity |
| Measured per-category spreads vs spread 5 (both whole-team) | −0.9 | +1.6 | +4.6 | +1.8 | Inconclusive; display fix only |
| Categories rescaled by their weekly noise (G-score style) | −1.1 | +1.9 | +4.8 | +1.9 | Inconclusive; don't change |
| Categories rescaled to equal spread | — | +4.1 | −0.1 | — | Inconclusive; don't change |
| Commit to Punt FT% from pick 1 | −43.5 | — | — | — | Don't punt early |
| Commit to Punt TO from pick 1 | −11.3 | — | — | — | Don't punt early |

Bold means the 95% interval excludes zero.

- **With a pure-projection market**, the differences are small: the market blend and don't-reach rule do nothing, while games weighting is still +5 to +18.
- **Picks 1 and 10 (2025-26)** give the same signs as pick 5.

### Caveats
- The projections are ESPN's alone, not the app's blend.
- The market is a proxy.
- Opponents are naive, so absolute win rates are inflated; only the *differences* matter.
- No lineup positions, and no in-season moves beyond filling injured games.
- The keeper value, the full look-ahead and the plan simulator weren't backtested directly (they're JavaScript). The whole-team strategy approximates what they do.

---

## 11. Calibration

| Output | Does "70%" mean 70%? |
|---|---|
| Plan win % and league-comparison win % | **No.** Too extreme: the weekly spread is too small for 5 categories, and projection sd is 1.5 vs 2.3–2.5 in reality. |
| "% still there" | The card model and the simulator model agree with each other to within about 5–8 points. **Externally not validated**, and anchored on the wrong ADP (A1). Can't be interpreted as calibrated until it's checked against real draft logs. |
| Games played | Over-projected by 6–13 games per season; correlation with actual 0.39–0.62. |
| Projection uncertainty (`projSd`) | Too small (1.5 vs about 2.4 for ESPN alone). Categories actually miss independently. |
| Breakdown risk for older players (`breakRisk`) | A judgment call, not tested; plausible in direction. |
| Look-ahead leads | Honest about simulation noise, but that noise inherits B1, so the tie bands are too narrow. |

---

## 12. Stress tests (live app)

| Scenario | App's pick | Why | Assessment |
|---|---|---|---|
| Balanced, 1.05 | Edwards | Look-ahead best, Tatum +0.85 ± 0.85 behind (a tie), Maxey 1.4 behind | Fine, but it's a tie, not a "clear" pick |
| Jokić unexpectedly available at 1.05 | Jokić | About 20 points ahead | Correct |
| Balanced at 2.06 after Edwards | Curry | Mitchell has the best expected value; Curry is 0.37 ± 0.96 behind, and the tie-break gives it to the plan's pick | Acceptable tie, but the tie-break drives it |
| Win-now at 2.06 | **Amen Thompson** | Mitchell is best; Amen is 1.01 ± 1.98 behind, "tied" because of his own uncertainty; the plan is Punt FT%+3PM, "Close call" | **Wrong: bug A2** |
| Build for the future at 2.06 | Cooper Flagg | Keeper value 2.0 × weight; Mitchell 0.16 behind | Sensible |
| Punt FT% with FT-poor bigs, 4.05 | Maxey (elite FT) | His PTS/3PM/STL/AST still help; Kawhi tied | Defensible: elite value can beat fit |
| No guards (5 bigs), 6.05 | Trey Murphy | Haliburton 1.4 behind and 78% likely to last | Sensible |
| No assists (team −4.7 AST), 5.06 | Kawhi | 4.5 ahead; Haliburton (assists) about 100% likely to last | Sensible: fit doesn't override a large value gap |
| All guards (−5 REB, −3.4 BLK), 5.06 | Haliburton (another guard) | The team model turns it into a guard build; Reaves 2.9 behind | Model-consistent, but shows the simulator's pick-rule vs scoring-rule mismatch |
| Higher risk vs safer, 6.05 | Duren over Haliburton (injury risk, 62 games) | Haliburton 78% likely to last to 7.06 | Correct use of availability |

### Why the pick wins at 1.05 (look-ahead values in points of weekly win rate, keeper value included)

| Player | Per-game value | Games share | Market shift | Season value (simulator) | Future term (0.4·keeper) | Chance he's there next turn | Look-ahead EV | Behind best |
|---|---|---|---|---|---|---|---|---|
| Edwards | 5.51 | 1.00 | 0.00 | 5.51 | 1.35 | 1% | 73.37 | best |
| Tatum | 5.11 | 1.00 | −0.06 | 5.04 | 0.81 | 4% | 72.52 | 0.85 ± 0.85 |
| Maxey | 4.76 | 1.00 | −0.25 | 4.50 | 0.87 | 32% | 71.98 | 1.39 ± 0.73 |
| Curry | 4.98 | 0.90 | −0.98 | 3.19 | 0.11 | 85% | 67.66 | 5.70 ± 0.77 |
| Kawhi | 7.03 | 0.86 | **−3.10** | 2.79 | 0.64 | 100% | 66.94 | 6.42 ± 0.88 |

Kawhi has the highest per-game value on the board but ranks last here. Two things drag him down: the market shift (his FantasyPros ESPN ADP is 42, vs 28 on ESPN live and 17 on Yahoo), and games played. **Part of that is bug A1 and double count B5.**

---

## 13. Proposed changes, ranked by importance

For each change: **why** (the problem and evidence), then **how**, then **how to test**.

1. **Replace the ADP source with ESPN's live ADP (A1).**
   - *Why:* the league drafts on ESPN. The FantasyPros "ESPN" column is off by a median of 13 picks, and it feeds the availability odds, the simulated opponents and the market blend.
   - *How:* the Python pipeline pulls `ownership.averageDraftPosition` from the ESPN feed and stores `adp_espn_live` next to the current values.
   - *Test:* check that the stress-test picks still make sense; then, after the real draft, compare which ADP predicted the actual pick order best (change 10).

2. **Fix the tie-break (A2).**
   - *Why:* a lower-EV player can win on a rule.
   - *How:* among tied candidates, prefer the plan's pick only when the plan's confidence is at least "Leaning this way" and the pick's own standard error isn't more than 1.5× the best candidate's. Otherwise take the highest mean.
   - *Test:* the win-now 2.06 scenario should return Mitchell; the other stress tests should be unchanged.

3. **Use one player value everywhere (A4, section 7).**
   - *Why:* the board, cards, keeper value and practice opponents ignore games, the simulator doesn't, and games weighting is the best-supported component (+7.6 on average).
   - *How:* add a single `seasonValue(p)` (the `effZ` vector) and use it for:
     - the board Rank and Value, keeping per-game value as a secondary figure;
     - `cv` on the pick cards;
     - the look-ahead candidates (top 6 by `seasonValue` plus the plan's pick);
     - `keeperPlan` (games-weighted);
     - `smartPick`.
   - *Test:* the board order should match the simulator order; stress tests unchanged or improved; and check across 50 practice drafts whether the look-ahead's winner ever falls outside the new candidate set.

4. **Make the market blend games-consistent and category-appropriate (B5, section 6).**
   - *Why:* the blend double-discounts injury-prone players and imports points-league value.
   - *How:* build `valueAtPick` from season values (games-weighted), and use as the anchor a mix of ESPN live ADP and ESPN's category-league rank (start 50/50). Keep the weight at 0.5.
   - *Test:* a backtest variant with a games-consistent table (3 seasons); after the draft, the log (change 10).

5. **Recalibrate uncertainty (B1, B2).**
   - *Why:* the tie bands and displayed probabilities rely on it.
   - *How:*
     - `projSd` goes from 1.5 to about 2.1, applied as independent category shocks (about 0.7 per category) plus a small shared component;
     - expected games = 0.85 × projected, capped at 82 (instead of the 72 cap), used in `gamesShare`.
   - *Test:* coverage, i.e. in each past season, whether about 80% of players land inside the app's 80% interval. Re-run the backtest's games-weighted strategy with the new games rule.

6. **Make the displays honest (B3, B4).**
   - *Why:* the win percentages are overconfident.
   - *How:* per-category weekly spreads from `weekly_sd.json` (fitted on held-out weeks) in `matchup()`, and re-measure `WIN_PER_Z` with the new model in the same change.
   - *Test:* on held-out weeks, predicted category-win probabilities vs actual frequencies (calibration curve). Decision impact is expected to be small (it was inconclusive in the backtest).

7. **Include `S.savvy`, keepers and `TUNE` in the look-ahead cache key (A3).**
   - *Why:* stale recommendations. *How:* one line. *Test:* change the setting and confirm the recommendation refreshes.

8. **Adaptive simulation count.**
   - *Why:* spend compute only on near-ties.
   - *How:* if the top two are within 2 standard errors, re-run those two with 180 replays.
   - *Test:* seed stability of the top pick should go from about 90% to about 99% at 2–3× cost, only in close cases.

9. **Age adjustment for this season (optional; B6).**
   - *Why:* players 31+ underperform slightly in every season.
   - *How:* about −0.4 value for 31+ this season.
   - *Test:* fit on two seasons and test on the third; adopt it only if it improves the held-out error.

10. **Log the real draft.**
    - *Why:* the opponent model and availability odds can only be calibrated with real picks from your league.
    - *How:* export pick number, player and team, plus each player's ADP, category rank and "% still there" at the time of the pick.
    - *Test:* after the draft, compute the log-likelihood of the actual picks under each anchor and scatter setting.

**Pipeline (enables all of the above):** move the data scripts from the temp folder into `fantasy-draft/pipeline/`, and have a single command regenerate the app's data block with source dates.

---

## 14. Changes that should NOT be made

- Don't drop or cut the market blend because of 2025-26 alone; it helped in 2 of 3 seasons (+3.7 on average).
- Don't switch to G-scores (categories re-weighted by weekly noise) or re-normalize the category scale. No backtest evidence of improvement.
- Don't add explicit "scarcity", "category need" or schedule factors on top. The whole-team approach already captures diminishing returns, and its extra value is unproven; more components wouldn't be testable.
- Don't raise the simulation count everywhere; the picks are already stable, so use the adaptive option.
- Don't make punts easier to recommend; fixed punts backtested badly.
- Don't rewrite the draft-day app in Python (next section).
- Don't remove plan memory or the don't-reach rule.

---

## 15. Python vs HTML, and a proposed improved architecture

**Draft day: keep the HTML app.**
- It opens instantly in a browser, needs no install or server, and redraws in about 10 ms.
- The look-ahead runs in about 0.5 s.
- A Python UI (Streamlit, a notebook) would need a running server, rerun the whole script on every click, and be slower and more fragile during a live draft.

**Everything offline: Python.**
- Pulling sources, blending, calibrating and backtesting are data-science work, and Python is clearly better for them.
- Those scripts currently live in a temp folder and would be lost.

```
fantasy-draft/
  draft-room.html          draft-day app (UI + simulator), reads a generated data block
  pipeline/                Python: fetch -> clean -> blend -> calibrate -> write data block (+ provenance/dates)
    fetch_espn.py, fetch_fanscout.py, fetch_fantasypros.py, news.py, blend.py, build_datablock.py
  analysis/                Python: calibration + backtests (this folder); gate any model change
  data/                    cached raw sources by date
```

Inside the app, with no new components, just consolidation:
1. `seasonValue(p)` (one valuation) →
2. opponent model (ESPN live ADP + category rank, calibrated scatter) →
3. simulator (independent category shocks, calibrated games) →
4. look-ahead (candidates from `seasonValue`; ties decided by mean unless the plan is robust) →
5. calibrated displays.

---

## 16. Implementation plan (for after review)

1. **Phase 0, pipeline (Python, 1 session):** move the scripts into `pipeline/`; add the ESPN live ADP and category rank; regenerate the data block; diff against the current one.
2. **Phase 1, bugs (fast, low risk):** A2 tie-break, A3 cache key, A1 new ADP field (the app switches anchor), A5 practice opponents. Re-run the stress tests and self-test.
3. **Phase 2, one valuation:** `seasonValue` everywhere, and candidates from it. Check board/simulator agreement, the stress tests and 50 practice drafts.
4. **Phase 3, calibration:** games rule, `projSd` split by category, per-category weekly spreads and `WIN_PER_Z` re-measured together. Check coverage and calibration curves on held-out seasons and weeks.
5. **Phase 4, market inputs:** games-consistent anchor table and the ESPN ADP + category-rank mixture. Three-season backtest variant.
6. **Phase 5, post-draft:** export the draft log and fit the opponent scatter and anchor on the real picks for next season's keeper draft.

Each phase: backtest (`BT_SEASON=2024/2025/2026`), then stress tests, then the app self-test. Merge only if nothing regresses beyond the week-bootstrap noise.

---

## 17. Implemented (Sept 25, 2026), with the tests that decided each change

Backup before the changes: `draft-room.backup.html`. The one-time patch is in `pipeline/legacy/apply_audit_changes.py`.

| Change | Status | Evidence |
|---|---|---|
| A1: ESPN's live ADP + ESPN category rank as the market | **Done** (`espnAnchor`, `ESPN_MKT`, `pipeline/refresh_espn.py`) | FantasyPros' ESPN column was a median 13 picks off. ESPN's ADP only covers 13-round leagues and bunches up past pick ~115, so category rank is used alone there. |
| A2: tie-break | **Done**: the plan's pick only wins a tie when the plan is at least "Leaning", and a candidate whose own result is much noisier (standard error over 1.5× the best one's) can't count as tied | The win-now 2.06 case now gives the higher-EV player |
| A3: look-ahead cache key | **Done** (adds leaguemate sharpness, format, keepers, `TUNE`) | |
| A4 + one valuation | **Done**: `valueOf` = season value (games, market, age) for the board Rank and Value, cards, look-ahead candidates and practice opponents; per-game value shown on hover | Games weighting was +7.6 points on average (3 seasons) |
| A5: practice opponents | **Done** (season value) | |
| Keeper value in games-aware units | **Done**: future games share = halfway between this season's and full health; next year's pick values measured the same way. Re-tuned `deplete` 0.25 → 0.3 (8.8 keeper-worthy players per team, target 8–9) and the badge cutoff 3 → 2.4 (about 26 players) | |
| B1: projection uncertainty | **Done**: `projSd` 1.5 → 2.2; shocks per category (`MISS_CAT`, correlation 0.09) instead of one shock split evenly | 3-season misses: 2.3–2.5 for ESPN alone |
| B3/B4: weekly spread per category + `WIN_PER_Z` | **Done**: `WEEK_SD_CAT` from `calibration.json`; `WIN_PER_Z` 0.021 → 0.016 (measured ratio 0.76); every win-unit threshold scaled by `WU` so it keeps its value-point meaning | League win rates now 44–59% for a balanced league, instead of extreme values |
| Age 31+ this season | **Done**: `TUNE.ageNow` = −0.4 | Out-of-sample: +4.6, +1.9, +0.7, −0.3, −0.3, −0.4 (average +1.0; never clearly worse) |
| Adaptive simulation count | **Done**: if the top two are within 2 standard errors, the top three are replayed 180 times | Pick stable in 7 of 8 seeds at 60 replays; this cuts the noise by √3 in close calls. About 1.9 s in close calls, 0.5 s otherwise. |
| Draft log export + `analysis/fit_opponent_model.py` | **Done** | On a practice draft whose opponents used the 50/50 ESPN mix, the script picked that mix as the best fit (log-likelihood −414 vs −444 or worse) |
| Games calibration (0.85 × projected games, share of 82) | **Rejected** | `backtest_variants.py`: −0.3, −3.9, −0.2, +0.9, −0.1, −7.2 vs the current `min(1, G/72)` |
| Market anchor on season values (B5) | **Rejected** | +3.6, +0.2, +0.9, −3.2, −2.7, +1.7: no gain, so the per-game table stays |
| G-scores / equal-spread categories | **Not done** (as the audit recommended) | Inconclusive in the backtest |

### Validation after the changes
- **Self-test:** passes, with new checks for the ESPN anchor, the shock scaling and games weighting.
- **Console:** no errors.
- **Practice drafts following Recommended** (ADP opponents and smart opponents): the Recommended card was first at every pick, the plan list started with it at every pick, no other card carried the plan label, and there were no errors.
- **Stress tests:**

  | Scenario | Pick |
  |---|---|
  | 1.05 | Edwards (Maxey 1.0 ± 0.5 behind) |
  | Jokić falls to 1.05 | Jokić (+14) |
  | 2.06, all three future settings | Kawhi, tied with Anthony Davis and Towns (the quick pick wins the tie) |
  | Bigs with punt FT% | Maxey, and Balanced beats Punt FT% |
  | All guards | Chet Holmgren (previously another guard) |
  | No guards | Trey Murphy III |

### Before draft day
Run `python pipeline/refresh_espn.py`. It refreshes ESPN's ADP, category ranks and last-season stats, and lists team changes and injury tags to check against the injury notes in the app.

### After the draft
Export the draft log, then run `python analysis/fit_opponent_model.py draft-log-*.csv`. Set `TUNE.catRank` from the best ESPN mix before next year's keeper draft.


---

## 18. Ranking sources: what the evidence says (Sept 29, 2026)

**Question:** is the ranking "just ESPN ADP", and which sources should drive player value and the prediction of experienced leaguemates?

### Before this change
- **Player values:** projections (FanScout/ESPN 50/50) were met halfway with ESPN's market (ESPN ADP plus ESPN category rank).
- **Opponent model:** 70% ESPN and 30% the app's own rank.
- **Result:** the app's ranking agreed with ESPN's category rank (0.97) more than with the experts (0.93). In a test league drafting off the expert consensus, the app said Chet Holmgren, Austin Reaves and Trae Young were 99-100% sure to last from 2.06 to 3.06; all three were gone.

### Evidence
**1. Accuracy on the 2025-26 season** (`analysis/backtest_sources.py`). The sources were:
- the real preseason expert consensus (FantasyPros roto/category, 8 experts, Oct 18, 2025, from the Internet Archive);
- ESPN's preseason projections;
- last season's stats.

ESPN's own 2025-26 rank and ADP have since been overwritten, so they can't be tested.

| Source | Rank correlation with actual 2025-26 value |
|---|---|
| Experts | 0.721 |
| ESPN projection | 0.746 |
| Last season (reputation) | 0.596 |
| **Experts + projection, 50/50** | **0.758** |

The blend beats the experts alone by +0.037 (95% interval +0.009 to +0.069). The best weight on the experts is anywhere from 25-50%; the curve is flat there, and the app's halfway market pull (0.5) sits inside it.

**2. Draft backtest in a league drafting off the expert consensus** (`analysis/backtest_experts_league.py`, 2025-26, real weekly results). Projection met halfway with the experts, against projection only, in points of weekly win rate:

| You pick | vs projection only | vs just following the experts |
|---|---|---|
| 5th | **+6.5** | +5.6 |
| 1st | **+3.7** | **+10.9** |
| 10th | **+7.1** | **+9.0** |

Bold means the 95% interval excludes zero.

**3. Published work.** No comprehensive study of preseason fantasy basketball projection accuracy exists. One peer-reviewed study found professional projections beat naive last-season forecasts only moderately (Springer, *An evaluation of predictions for NBA "Fantasy Sports"*), which matches result 1.

### Changes made
- **Market for player value:** the FantasyPros expert consensus (6 experts now, including Yahoo's two analysts; refreshed every morning by `pipeline/refresh_fantasypros.py`), then Yahoo ADP, then ESPN. The weight stays 0.5.
- **Third projection source:** FantasyPros' consensus projections ("all the major projections combined"), a third of per-game stats, half for our own estimates. Games are unchanged. This is justified by the forecast-combination result above; FantasyPros' past projections weren't available to test.
- **Opponent model: leaguemates as types, not an averaged list.** In each simulated draft, each other manager drafts off the expert consensus (75% on **Sharp**, the new default for this league; 50% Mixed; 0% Casual) or off ESPN's list, with the usual scatter. The "% still there" odds mix the two in the same way.

  Averaging the lists made an in-between ranking nobody drafts from (Chet about 28th, when expert followers take him about 18th and ESPN followers about 58th).

  Calibration on 5-pick test drafts (Brier score, lower is better):

  | League actually drafts off… | App on Sharp | App on Casual |
  |---|---|---|
  | The experts | **0.030** | 0.126 |
  | ESPN | 0.082 | **0.017** |

  Sharp is the better choice whenever there's at least about a 40% chance the league drafts like the experts.
- **Displays:** the board and cards show "Experts #n"; the ADP tooltip shows ESPN ADP, ESPN category rank, Yahoo ADP and the expert range.
- **Draft log:** now records the expert rank, and `fit_opponent_model.py` tests the expert consensus and the app's Sharp/Mixed models against your league's real picks.

### After the change
- **Agreement:** the app's ranking agrees with the experts at 0.97 (was 0.93) and with ESPN's category rank at 0.93 (was 0.97). It still keeps projection-based opinions, such as Kawhi 17th vs the experts' 26th.
- **Checks:** self-test passes, no console errors, a full practice draft passes the consistency checks, and the stress tests are sensible.

## 19. League stress test: leaguemates with builds and mistakes (Sept 29, 2026)

**Question:** when leaguemates commit to different builds and make mistakes, does the app build around them and still win?

**Method:** `analysis/league_personas_test.js`, run in the live app.
- **Leagues:** 5 kinds of league, 4 drafts each, with you at 5th.
- **Leaguemates:** each drafts off the expert consensus or ESPN's list, with realistic scatter. Some commit to a build and reach for players who fit it. Some make mistakes (reaches of 15-45 spots, injured players, old vets, rookie hype).
- **Your picks, four ways, in the same leagues:**
  - the app's Recommended pick;
  - best available by the experts;
  - best available by ESPN's list;
  - the app's board order.
- **Season:** 600 simulated seasons per draft, each with:
  - a projection miss for every player (the size the app assumes);
  - a 19-week schedule, each week decided category by category with the measured weekly swings;
  - top 6 into the playoffs.
- **Three views of what's true:**
  - the app's values;
  - projections only;
  - "the experts are right". This is the skeptical check, since it grades the app on the list the experts drafting strategy uses.

An average team wins 9.5 of 19 weeks, makes the playoffs 60% of the time and wins the title 10% of the time.

| League | You draft by | Wins | Playoffs | Title | Wins if projections right | Wins if experts right |
|---|---|---|---|---|---|---|
| Control: everyone balanced, no mistakes | **App** | **12.9** | **92%** | **31%** | 14.2 | 11.5 |
| | Experts | 11.7 | 84% | 22% | 11.1 | 12.3 |
| | ESPN list | 9.7 | 62% | 13% | 11.2 | 8.2 |
| Builds: everyone commits to a different build, 5% mistakes | **App** | **12.2** | **88%** | **26%** | 12.8 | 11.7 |
| | Experts | 11.6 | 84% | 21% | 10.7 | 12.4 |
| | ESPN list | 9.9 | 67% | 11% | 10.3 | 9.6 |
| Messy: same builds, 20% mistakes, a Raptors homer, a vet lover, a rookie lover | **App** | **13.2** | **94%** | **33%** | 13.9 | 12.5 |
| | Experts | 12.9 | 94% | 33% | 12.5 | 13.3 |
| | ESPN list | 11.6 | 83% | 21% | 12.2 | 10.9 |
| Bigs rush: 5 teams chase big men from round 1-2 | **App** | **13.0** | **94%** | **31%** | 14.1 | 11.9 |
| | Experts | 11.9 | 88% | 22% | 11.6 | 12.3 |
| | ESPN list | 11.5 | 82% | 19% | 12.3 | 10.6 |
| Guards rush: 5 teams chase guards from round 1-2 | **App** | **11.7** | **85%** | **24%** | 12.4 | 10.9 |
| | Experts | 10.0 | 69% | 13% | 9.0 | 11.1 |
| | ESPN list | 9.7 | 62% | 12% | 10.6 | 8.8 |

The board-order strategy landed between the app and the experts; the full output is in the script.

**The app builds around the league.** Your team's average category rank (1 = best of 10):

| League | PTS | REB | AST | STL | BLK | 3PM | FG% | FT% | TO |
|---|---|---|---|---|---|---|---|---|---|
| Bigs rush | 2.0 | **9.5** | 3.0 | 2.3 | **8.8** | 1.5 | 7.8 | 1.3 | 7.3 |
| Guards rush | 6.3 | 3.0 | **9.8** | 5.0 | 2.8 | 6.3 | 4.0 | 5.3 | 2.8 |

- **Bigs rush:** when five teams hoarded big men, the app took the guards they left (Haliburton, Murray, Reaves, Bane, Quickley). It gave up rebounds and blocks and won points, threes, FT%, assists and steals.
- **Guards rush:** when five teams hoarded guards, it took the bigs instead (Chet, Bam, Jaren Jackson Jr., Okongwu, Zubac, Kel'el Ware).
- **Mistakes:** leaguemates' mistakes helped. The messy league was the app's best result.

**When you go off-script** (in the Builds league), the app re-plans around your picks. The cost is what the off-script picks themselves lose:

| Your first picks | Wins | Playoffs | Wins if experts right |
|---|---|---|---|
| Follow the app | 12.2 | 88% | 11.7 |
| Giannis, then Jalen Duren | 11.5 | 83% | 10.7 |
| Trae Young, then LaMelo Ball | 11.1 | 78% | 10.8 |
| Durant, then Curry | 10.3 | 71% | 8.8 |
| Three reaches (rounds 3, 6 and 9) | 11.5 | 81% | 11.0 |

**Giannis plus Duren doesn't mean you should punt FT%.** The app stayed Balanced and drafted good free-throw shooters to cover them. Committing to the simulator's Punt FT% plan instead did much worse:

| League | App (stays Balanced) | Committed Punt FT% |
|---|---|---|
| Control | 11.2 wins, 81% playoffs | 8.5 wins, 50% playoffs |
| Builds | 11.5 wins, 83% playoffs | 9.3 wins, 61% playoffs |

**Holes found** (all four fixed the same day; see *Fixes* below)
1. **Plan name.** The plan name can stay "Balanced" after the roster has become a guard team: in the bigs rush it was 9th-10th in rebounds and blocks. The card's "Already losing" line reports it, but the headline doesn't.
2. **Punt plans in the simulator.** They draft greedily for their categories, so Punt FT% turns into a full big-man build that is also 10th in points, assists and threes. The simulator therefore compares Balanced against a badly run punt, which is part of why the app rarely suggests punts other than Punt AST. A well-run punt hasn't been tested.
3. **Opponent model.** The simulator's leaguemates draft off the rankings and don't keep following the builds their rosters show. This didn't stop the app from adapting here, because the look-ahead scores against the real rosters already drafted.
4. **Encoding bug.** `draft-room.html` had no `<meta charset="utf-8">`. Chrome guesses UTF-8 when the file is opened by double-click, but when served or guessed differently the whole script failed on the accent-stripping regex.

### Fixes (Sept 29, 2026)

**1. Plan name.** Once a category is lost in over 70% of simulated weeks (the "Already losing" rule), the headline gets a tag naming the build the roster really plays like. The tag is the build sharing the most given-up categories, and it must share at least half of them, for example "Playing as Guard build" or "Playing as Punt BLK". Otherwise the tag reads "Also giving up …". The first-timer guide explains it.

In the stress leagues:
- **Guards rush:** "Playing as Punt AST" from round 4.
- **Bigs rush:** "Playing as Punt BLK" from round 9. Before that the team still won rebounds in 30-40% of weeks, so it wasn't giving them up yet.

**2. Punt plans play the categories they can still win** (`TUNE.dynW`). In the simulator, your future picks weigh each category by how much one more unit of it moves your weekly matchups against the other nine teams' projected final rosters, on top of the plan's weights:
- the weight is a normal density at the projected gap;
- the spread is the measured weekly swing, plus projection misses, plus the picks still to come.

A category you already win easily, or can't win, counts for less, so a plan stops piling onto one kind of player.

Real-season test: `analysis/backtest_dynamic.py`, results in `backtest_dynamic_results.txt`. It replays drafts from preseason information and scores them on real weekly results: 3 seasons, picks 1/5/10, and the expert market for 2025-26. Weekly win rate, averaged over the 12 runs:

| Plan | Fixed weights (before) | Category-aware (now) |
|---|---|---|
| Balanced | 64.5% | 65.9% (+1.3; ahead in 7 of 12 runs, tied in 1, behind in 4, two of them by 5+ points: 2024-25 from pick 1 and the 2025-26 expert market from pick 10) |
| Punt FT% | 27.3% | 54.0% (+26.7; ahead in 12 of 12) |
| Punt TO | 53.2% | 58.7% (+5.5; ahead in 10 of 12) |

A half-strength version (multipliers square-rooted) did slightly worse overall, so `dynW` is 1.

**3. Leaguemates keep drafting toward their plan** (`TUNE.oppBuilds`). A leaguemate's lean (`teamLean`, from 3 players) becomes category weights relative to a neutral roster. Among the next five players on their list, they take the best fit, giving up 0.3 value points per spot they reach. A balanced drafter's lean is near zero, so he still follows his list.

A cutoff of "50% sure of one build" almost never fired, because `teamLean` spreads a real lean over similar builds (a big-man drafter reads about 25% Big-man build and 20% Punt FT%). So the whole mix is used.

**4. Encoding.** Added `<meta charset="utf-8">`.

**The whole app, before vs after.** Same 5 leagues and 4 drafts each, with seeds paired so only the app changed. Your wins over 19 weeks:

| League | Before | Fix 2 only | Fixes 2 + 3 (now) |
|---|---|---|---|
| Control | 12.9 | 12.8 | 12.7 |
| Builds | 12.1 | 12.5 | 12.7 |
| Messy | 13.4 | 13.4 | 13.5 |
| Bigs rush | 13.1 | 13.1 | 13.4 |
| Guards rush | 11.7 | 12.0 | 11.8 |
| **Change, app's view** | | +0.14 ± 0.10 | **+0.19 ± 0.10** |
| **Change, if the experts are right** | | +0.05 ± 0.11 | **+0.30 ± 0.14** |

Playoff odds rose about 1 point. The gains come from leagues where people commit to builds. The balanced control league is flat within noise (-0.3 ± about 0.3).

**Giannis, then Duren** (control league, 4 drafts):
- **Committing to Punt FT%:** 8.5 wins and 50% playoffs before; 10.6 wins and 74% playoffs now.
- **Following the app:** it still stays Balanced and repairs FT%, at 11.0 wins and 80% playoffs.

The comparison between the two is now fair: the punt plan is played sensibly and still loses narrowly.

**Checks**
- **Speed:** the slowest pick took 2.4 s (usually 0.5-2 s).
- **App:** the self-test passes with no console errors.
- **Old behavior:** setting `TUNE.dynW` to 0 and `TUNE.oppBuilds` to false restores the previous simulator exactly.

**Limits**
- All three views of "true" are built from the same projection data. The experts-are-right column is the skeptical check, and there the pure expert list edges the app by 0.2-0.8 wins.
- Leaguemates scatter about ±3 picks early and ±10 around pick 70.
- In-season moves (waivers, streaming, trades) aren't modeled.
