"""Projection accuracy across three seasons (ESPN preseason projections vs actual), on the app's z scale:
size of misses (the app assumes TUNE.projSd = 1.5), games-played bias, and misses by age.
Run: python analysis/audit_projection_seasons.py"""
import statistics as st
from common import *
P = app_players(); Z = ZMap(P)
share = lambda g: min(1.0, g / 72.0)
for season in (2024, 2025, 2026):
    E = load_espn(season=season); prior = load_bbref(os.path.join(DATA, PRIOR_BBREF[season]))
    rows = []
    for e in E.values():
        pj, ac = e.get('proj'), e.get('act')
        if not pj or pj['G'] <= 0 or pj['MIN'] < 12: continue
        zp = Z.z(pj['line']); za = Z.z(ac['line']) if ac and ac['G'] > 0 else None
        R0 = -4.3                                   # the app's replacement total
        sp = sum(zp) * share(pj['G']) + R0 * (1 - share(pj['G']))
        ga = ac['G'] if ac else 0
        sa = (sum(za) * share(ga) + R0 * (1 - share(ga))) if za else R0
        pr = prior.get(key(e['name'])); age = pr['age'] + 1 if pr else None
        rows.append(dict(sp=sp, sa=sa, vp=sum(zp), va=sum(za) if za else None, gp=pj['G'], ga=ga, age=age, rookie=pr is None))
    rows.sort(key=lambda r: -r['sp']); pool = rows[:200]
    err = [r['sa'] - r['sp'] for r in pool]; pg = [r['va'] - r['vp'] for r in pool if r['va'] is not None and r['ga'] >= 20]
    ages = {lab: [r['sa'] - r['sp'] for r in pool if f(r)] for lab, f in (('<=24', lambda r: r['age'] and r['age'] <= 24), ('25-30', lambda r: r['age'] and 25 <= r['age'] <= 30), ('31+', lambda r: r['age'] and r['age'] >= 31), ('rookie', lambda r: r['rookie']))}
    print(f"{season - 1}-{str(season)[2:]}: season-value miss sd {st.pstdev(err):.2f} (mean {st.mean(err):+.2f}) | per-game miss sd {st.pstdev(pg):.2f} | "
          f"games projected {st.mean(r['gp'] for r in pool):.1f} vs actual {st.mean(r['ga'] for r in pool):.1f} | corr(proj G, actual G) {st.correlation([r['gp'] for r in pool], [r['ga'] for r in pool]):.2f}")
    print('      mean miss by age: ' + '  '.join(f"{k} {st.mean(v):+.2f} (n={len(v)})" for k, v in ages.items() if v))
