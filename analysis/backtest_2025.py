"""Backtest the app's decision rules on the 2025-26 season.

The draft is replayed as it would have looked in October 2025: every strategy only sees ESPN's 2025-26
preseason projections (converted to the app's z scale). Opponents draft off a "market" ranking with the
app's ADP scatter. Each finished league is then scored on what really happened: week-by-week head-to-head
category matchups built from 24,884 real box scores.

Because 2025 ADP isn't available, the market is a proxy: half projection, half last season's value
(reputation), which is roughly how ADP forms. A second run uses a pure-projection market.

Strategies (your pick at 5th, 10 teams, 15 rounds, 3rd-round reversal):
  ADP        take the best market rank left (what a casual manager does)
  VALUE      projected per-game 9-cat value (the board's Value column)
  VALUE_G    + games-weighted, missed games filled by a waiver player (the simulator's player value)
  VALUE_GM   + meet the market halfway (TUNE.market = 0.5): the simulator's effZ
  WAIT       VALUE_GM + the expected-loss rule (don't take a player who will likely be there next turn)
  POS        VALUE_GM + the simulator's position bonus
  TEAM_5     greedy roster fit: the player who most raises your weekly win chance against the other nine
             rosters, with the app's matchup model (one weekly sd of 5 for every category)
  TEAM_G     the same with weekly sd measured per category (fitted on odd weeks only)
  GSCORE     VALUE_GM with each category divided by its measured weekly sd (additive, no roster fit)
  PUNT_FT, PUNT_TO   the app's build weights for those plans

Scoring uses even weeks when strategies use the measured sd (so the sd isn't tested on the weeks it was
fitted on); every strategy is reported on even weeks and on all weeks.

Run: python analysis/backtest_2025.py [drafts=200]
"""
import sys, random, math, time, statistics as st, bisect
from common import *

NDRAFT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 200
SEASON = int(os.environ.get('BT_SEASON', '2026'))         # ESPN season id: 2026 = 2025-26, 2025 = 2024-25, 2024 = 2023-24
MY = 4                                                    # 5th pick
A = load_app(); P = app_players(A); Z = ZMap(P); E = load_espn(season=SEASON)
B24 = load_bbref(os.path.join(DATA, PRIOR_BBREF[SEASON]))   # the season before: the market proxy's "reputation"
INV_TEAM = {v: k for k, v in ESPN_TEAM.items()}

# ---------- the 2025 player pool, as seen before the season ----------
pool = []
for e in E.values():
    pj = e.get('proj')
    if not pj or pj['G'] <= 0 or pj['MIN'] < 12 or not e['pos']: continue
    pool.append(dict(name=e['name'], pos=e['pos'], zp=Z.z(pj['line']), gp=pj['G'], e=e,
                     last=B24.get(key(e['name']))))
share = lambda g: min(1.0, g / 72.0)
for p in pool: p['vpg'] = sum(p['zp'])
pool.sort(key=lambda p: -(p['vpg'] * share(p['gp'])))
R = [st.mean(p['zp'][q] for p in pool[120:150]) for q in range(9)]           # replacement profile, as the app does
for p in pool:
    sh = share(p['gp']); p['sh'] = sh
    p['eff'] = [p['zp'][q] * sh + R[q] * (1 - sh) for q in range(9)]
    p['vs'] = sum(p['eff'])
    if p['last'] and p['last']['G'] > 0:
        zl = Z.z(p['last']['line']); shl = share(p['last']['G'])
        p['vlast'] = sum(zl) * shl + sum(R) * (1 - shl)
    else: p['vlast'] = None
pool.sort(key=lambda p: -p['vs'])
pool = pool[:240]
NP = len(pool)
VT = sorted((p['vpg'] for p in pool), reverse=True)            # the app's valueAtPick table
value_at = lambda a: VT[max(0, min(len(VT) - 1, round(a) - 1))]
POSBIT = {'PG': 1, 'SG': 2, 'SF': 4, 'PF': 8, 'C': 16}
for p in pool: p['mask'] = sum(POSBIT[x] for x in set(p['pos']))

