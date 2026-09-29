"""Does drafting for the categories your team can still win beat drafting for fixed category weights?

The app's simulator fills your future picks with a fixed weighting per plan (Balanced counts every category
equally, Punt FT% zeroes FT% and leans on rebounds, blocks and FG%). Fixed weights never notice that a team
already wins a category easily or can't win it at all, so a punt plan keeps stacking the same kind of player:
Punt FT% became an all-bigs team that also lost points, assists and threes (MODEL_AUDIT.md section 19).

DYN_* weighs each category by how much one more unit of it raises your chance of winning it against the other
nine teams' projected final rosters (a normal density at the projected gap, with the measured weekly spread
plus projection and rest-of-draft uncertainty), on top of the plan's own weights. This is the linear version of
TEAM_G's roster-fit rule, cheap enough to run inside the simulator.

Replays drafts with only preseason information and scores them on real week-by-week results (backtest_2025.py),
for 3 seasons, with a week bootstrap for the intervals.
Run: python analysis/backtest_dynamic.py [drafts=150]
"""
import os, sys, math, random, statistics as st, subprocess

NDR = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 150
if os.environ.get('BT_SEASON') is None:          # run each season in its own process (the module loads one season)
    for season in ('2024', '2025', '2026'):
        subprocess.run([sys.executable, __file__, str(NDR)], env={**os.environ, 'BT_SEASON': season}, check=True)
    sys.exit()

import backtest_2025 as B
from backtest_robustness import run, compare

# the app's constants (draft-room.html): weekly spread per category, projection misses
WEEK_SD_CAT = [5.83, 5.39, 5.12, 9.47, 6.42, 7.78, 9.01, 8.97, 6.92]
W = {   # the app's BUILDS weights (win categories 1.35, punted 0, normalised to the number of counted categories)
    'bal': [1.0] * 9,
    'ft': [0.884, 1.193, 0.884, 0.884, 1.193, 0.884, 1.193, 0.0, 0.884],
    'to': [1.193, 0.884, 1.193, 0.884, 0.884, 1.193, 0.884, 0.884, 0.0],
}
phi = lambda x: math.exp(-x * x / 2)


def dyn_mult(av, mine, rosters, k, w):
    """per-category multipliers: how much a unit of each category is worth to this roster right now"""
    av = sorted(av, key=lambda i: B.pool[i]['mrank'])[:150 - k]      # who the rest of the draft takes
    fill = [st.mean(B.pool[i]['effm'][q] for i in av) for q in range(9)] if av else [0.0] * 9
    proj = lambda r: [sum(B.pool[i]['effm'][q] for i in r) + (15 - len(r)) * fill[q] for q in range(9)]
    me = proj(mine); rest = 15 - len(mine)
    m = [0.0] * 9
    for t, r in enumerate(rosters):
        if t == B.MY: continue
        o = proj(r)
        for q in range(9):
            sd = math.sqrt(WEEK_SD_CAT[q] ** 2 + 11.4 + 1.6 * rest)
            m[q] += phi((me[q] - o[q]) / sd) / sd
    cnt = [q for q in range(9) if w[q] > 0]
    avg = sum(m[q] for q in cnt) / len(cnt)
    return [m[q] / avg for q in range(9)]


def dyn(plan, alpha=1.0):
    """alpha shrinks the multipliers toward 1 (0 = the fixed weights, 1 = fully dynamic)"""
    w = W[plan]
    def pick(av, mine, rosters, k):
        mu = [x ** alpha for x in dyn_mult(av, mine, rosters, k, w)]
        return max(av, key=lambda i: sum(w[q] * mu[q] * B.pool[i]['effm'][q] for q in range(9)))
    return pick


def fixed(plan):
    w = W[plan]
    return lambda av, mine, rosters, k: max(av, key=lambda i: sum(w[q] * B.pool[i]['effm'][q] for q in range(9)))


if __name__ == '__main__':
    markets = ['reputation'] + (['experts'] if B.SEASON == 2026 else [])
    S = [('FIX_BAL', fixed('bal')), ('DYN_BAL', dyn('bal')), ('HALF_BAL', dyn('bal', 0.5)),
         ('FIX_FT', fixed('ft')), ('DYN_FT', dyn('ft')), ('HALF_FT', dyn('ft', 0.5)),
         ('FIX_TO', fixed('to')), ('DYN_TO', dyn('to')), ('HALF_TO', dyn('to', 0.5))]
    B.set_market('reputation')
    SIG = B.fit_sigma([w for i, w in enumerate(B.WEEKS) if i % 2 == 0])
    S.append(('TEAM_G', B.make_strategy('TEAM_G', SIG)))
    season = {2024: '2023-24', 2025: '2024-25', 2026: '2025-26'}[B.SEASON]
    for market in markets:
        for slot, n in ((4, NDR), (0, NDR // 2), (9, NDR // 2)):
            res = run(S, market, n, slot)
            wr = {k: sum(v) / len(v) for k, v in res.items()}
            print(f"\n== {season}, market={market}, pick {slot + 1}, {n} drafts: weekly win ==")
            print('   ' + '  '.join(f"{k} {v:.1%}" for k, v in wr.items()))
            for a, b in (('DYN_BAL', 'FIX_BAL'), ('HALF_BAL', 'FIX_BAL'), ('DYN_FT', 'FIX_FT'), ('HALF_FT', 'FIX_FT'),
                         ('DYN_TO', 'FIX_TO'), ('HALF_TO', 'FIX_TO'), ('TEAM_G', 'FIX_BAL')):
                d, lo, hi = compare(res, a, b)
                print(f"   {a:8s}- {b:8s}: {d:+.1%}  (95% week-bootstrap {lo:+.1%} to {hi:+.1%}){'  <- clear' if lo > 0 or hi < 0 else ''}")
        sys.stdout.flush()
