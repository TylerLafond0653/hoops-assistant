"""Age adjustment on its own, leave-one-season-out: for each test season the 31+ adjustment is the average
extra miss of the OTHER two seasons (2023-24 -0.13, 2024-25 -0.45, 2025-26 -0.68; audit_projection_seasons.py).
Run: BT_SEASON=2025 python analysis/backtest_age.py [drafts=150]"""
import sys
import backtest_2025 as B
from backtest_robustness import run, compare
import backtest_variants as V
ND = int(sys.argv[1]) if len(sys.argv) > 1 else 150
EXTRA = {2024: -0.13, 2025: -0.45, 2026: -0.68}
adj = sum(v for k, v in EXTRA.items() if k != B.SEASON) / 2
def make(a):
    def pick(av, mine, rosters, k):
        def val(i):
            p = B.pool[i]; ag = V.age_of(p)
            return p['vsm'] + (a if ag is not None and ag >= 31 else 0)
        return max(av, key=val)
    return pick
print('season', B.SEASON, '| held-out age adjustment', round(adj, 2))
for market in ('reputation', 'projection'):
    res = run([('now', make(0)), ('age', make(adj))], market, ND, 4)
    m, lo, hi = compare(res, 'age', 'now')
    print(f"   {market:10s}: now {sum(res['now']) / len(res['now']):.1%}, with age adjustment {m:+.1%} ({lo:+.1%} to {hi:+.1%})")