ECR = None   # the real preseason expert consensus (2025-26 only), loaded on first use


def load_experts():
    """FantasyPros roto/category expert consensus archived Oct 19, 2025: {key: rank}"""
    s = open(os.path.join(DATA, 'fp_ecr_2025-10-19.html'), encoding='utf-8', errors='replace').read()
    i = s.index('ecrData =') + len('ecrData ='); j = s.index('};', i) + 1
    return {key(p['player_name']): float(p['rank_ecr']) for p in json.loads(s[i:j].strip())['players']}


def set_market(kind):
    """kind: 'reputation' (half projection, half last season), 'projection', or 'experts' (the real
    preseason expert consensus; 2025-26 only)"""
    global ECR
    if kind == 'experts':
        assert SEASON == 2026, 'the archived expert consensus is for 2025-26'
        ECR = ECR or load_experts()
        for i, p in enumerate(sorted(pool, key=lambda p: -p['vs'])):
            p['m'] = -ECR.get(key(p['name']), 400 + i)     # players the experts didn't rank go after those they did
    else:
        for p in pool:
            p['m'] = p['vs'] if kind == 'projection' or p['vlast'] is None else 0.5 * p['vs'] + 0.5 * p['vlast']
    order = sorted(range(NP), key=lambda i: -pool[i]['m'])
    for r, i in enumerate(order): pool[i]['mrank'] = r + 1
    for p in pool:   # the simulator's effZ: meet the market halfway on total value
        shift = 0.5 * (value_at(p['mrank']) - p['vpg']) / 9
        p['effm'] = [(p['zp'][q] + shift) * p['sh'] + R[q] * (1 - p['sh']) for q in range(9)]
        p['vsm'] = sum(p['effm'])

# ---------- what actually happened, week by week ----------
all_days = sorted({d for e in E.values() for d in e['games']})
d0 = all_days[0]; wk = lambda d: (d - d0) // 7; NW = wk(all_days[-1]) + 1
team_days = {}
for e in E.values():
    for d, t in e.get('game_team', {}).items(): team_days.setdefault(t, set()).add(d)
games_in_week = [0] * NW
for e in E.values():
    for d in e['games']: games_in_week[wk(d)] += 1
WEEKS = [w for w in range(NW) if games_in_week[w] > 0.6 * max(games_in_week)]
# a waiver player's per-game line: the actual 121st-150th best by season value
act = [e for e in E.values() if 'act' in e and e['act']['G'] >= 20]
act.sort(key=lambda e: -(sum(Z.z(e['act']['line'])) * share(e['act']['G'])))
REPL = [st.mean(e['act']['line'][i] for e in act[120:150]) for i in range(11)]

def weekly_lines(p, fill):
    e = p['e']; out = [[0.0] * 11 for _ in range(NW)]
    for d, line in e['games'].items():
        w = out[wk(d)]
        for i in range(11): w[i] += line[i]
    if fill:
        gd = sorted(e['games']); gt = e.get('game_team', {})
        def team_on(d):
            if not gd: return INV_TEAM.get(e['team'])
            j = bisect.bisect_left(gd, d); j = min(j, len(gd) - 1)
            if j > 0 and abs(gd[j - 1] - d) < abs(gd[j] - d): j -= 1
            return gt.get(gd[j])
        for t in {team_on(d) for d in all_days}:
            pass
        for d in all_days:
            if d in e['games']: continue
            t = team_on(d)
            if t is not None and d in team_days.get(t, ()):
                w = out[wk(d)]
                for i in range(11): w[i] += REPL[i]
    return out
for p in pool:
    p['wk_raw'] = weekly_lines(p, False); p['wk_fill'] = weekly_lines(p, True)
    ac = p['e'].get('act'); p['ga'] = ac['G'] if ac else 0

