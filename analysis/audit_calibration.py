"""Calibration checks for the draft model, using last season (2025-26) as a test set.

1. ESPN's 2025-26 preseason projections vs what actually happened: how big projection misses are
   (the app assumes TUNE.projSd = 1.5 value points), games-played misses, and whether weighting value by
   projected games predicts real season value better.
2. Does pulling projections toward a "market" view help? (Proxy market = last season's value, since
   2025 ADP isn't available.)
3. Week-to-week noise per category, measured from 24,884 real box scores, in the app's own z units
   (the app uses one weekly sd of 5 for every category).
4. Availability: the pick cards' chance() vs the simulator's ADP scatter, and how far apart real ADP
   sources are.

Run: python analysis/audit_calibration.py
"""
import math, random, statistics as st
from common import *

A = load_app(); P = app_players(A); Z = ZMap(P); E = load_espn()
B24 = load_bbref(os.path.join(DATA, 'bbref_2024-25_per_game.html'))
print('z-map fit, worst error on the app top 150 by category:', [round(e, 2) for e in Z.fit_err])

R = [st.mean(p['z'][k] for p in P[120:150]) for k in range(9)]           # the app's replacement profile
share = lambda g: min(1.0, g / 72.0)
season = lambda z, g: sum(z) * share(g) + sum(R) * (1 - share(g))          # games-weighted, waiver fill (effZ total)

# ---------- 1. projection misses ----------
rows = []
for k, e in E.items():
    if 'proj25' not in e or 'act25' not in e: continue
    pj, ac = e['proj25'], e['act25']
    if pj['G'] <= 0 or pj['MIN'] < 10: continue
    zp, za = Z.z(pj['line']), Z.z(ac['line'])
    rookie = key(e['name']) not in B24
    age = (B24.get(key(e['name'])) or {}).get('age')
    rows.append(dict(name=e['name'], zp=zp, za=za, vp=sum(zp), va=sum(za), gp=pj['G'], ga=ac['G'],
                     sp=season(zp, pj['G']), sa=season(za, ac['G']), rookie=rookie, age=(age + 1) if age else None,
                     last=(season(Z.z(B24[key(e['name'])]['line']), B24[key(e['name'])]['G']) if not rookie else None)))
rows.sort(key=lambda r: -r['sp'])
pool = rows[:200]                                                          # the draftable range
print('\n== 1. ESPN 2025-26 projections vs actual (top 200 by projected season value) ==')
def sd(x): return st.pstdev(x) if len(x) > 1 else float('nan')
per_game = [r['va'] - r['vp'] for r in pool if r['ga'] >= 20]
season_err = [r['sa'] - r['sp'] for r in pool]
print(f"per-game value miss (played 20+ games): sd {sd(per_game):.2f}, mean {st.mean(per_game):+.2f}  (n={len(per_game)})")
print(f"season value miss incl. games (waiver fill): sd {sd(season_err):.2f}, mean {st.mean(season_err):+.2f}  (app assumes sd 1.5)")
for lab, f in (('rookies', lambda r: r['rookie']), ('age <= 24', lambda r: not r['rookie'] and r['age'] and r['age'] <= 24),
               ('age 25-30', lambda r: r['age'] and 25 <= r['age'] <= 30), ('age 31+', lambda r: r['age'] and r['age'] >= 31)):
    x = [r['sa'] - r['sp'] for r in pool if f(r)]
    if x: print(f"   {lab:10s} n={len(x):3d}  season miss sd {sd(x):.2f}  mean {st.mean(x):+.2f}")
