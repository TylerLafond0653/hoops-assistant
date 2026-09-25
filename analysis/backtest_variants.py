"""Tests for the proposed calibration changes, before they go into the app (3 seasons, pick 5, week bootstrap).

  games rule:   G72  = min(1, G/72)            (current app)
                G82c = 0.85*G/82                (calibrated: projections run ~15% high; share of an 82-game season)
                G72c = min(1, 0.85*G/72)
  market table: per-game (current: per-game value at the player's ADP vs his per-game value)
                season   (season value at his ADP vs his season value: ADP already prices in missed games)
  age:          -0.4 value for players 31+ this season (fit on the other seasons' misses)

Run: BT_SEASON=2025 python analysis/backtest_variants.py [drafts=150]
"""
import sys, os, statistics as st
import backtest_2025 as B
from backtest_robustness import run, compare

ND = int(sys.argv[1]) if len(sys.argv) > 1 else 150
R = B.R
ages = {B.key(k): v for k, v in B.A['AGE'].items()}   # 2026-27 ages; shift back by season for the backtest year
AGE_SHIFT = 2027 - B.SEASON
def age_of(p):
    a = ages.get(B.key(p['name']))
    if a is not None: return a - AGE_SHIFT
    last = p.get('last'); return (last['age'] + 1) if last and last.get('age') else None

def prepare(games_rule, table, age_adj):
    """recompute every player's season vector under the chosen rules (market shift at 0.5)"""
    for p in B.pool:
        g = p['gp']
        sh = min(1, g / 72) if games_rule == 'G72' else 0.85 * g / 82 if games_rule == 'G82c' else min(1, 0.85 * g / 72)
        p['sh2'] = sh
        base = [p['zp'][q] * sh + R[q] * (1 - sh) for q in range(9)]
        a = age_of(p)
        if age_adj and a is not None and a >= 31: base = [x - 0.4 / 9 for x in base]
        p['base2'] = base; p['vs2'] = sum(base)
    VTs = sorted((p['vs2'] for p in B.pool), reverse=True)
    VTp = sorted((p['vpg'] for p in B.pool), reverse=True)
    at = lambda T, a: T[max(0, min(len(T) - 1, round(a) - 1))]
    for p in B.pool:
        if table == 'season':
            shift = 0.5 * (at(VTs, p['mrank']) - p['vs2']) / 9
            p['v2'] = sum(x + shift for x in p['base2'])
        else:   # the app today: shift on the per-game scale, then games weighting
            shift = 0.5 * (at(VTp, p['mrank']) - p['vpg']) / 9
            p['v2'] = sum((p['zp'][q] + shift) * p['sh2'] + R[q] * (1 - p['sh2']) for q in range(9))
            a = age_of(p)
            if age_adj and a is not None and a >= 31: p['v2'] -= 0.4

def strat(games_rule, table, age_adj=False):
    key = (games_rule, table, age_adj)
    def pick(av, mine, rosters, k):
        if strat.cur != key: prepare(*key); strat.cur = key
        return max(av, key=lambda i: B.pool[i]['v2'])
    return pick
strat.cur = None

variants = [('now: G72 + per-game table', strat('G72', 'pergame')),
            ('G82c + per-game table', strat('G82c', 'pergame')),
            ('G72c + per-game table', strat('G72c', 'pergame')),
            ('G72 + season table', strat('G72', 'season')),
            ('G82c + season table', strat('G82c', 'season')),
            ('G82c + season table + age', strat('G82c', 'season', True)),
            ('G72 + season table + age', strat('G72', 'season', True))]
if __name__ == '__main__':
    print('season', B.SEASON)
    for market in ('reputation', 'projection'):
        # strategies are run one at a time, so prepare() is re-run when the variant changes
        res = {}
        for name, fn in variants:
            strat.cur = None
            res.update(run([(name, fn)], market, ND, 4))
        print(f"\n== market={market}, pick 5, {ND} drafts ==")
        base = variants[0][0]
        for name, _ in variants:
            m, lo, hi = compare(res, name, base) if name != base else (0, 0, 0)
            print(f"   {name:28s} weekly win {sum(res[name]) / len(res[name]):.1%}   vs now {m:+.1%} ({lo:+.1%} to {hi:+.1%})")