def team_week_cats(roster, w, fill):
    t = [0.0] * 11
    key_ = 'wk_fill' if fill else 'wk_raw'
    for i in roster:
        x = pool[i][key_][w]
        for k in range(11): t[k] += x[k]
    return [t[0], t[1], t[2], t[3], t[4], t[5], t[6] / t[7] if t[7] else 0.0, t[8] / t[9] if t[9] else 0.0, -t[10]]

def score_league(rosters, weeks, fill=True):
    """weekly H2H: each team vs every other team every week. Returns per team (win rate, cats per week)."""
    C = [[team_week_cats(r, w, fill) for w in weeks] for r in rosters]
    n = len(rosters); win = [0.0] * n; cats = [0.0] * n; cw = [[0.0] * 9 for _ in range(n)]
    for a in range(n):
        for b in range(a + 1, n):
            for wi in range(len(weeks)):
                x, y = C[a][wi], C[b][wi]; ca = 0.0
                for q in range(9):
                    s = 1.0 if x[q] > y[q] else 0.5 if x[q] == y[q] else 0.0
                    ca += s; cw[a][q] += s; cw[b][q] += 1 - s
                cats[a] += ca; cats[b] += 9 - ca
                r_ = 1.0 if ca > 4.5 else 0.5 if ca == 4.5 else 0.0
                win[a] += r_; win[b] += 1 - r_
    den = (n - 1) * len(weeks)
    return [w / den for w in win], [c / den for c in cats], [[v / den for v in row] for row in cw]

# ---------- measured weekly sd per category (odd weeks only) ----------
def fit_sigma(weeks):
    rng = random.Random(11); teams = []
    for s in range(30):
        order = sorted(range(NP), key=lambda i: pool[i]['mrank'] + rng.gauss(0, 1.5 + 0.12 * pool[i]['mrank']))
        for t in range(10): teams.append([order[r * 10 + (t if r % 2 == 0 else 9 - t)] for r in range(13)])
    def strength(tm):   # actual per-game z x actual games share (waiver fill for missed games), app units
        out = [0.0] * 9
        for i in tm:
            p = pool[i]; ac = p['e'].get('act')
            za = Z.z(ac['line']) if ac else [0] * 9; sh = share(p['ga'])
            for q in range(9): out[q] += za[q] * sh + R[q] * (1 - sh)
        return out
    S_ = [strength(tm) for tm in teams]
    W_ = [[team_week_cats(tm, w, True) for w in weeks] for tm in teams]
    pairs = [(a, b) for a, b in ((rng.randrange(len(teams)), rng.randrange(len(teams))) for _ in range(2500)) if a != b]
    sig = []
    for q in range(9):
        obs = []
        for a, b in pairs:
            dS = S_[a][q] - S_[b][q]
            for wi in range(len(weeks)):
                x, y = W_[a][wi][q], W_[b][wi][q]
                obs.append((dS, 1.0 if x > y else 0.5 if x == y else 0.0))
        def nll(s_):
            t = 0.0
            for dS, y in obs:
                p = min(1 - 1e-9, max(1e-9, ncdf(dS / s_))); t -= y * math.log(p) + (1 - y) * math.log(1 - p)
            return t
        lo, hi = 1.0, 40.0                                   # golden-section search
        g = (math.sqrt(5) - 1) / 2
        c, d = hi - g * (hi - lo), lo + g * (hi - lo); fc, fd = nll(c), nll(d)
        for _ in range(30):
            if fc < fd: hi, d, fd = d, c, fc; c = hi - g * (hi - lo); fc = nll(c)
            else: lo, c, fc = c, d, fd; d = lo + g * (hi - lo); fd = nll(d)
        sig.append((lo + hi) / 2)
    return sig

