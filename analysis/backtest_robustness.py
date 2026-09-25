"""Robustness checks for backtest_2025.py.

Every replayed draft is scored on the same 23 weeks of one season, so the spread across drafts understates
the real uncertainty. Here each comparison is also bootstrapped over weeks (resampling whole weeks), and the
key strategies are re-run from other draft slots and with a smaller market pull (0.25).

Run: python analysis/backtest_robustness.py [drafts=200]
"""
import sys, os, random, statistics as st, math
sys.argv = sys.argv[:1] + sys.argv[1:]
import backtest_2025 as B

NDR = int(sys.argv[1]) if len(sys.argv) > 1 else 200

def per_week(rosters, me):
    """your weekly result (share of the 9 matchups won) for every week"""
    C = [[B.team_week_cats(r, w, True) for w in B.WEEKS] for r in rosters]
    out = []
    for wi in range(len(B.WEEKS)):
        s = 0.0
        for o in range(10):
            if o == me: continue
            x, y = C[me][wi], C[o][wi]
            ca = sum(1.0 if x[q] > y[q] else 0.5 if x[q] == y[q] else 0.0 for q in range(9))
            s += 1.0 if ca > 4.5 else 0.5 if ca == 4.5 else 0.0
        out.append(s / 9)
    return out

def run(strats, market, ndraft, slot=4):
    B.set_market(market); B.MY = slot
    B.MY_PICKS[:] = [k for k, t in B.ORDER if t == slot]
    res = {}
    for name, fn in strats:
        weeks = [0.0] * len(B.WEEKS)
        for s in range(ndraft):
            pw = per_week(B.run_draft(fn, 1000 + s), slot)
            for i, v in enumerate(pw): weeks[i] += v / ndraft
        res[name] = weeks
    return res

def compare(res, a, b, nboot=4000):
    d = [x - y for x, y in zip(res[a], res[b])]; rng = random.Random(3); bs = []
    for _ in range(nboot):
        s = [d[rng.randrange(len(d))] for _ in d]; bs.append(sum(s) / len(s))
    bs.sort()
    return sum(d) / len(d), bs[int(0.025 * nboot)], bs[int(0.975 * nboot)]

if __name__ == '__main__':
    B.set_market('reputation')
    SIG = B.fit_sigma([w for i, w in enumerate(B.WEEKS) if i % 2 == 0])
    names = ['ADP', 'VALUE', 'VALUE_G', 'VALUE_GM', 'WAIT', 'POS', 'GSCORE', 'TEAM_5', 'TEAM_G']
    S = {n: B.make_strategy(n, SIG) for n in names}

    # market pull of 0.25 instead of 0.5
    def value_gm25(av, mine, rosters, k):
        return max(av, key=lambda i: B.pool[i]['vs'] + 0.5 * (B.pool[i]['vsm'] - B.pool[i]['vs']))
    # the wait rule on top of games-weighted value without the market pull
    def wait_g(av, mine, rosters, k):
        j = B.MY_PICKS.index(k); g = (B.MY_PICKS[j + 1] - k - 1) if j + 1 < len(B.MY_PICKS) else 0
        if g <= 0: return max(av, key=lambda i: B.pool[i]['vs'])
        by_adp = sorted(av, key=lambda i: B.pool[i]['mrank'])
        q = {i: B.chance(n, g) for n, i in enumerate(by_adp)}
        vals = sorted((B.pool[i]['vs'] for i in av), reverse=True); X = vals[min(g, len(vals) - 1)]
        return max(av, key=lambda i: (1 - q[i]) * (B.pool[i]['vs'] - X))

    # each category rescaled to equal spread over the top 150 (instead of FanScout's uneven scale)
    top150 = sorted(range(B.NP), key=lambda i: -B.pool[i]['vs'])[:150]
    SDC = [st.pstdev([B.pool[i]['zp'][q] for i in top150]) for q in range(9)]
    print('category spread over the top 150 (app z scale):', dict(zip(B.CATS, [round(x, 2) for x in SDC])))
    def norm_g(av, mine, rosters, k):
        return max(av, key=lambda i: sum(B.pool[i]['eff'][q] / SDC[q] for q in range(9)))

    pairs = [('VALUE_G', 'VALUE'), ('VALUE_G', 'ADP'), ('VALUE_GM', 'VALUE_G'), ('VALUE_GM25', 'VALUE_G'), ('WAIT', 'VALUE_GM'),
             ('WAIT_G', 'VALUE_G'), ('POS', 'VALUE_GM'), ('GSCORE', 'VALUE_GM'), ('TEAM_5', 'VALUE_GM'), ('TEAM_5', 'VALUE_G'), ('TEAM_G', 'TEAM_5'), ('NORM_G', 'VALUE_G')]
    strats = [(n, S[n]) for n in names] + [('VALUE_GM25', value_gm25), ('WAIT_G', wait_g), ('NORM_G', norm_g)]
    SLOTS = [int(x) for x in os.environ.get('BT_SLOTS', '4,0,9').split(',')]
    print('season', B.SEASON)
    for market in ('reputation', 'projection'):
        for slot in SLOTS:
            nd = NDR if slot == 4 else NDR // 2
            res = run(strats, market, nd, slot)
            print(f"\n== market={market}, pick {slot + 1}, {nd} drafts: weekly win (mean over weeks) ==")
            print('   ' + '  '.join(f"{n} {sum(v) / len(v):.1%}" for n, v in res.items()))
            for a, b in pairs:
                m, lo, hi = compare(res, a, b)
                flag = '' if lo < 0 < hi else '  <- clear'
                print(f"   {a:10s} - {b:9s}: {m:+.1%}  (95% week-bootstrap {lo:+.1%} to {hi:+.1%}){flag}")
