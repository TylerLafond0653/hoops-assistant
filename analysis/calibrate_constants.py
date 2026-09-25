"""Constants for the app, measured over three seasons (2023-24 to 2025-26). Writes calibration.json.
  weekly_sd[cat]   weekly spread of each category in the app's units (all weeks, injured games filled)
  proj_sd[cat]     per-category projection miss (per game) and the average correlation between categories
  proj_total_sd    season-value projection miss (ESPN alone)
Run: python analysis/calibrate_constants.py"""
import json, os, subprocess, sys, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__))
if len(sys.argv) > 1 and sys.argv[1] == 'one':
    import backtest_2025 as B
    from common import CATS
    B.set_market('reputation')
    sig = B.fit_sigma(B.WEEKS)
    Z, E = B.Z, B.E
    pool = sorted([p for p in B.pool if p['e'].get('act') and p['e']['act']['G'] >= 20], key=lambda p: -p['vs'])[:200]
    miss = [[Z.z(p['e']['act']['line'])[q] - p['zp'][q] for p in pool] for q in range(9)]
    print(json.dumps(dict(sig=sig, miss_sd=[st.pstdev(m) for m in miss],
                          miss_r=st.mean(st.correlation(miss[a], miss[b]) for a in range(9) for b in range(a + 1, 9)))))
    sys.exit()
out = {}
for season in (2024, 2025, 2026):
    r = subprocess.run([sys.executable, __file__, 'one'], env=dict(os.environ, BT_SEASON=str(season), PYTHONIOENCODING='utf-8'),
                       capture_output=True, text=True, cwd=HERE)
    out[season] = json.loads(r.stdout.strip().splitlines()[-1]); print(season, {k: (v if isinstance(v, float) else [round(x, 2) for x in v]) for k, v in out[season].items()})
CATS = ['PTS', 'REB', 'AST', 'STL', 'BLK', '3PM', 'FG', 'FT', 'TO']
res = dict(weekly_sd={c: round(st.mean(out[s]['sig'][q] for s in out), 2) for q, c in enumerate(CATS)},
           proj_sd={c: round(st.mean(out[s]['miss_sd'][q] for s in out), 2) for q, c in enumerate(CATS)},
           proj_r=round(st.mean(out[s]['miss_r'] for s in out), 3))
print(json.dumps(res, indent=1))
json.dump(res, open(os.path.join(HERE, 'calibration.json'), 'w'), indent=1)