# ---------- the draft ----------
def reversed_round(r): return r == 1 or (r >= 2 and r % 2 == 0)
ORDER = [(r * 10 + i, (9 - i) if reversed_round(r) else i) for r in range(15) for i in range(10)]
MY_PICKS = [k for k, t in ORDER if t == MY]
def chance(i, m):
    if m <= 0: return 1
    s = max(1.3, m * 0.2); return 1 / (1 + math.exp((m - i - 0.5) / s))

def team_total(idx_list, key_='effm'):
    items = sorted((pool[i][key_] for i in idx_list), key=lambda e: -sum(e))
    while len(items) < 15: items.append(R)
    items.sort(key=lambda e: -sum(e))
    return [sum(SLOT_W[k] * items[k][q] for k in range(len(items))) for q in range(9)]

def make_strategy(name, sig=None):
    wG = [5.0 / s for s in sig] if sig else None
    FT_W = [0.884, 1.193, 0.884, 0.884, 1.193, 0.884, 1.193, 0.0, 0.884]      # app BUILDS 'ft' (Sept 25)
    TO_W = [1.193, 0.884, 1.193, 0.884, 0.884, 1.193, 0.884, 0.884, 0.0]      # app BUILDS 'to'
    def pick(av, mine, rosters, k):
        if name == 'ADP': return min(av, key=lambda i: pool[i]['mrank'])
        if name == 'VALUE': return max(av, key=lambda i: pool[i]['vpg'])
        if name == 'VALUE_G': return max(av, key=lambda i: pool[i]['vs'])
        if name == 'VALUE_GM': return max(av, key=lambda i: pool[i]['vsm'])
        if name == 'GSCORE': return max(av, key=lambda i: sum(pool[i]['effm'][q] * wG[q] for q in range(9)))
        if name == 'PUNT_FT': return max(av, key=lambda i: sum(pool[i]['effm'][q] * FT_W[q] for q in range(9)))
        if name == 'PUNT_TO': return max(av, key=lambda i: sum(pool[i]['effm'][q] * TO_W[q] for q in range(9)))
        if name == 'POS':
            have = 0
            for i in mine:
                free = pool[i]['mask'] & ~have
                if free: have |= free & -free
            left = len(MY_PICKS) - len(mine); open_ = 5 - bin(have).count('1')
            pb = 0.5 + 1.5 * min(1, open_ / max(1, left))
            return max(av, key=lambda i: pool[i]['vsm'] + (pb if pool[i]['mask'] & ~have else 0))
        if name == 'WAIT':
            j = MY_PICKS.index(k); g = (MY_PICKS[j + 1] - k - 1) if j + 1 < len(MY_PICKS) else 0
            if g <= 0: return max(av, key=lambda i: pool[i]['vsm'])
            by_adp = sorted(av, key=lambda i: pool[i]['mrank'])
            q = {i: chance(n, g) for n, i in enumerate(by_adp)}
            vals = sorted((pool[i]['vsm'] for i in av), reverse=True); X = vals[min(g, len(vals) - 1)]
            return max(av, key=lambda i: (1 - q[i]) * (pool[i]['vsm'] - X))
        if name in ('TEAM_5', 'TEAM_G'):
            sd = 5.0 if name == 'TEAM_5' else sig
            opp = [team_total(r) for t, r in enumerate(rosters) if t != MY]
            cands = sorted(av, key=lambda i: -pool[i]['vsm'])[:25]
            def ev(i):
                me_ = team_total(mine + [i])
                return sum(matchup(me_, o, sd)[0] for o in opp)
            return max(cands, key=ev)
        raise ValueError(name)
    return pick

def run_draft(strategy, seed, noise_mult=1.0):
    rng = random.Random(seed)
    order = sorted(range(NP), key=lambda i: pool[i]['mrank'] + noise_mult * rng.gauss(0, 1.5 + 0.12 * pool[i]['mrank']))
    taken = [False] * NP; rosters = [[] for _ in range(10)]; ptr = 0
    for k, t in ORDER:
        if t == MY:
            av = [i for i in range(NP) if not taken[i]]
            i = strategy(av, rosters[MY], rosters, k)
        else:
            while taken[order[ptr]]: ptr += 1
            i = order[ptr]
        taken[i] = True; rosters[t].append(i)
    return rosters

