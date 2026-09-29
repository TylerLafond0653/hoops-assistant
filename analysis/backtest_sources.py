"""Which preseason ranking source best predicted the 2025-26 season?

Sources, as they stood before the 2025-26 season (it started Oct 21, 2025):
  experts      FantasyPros expert consensus for roto/category leagues: 8 experts, updated Oct 18, 2025
               (archived by the Internet Archive on Oct 19, 2025) -> data/fp_ecr_2025-10-19.html
  espn_proj    ESPN's 2025-26 preseason projection, turned into 9-cat season value with the app's formula
  last_season  each player's actual 2024-25 value (what a "reputation" drafter goes by)
  blends of these.
ESPN's own 2025-26 category rank and ADP can't be tested: ESPN has since overwritten them (its "2025-26" rank
has Tatum 9th and Haliburton 18th, who both missed the season with injuries known before it started).

Target: each player's ACTUAL 2025-26 season value = per-game 9-cat z-scores on the app's scale x games played,
missed games filled by a waiver player (what he was really worth). Players who never played count as waiver.

Metrics over every player any source ranked in its top 150:
  rank correlation with actual value (Spearman, 95% bootstrap interval), the average actual value of each
  source's top 30 / 60 / 120, and paired differences against the experts.

Run: python analysis/backtest_sources.py
"""
import json, os, random, statistics as st
from common import DATA, key, load_app, app_players, ZMap, load_bbref

P = app_players(load_app()); Z = ZMap(P)
share = lambda g: min(1.0, g / 72.0)
R_TOT = -4.3                                       # the app's replacement (waiver) total
def season_value(line, g): return sum(Z.z(line)) * share(g) + R_TOT * (1 - share(g))


def load_ecr(path):
    s = open(path, encoding='utf-8', errors='replace').read()
    i = s.index('ecrData =') + len('ecrData ='); j = s.index('};', i) + 1
    d = json.loads(s[i:j].strip())
    return {key(p['player_name']): float(p['rank_ecr']) for p in d['players']}, d


def espn_2026(path):
    """ESPN 2025-26 preseason projection and actual line per player"""
    d = json.load(open(path, encoding='utf-8'))
    out = {}
    for x in d['players']:
        pl = x['player']; pj = ac = None
        for s in pl.get('stats', []):
            if s.get('seasonId') == 2026 and s.get('statSplitTypeId') == 0 and s.get('averageStats'):
                a = s['averageStats']
                line = [float(a.get(q, 0) or 0) for q in ['0', '6', '3', '2', '1', '17', '13', '14', '15', '16', '11']]
                if s.get('statSourceId') == 1: pj = (line, float(a.get('42', 0) or 0))
                if s.get('statSourceId') == 0: ac = (line, float(a.get('42', 0) or 0))
        out[key(pl['fullName'])] = dict(name=pl['fullName'], proj=pj, act=ac)
    return out


def ranks(values):
    """{key: value} (higher better) -> {key: rank}"""
    return {k: i + 1 for i, k in enumerate(sorted(values, key=lambda k: -values[k]))}


def spearman(a, b):
    def rk(v):
        o = sorted(range(len(v)), key=lambda i: v[i]); r = [0] * len(v)
        for j, i in enumerate(o): r[i] = j + 1
        return r
    return st.correlation(rk(a), rk(b))


def blend(sources, parts):
    keys = set().union(*(sources[s].keys() for s, _ in parts))
    out = {}
    for k in keys:
        v = [(w, sources[s][k]) for s, w in parts if k in sources[s]]
        if len(v) == len(parts): out[k] = sum(w * x for w, x in v) / sum(w for w, _ in v)
    return out


def main():
    ecr, meta = load_ecr(os.path.join(DATA, 'fp_ecr_2025-10-19.html'))
    print(f"experts: {len(ecr)} players, {meta.get('total_experts')} experts, updated {meta.get('last_updated')}/{meta.get('year')}")
    E = espn_2026(os.path.join(DATA, 'espn_feed_season2026.json'))
    B24 = load_bbref(os.path.join(DATA, 'bbref_2024-25_per_game.html'))
    act = {}
    for k, e in E.items():
        if e['act'] and e['act'][1] > 0: act[k] = season_value(*e['act'])
        elif e['proj'] or k in ecr: act[k] = R_TOT
    proj = {k: season_value(*e['proj']) for k, e in E.items() if e['proj'] and e['proj'][1] > 0}
    last = {k: season_value(b['line'], b['G']) for k, b in B24.items() if b['G'] and b['G'] > 0}
    sources = {'experts (Oct 2025)': ecr, 'ESPN projection': ranks(proj), 'last season (2024-25)': ranks(last)}
    sources['experts + ESPN projection'] = blend(sources, [('experts (Oct 2025)', 0.5), ('ESPN projection', 0.5)])
    sources['experts + last season'] = blend(sources, [('experts (Oct 2025)', 0.5), ('last season (2024-25)', 0.5)])
    sources['ESPN projection + last season'] = blend(sources, [('ESPN projection', 0.5), ('last season (2024-25)', 0.5)])

    evalset = set()
    for d in sources.values():
        evalset |= {k for k, _ in sorted(d.items(), key=lambda kv: kv[1])[:150]}
    evalset = [k for k in evalset if k in act]
    print(f"evaluation set: {len(evalset)} players ranked top-150 by at least one source\n")
    rng = random.Random(5)
    print(f"{'source':32s} {'n':>4s} {'rank corr (95% CI)':>22s}   avg actual value of its top 30 / 60 / 120")
    for s, d in sources.items():
        ks = [k for k in evalset if k in d]
        corr = spearman([-d[k] for k in ks], [act[k] for k in ks])
        order = sorted(ks, key=lambda k: d[k])
        tops = [st.mean(act[k] for k in order[:n]) for n in (30, 60, 120)]
        boots = sorted(spearman([-d[k] for k in smp], [act[k] for k in smp])
                       for smp in ([ks[rng.randrange(len(ks))] for _ in ks] for _ in range(800)))
        print(f"{s:32s} {len(ks):4d} {corr:8.3f} ({boots[20]:.2f}-{boots[779]:.2f})    {tops[0]:+6.2f} {tops[1]:+6.2f} {tops[2]:+6.2f}")
    print('\npaired difference in rank correlation vs the experts (same players; 95% bootstrap):')
    base = sources['experts (Oct 2025)']
    for s, d in sources.items():
        if s == 'experts (Oct 2025)': continue
        ks = [k for k in evalset if k in d and k in base]
        diffs = sorted(spearman([-d[k] for k in smp], [act[k] for k in smp]) - spearman([-base[k] for k in smp], [act[k] for k in smp])
                       for smp in ([ks[rng.randrange(len(ks))] for _ in ks] for _ in range(800)))
        m = st.mean(diffs)
        print(f"  {s:32s} {m:+.3f} ({diffs[20]:+.3f} to {diffs[779]:+.3f}){'  <- clear' if diffs[20] > 0 or diffs[779] < 0 else ''}")


if __name__ == '__main__':
    main()