gerr = [r['ga'] - r['gp'] for r in pool]
print(f"games: projected mean {st.mean(r['gp'] for r in pool):.1f}, actual mean {st.mean(r['ga'] for r in pool):.1f}, miss sd {sd(gerr):.1f}")
buck = {}
for r in pool: buck.setdefault(min(4, int((r['gp'] - 40) // 10)) if r['gp'] >= 40 else -1, []).append(r['ga'])
for b in sorted(buck): print(f"   projected {'<40' if b < 0 else f'{40 + 10 * b}-{49 + 10 * b}' if b < 4 else '80+'} games: actual mean {st.mean(buck[b]):.1f}  n={len(buck[b])}")
# does weighting by projected games help predict real season value?
sa = [r['sa'] for r in pool]
print(f"predict actual season value: corr(per-game projection) {st.correlation([r['vp'] for r in pool], sa):.3f}"
      f"  vs corr(games-weighted projection) {st.correlation([r['sp'] for r in pool], sa):.3f}")
# per-category misses: are they one shared shock (how the app models it) or category by category?
print('per-category per-game misses (sd):', ' '.join(f"{c} {sd([r['za'][q] - r['zp'][q] for r in pool if r['ga'] >= 20]):.2f}" for q, c in enumerate(CATS)))
cats_err = [[r['za'][q] - r['zp'][q] for r in pool if r['ga'] >= 20] for q in range(9)]
avg_r = st.mean(st.correlation(cats_err[a], cats_err[b]) for a in range(9) for b in range(9) if a < b)
print(f"average correlation between category misses: {avg_r:+.2f}  (the app's shock is split evenly: correlation +1)")

# ---------- 2. market-style shrinkage (proxy: last season's value) ----------
print('\n== 2. Blend projection with a market proxy (last season value) ==')
vets = [r for r in pool if r['last'] is not None]
for w in (0, 0.1, 0.2, 0.3, 0.5):
    pred = [(1 - w) * r['sp'] + w * r['last'] for r in vets]
    rmse = math.sqrt(st.mean((p - r['sa']) ** 2 for p, r in zip(pred, vets)))
    print(f"   weight {w:.1f} on last season: RMSE {rmse:.3f}  corr {st.correlation(pred, [r['sa'] for r in vets]):.3f}")

# ---------- 3. week-to-week noise per category, in the app's z units ----------
print('\n== 3. Weekly noise per category (real 2025-26 box scores) ==')
ppl = [e for e in E.values() if e['games'] and 'act25' in e and e['act25']['G'] >= 20]
for e in ppl: e['za'] = Z.z(e['act25']['line'])
ppl.sort(key=lambda e: -season(e['za'], e['act25']['G']))
ppl = ppl[:170]
days = sorted({d for e in ppl for d in e['games']})
d0 = days[0]; week = lambda d: (d - d0) // 7
nweeks = week(days[-1]) + 1
for e in ppl:
    wk = [[0.0] * 11 for _ in range(nweeks)]
    for d, line in e['games'].items():
        w = wk[week(d)]
        for i in range(11): w[i] += line[i]
    e['wk'] = wk
full = [w for w in range(nweeks) if sum(1 for e in ppl for d in e['games'] if week(d) == w) > 200]   # skip part weeks / break
rng = random.Random(7)
teams = []
for s in range(60):                        # realistic 13-man rosters: snake draft on actual value with noise
    order = sorted(range(len(ppl)), key=lambda i: i + rng.gauss(0, 2 + 0.15 * i))
    for t in range(10):
        teams.append([ppl[order[r * 10 + (t if r % 2 == 0 else 9 - t)]] for r in range(13)])
# team strength in app units = sum of per-game z x games share; weekly outcome from the box scores
mu_fg = sum(e['act25']['line'][6] for e in ppl) / sum(e['act25']['line'][7] for e in ppl)
mu_ft = sum(e['act25']['line'][8] for e in ppl) / sum(e['act25']['line'][9] for e in ppl)
def strength(tm): return [sum(e['za'][q] * share(e['act25']['G']) for e in tm) for q in range(9)]
def weekly(tm, w):
    t = [sum(e['wk'][w][i] for e in tm) for i in range(11)]
    return [t[0], t[1], t[2], t[3], t[4], t[5], t[6] / t[7] if t[7] else 0, t[8] / t[9] if t[9] else 0, -t[10]]
S_ = [strength(tm) for tm in teams]
W_ = [[weekly(tm, w) for w in full] for tm in teams]
pairs = [(rng.randrange(len(teams)), rng.randrange(len(teams))) for _ in range(6000)]
pairs = [(a, b) for a, b in pairs if a != b]
sig = []
for q, c in enumerate(CATS):
    obs = []
    for a, b in pairs:
        dS = S_[a][q] - S_[b][q]
        for wi in range(len(full)):
            x, y = W_[a][wi][q], W_[b][wi][q]
            obs.append((dS, 1.0 if x > y else 0.5 if x == y else 0.0))
    best = None
    for s10 in range(10, 400, 2):          # 1-D maximum likelihood for the probit scale
        s_ = s10 / 10; ll = 0
        for dS, y in obs:
            p = min(1 - 1e-9, max(1e-9, ncdf(dS / s_))); ll += y * math.log(p) + (1 - y) * math.log(1 - p)
        if best is None or ll > best[0]: best = (ll, s_)
    spread = sd([s[q] for s in S_])
    sig.append(best[1])
    print(f"   {c:4s} weekly sd {best[1]:5.1f} z-units | spread of team strength {spread:4.2f} | edge of +1 sd of spread wins {ncdf(spread / best[1]):.0%} of weeks")
print('   the app uses weekly sd 5.0 for every category')
open(os.path.join(HERE, 'weekly_sd.json'), 'w').write(json.dumps(dict(zip(CATS, sig))))

# ---------- 4. availability ----------
print('\n== 4. Availability ==')
def chance(i, m):                          # the pick cards
    if m <= 0: return 1
    s = max(1.3, m * 0.2); return 1 / (1 + math.exp((m - i - 0.5) / s))
def sim_survive(adp_rank, m, n=4000):      # the simulator: others pick by ADP + N(0, 1.5 + 0.12*ADP)
    rng2 = random.Random(1); cnt = 0
    for _ in range(n):
        board = sorted(range(1, adp_rank + m + 60), key=lambda a: a + rng2.gauss(0, 1.5 + 0.12 * a))
        cnt += board.index(adp_rank) >= m
    return cnt / n
print('   survival of a player with i better-ADP players left, over m picks: cards vs simulator')
for m in (9, 11):
    print('   m=%d: ' % m + '  '.join(f"i={i}: {chance(i, m):.0%}/{sim_survive(i + 1, m):.0%}" for i in (4, 7, 9, 11, 14, 18)))
ya_es = [(p['adp'][0], p['adp'][1]) for p in P if p['adp'] and None not in p['adp']]
for lo, hi in ((1, 30), (31, 70), (71, 130)):
    d = [a - b for a, b in ya_es if lo <= (a + b) / 2 <= hi]
    print(f"   ADP {lo}-{hi}: Yahoo vs ESPN gap sd {sd(d):.1f} picks (n={len(d)}); simulator sd at ADP {(lo + hi) // 2}: {1.5 + 0.12 * (lo + hi) / 2:.1f}")
rr = [(e['roto_rank'], e['espn_adp'], e['name']) for e in E.values() if e.get('roto_rank') and e.get('espn_adp') and e['espn_adp'] < 130]
print(f"   ESPN category-league rank vs ESPN ADP: corr {st.correlation([a for a, b, _ in rr], [b for a, b, _ in rr]):.2f}; biggest gaps:",
      sorted(rr, key=lambda x: -abs(x[0] - x[1]))[:6])