def evaluate(strats, market, noise_mult=1.0, ndraft=NDRAFT):
    set_market(market)
    print(f"\n==== market = {market}, opponent scatter x{noise_mult}, {ndraft} drafts, you pick 5th ====")
    even = [w for i, w in enumerate(WEEKS) if i % 2 == 1]
    res = {}
    for name, fn in strats:
        t0 = time.time(); wr_e, wr_a, fin, cats, cw = [], [], [], [], [[] for _ in range(9)]
        for s in range(ndraft):
            ros = run_draft(fn, 1000 + s, noise_mult)
            w_all, c_all, cwin = score_league(ros, WEEKS)
            w_even, _, _ = score_league(ros, even)
            wr_a.append(w_all[MY]); wr_e.append(w_even[MY]); cats.append(c_all[MY])
            fin.append(1 + sum(1 for t in range(10) if w_all[t] > w_all[MY]))
            for q in range(9): cw[q].append(cwin[MY][q])
        res[name] = dict(e=wr_e, a=wr_a, fin=fin, cats=cats, cw=[st.mean(x) for x in cw])
        print(f"  {name:9s} weekly win {st.mean(wr_a):.1%} (even weeks {st.mean(wr_e):.1%}) | cats/week {st.mean(cats):.2f} | "
              f"avg finish {st.mean(fin):.1f} | top-3 {sum(f <= 3 for f in fin) / len(fin):.0%}   [{time.time() - t0:.0f}s]")
    base = res.get('VALUE_G')
    if base:
        print('  paired difference in weekly win rate vs VALUE_G (all weeks; even weeks), with standard error:')
        for name in res:
            if name == 'VALUE_G': continue
            for lab, k_ in (('all', 'a'), ('even', 'e')):
                d = [x - y for x, y in zip(res[name][k_], base[k_])]
                print(f"    {name:9s} {lab:4s}: {st.mean(d):+.1%} ± {st.pstdev(d) / math.sqrt(len(d)):.1%}", end='')
            print()
    return res

if __name__ == '__main__':
    t0 = time.time()
    set_market('reputation')
    odd = [w for i, w in enumerate(WEEKS) if i % 2 == 0]
    SIG = fit_sigma(odd)
    print('pool', NP, '| weeks', len(WEEKS), '| measured weekly sd (odd weeks):', dict(zip(CATS, [round(s, 1) for s in SIG])), f'[{time.time() - t0:.0f}s]')
    names = ['ADP', 'VALUE', 'VALUE_G', 'VALUE_GM', 'WAIT', 'POS', 'GSCORE', 'PUNT_FT', 'PUNT_TO', 'TEAM_5', 'TEAM_G']
    strats = [(n, make_strategy(n, SIG)) for n in names]
    r1 = evaluate(strats, 'reputation')
    r2 = evaluate([(n, f) for n, f in strats if n in ('ADP', 'VALUE', 'VALUE_G', 'VALUE_GM', 'WAIT', 'GSCORE', 'TEAM_5', 'TEAM_G')], 'projection', ndraft=max(60, NDRAFT // 2))
    r3 = evaluate([(n, f) for n, f in strats if n in ('VALUE_G', 'VALUE_GM', 'WAIT')], 'reputation', noise_mult=2.5, ndraft=max(60, NDRAFT // 2))
    print('\ncategory win rates, reputation market (VALUE_G / GSCORE / TEAM_5 / TEAM_G):')
    for q, c in enumerate(CATS):
        print(f"  {c:4s} " + ' / '.join(f"{r1[n]['cw'][q]:.0%}" for n in ('VALUE_G', 'GSCORE', 'TEAM_5', 'TEAM_G')))
    print(f'total {time.time() - t0:.0f}s')
