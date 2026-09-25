"""Daily team checkup for GUGUGUZZLERS V2 (ESPN, H2H most categories). Sends one Discord/Telegram alert.

  python inseason/checkup.py --dry-run            print the alert instead of sending it
  python inseason/checkup.py --demo --dry-run     no league needed: practice-draft rosters, first week of the season
  python inseason/checkup.py                      real run (needs config.json + ESPN cookies)

Alerts: lineup swaps for today, IR moves, this week's category matchup, streaming pickups, waiver upgrades.
It only suggests; you make the moves in the ESPN app.

Real runs need:
  inseason/config.json         {"league_id": 123456, "team_id": 5}
  ESPN_S2 and ESPN_SWID        cookies, from environment variables (GitHub secrets) or inseason/secrets.local.json
"""
import csv, datetime, json, os, sys, urllib.request
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, os.path.join(ROOT, 'analysis'))
sys.path.insert(0, HERE)
from common import app_players, ZMap, key, CATS, ESPN_KEYS   # noqa: E402
import notify                                               # noqa: E402

SEASON = 2027
try:
    TZ = ZoneInfo('America/Toronto')
except Exception:          # Windows without the tzdata package: Eastern time, close enough for game days
    TZ = datetime.timezone(datetime.timedelta(hours=-5))
BASE = f'https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/{SEASON}'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36'
SLOT = {0: 'PG', 1: 'SG', 2: 'SF', 3: 'PF', 4: 'C', 5: 'G', 6: 'F', 11: 'UTIL', 12: 'BN', 13: 'IR'}
STARTING = {0, 1, 2, 3, 4, 5, 6, 11}
OUT = {'OUT', 'INJURY_RESERVE', 'SUSPENSION'}
IR_SLOTS = 3


# ---------------------------------------------------------------- fetching
def get(url, cookies=None, flt=None):
    h = {'User-Agent': UA}
    if cookies: h['Cookie'] = f"espn_s2={cookies[0]}; SWID={cookies[1]}"
    if flt: h['x-fantasy-filter'] = json.dumps(flt)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise PermissionError('ESPN login expired or missing')
        raise


def schedule():
    """{proTeamId: set of local dates with a game}"""
    d = get(f'{BASE}?view=proTeamSchedules_wl')
    out = {}
    for t in d['settings']['proTeams']:
        for games in t.get('proGamesByScoringPeriod', {}).values():
            for g in games:
                day = datetime.datetime.fromtimestamp(g['date'] / 1000, TZ).date()
                out.setdefault(t['id'], set()).add(day)
    return out


def projection(pl):
    """per-game projection [PTS..TO line], games, from ESPN (season projection)"""
    for s in pl.get('stats', []):
        if s.get('seasonId') == SEASON and s.get('statSourceId') == 1 and s.get('statSplitTypeId') == 0 and s.get('averageStats'):
            a = s['averageStats']
            return [float(a.get(k, 0) or 0) for k in ESPN_KEYS], float(a.get('42', 0) or 0)
    return None, 0


def player(pl, slot=None):
    line, g = projection(pl)
    return dict(name=pl['fullName'], pro=pl.get('proTeamId'), inj=pl.get('injuryStatus') or 'ACTIVE',
                elig=set(pl.get('eligibleSlots', [])), slot=slot, line=line, G=g)


def load_league(cfg, cookies):
    lid, tid = cfg['league_id'], cfg['team_id']
    d = get(f'{BASE}/segments/0/leagues/{lid}?view=mRoster&view=mTeam&view=mMatchupScore&view=mSettings', cookies)
    teams = {t['id']: t for t in d['teams']}
    roster = lambda t: [player(e['playerPoolEntry']['player'], e['lineupSlotId']) for e in t.get('roster', {}).get('entries', [])]
    period = d['status']['currentMatchupPeriod']
    opp_id = None; mine_score = opp_score = None
    for m in d.get('schedule', []):
        if m.get('matchupPeriodId') != period: continue
        h, a = m.get('home', {}), m.get('away', {})
        if h.get('teamId') == tid or a.get('teamId') == tid:
            me_, op = (h, a) if h.get('teamId') == tid else (a, h)
            opp_id = op.get('teamId')
            mine_score = (me_.get('cumulativeScore') or {}).get('scoreByStat')
            opp_score = (op.get('cumulativeScore') or {}).get('scoreByStat')
    fa = get(f'{BASE}/segments/0/leagues/{lid}?view=kona_player_info', cookies,
             {"players": {"filterStatus": {"value": ["FREEAGENT", "WAIVERS"]}, "limit": 120,
                          "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}})
    return dict(mine=roster(teams[tid]), opp=roster(teams[opp_id]) if opp_id else [],
                fa=[player(x['player']) for x in fa.get('players', [])],
                opp_name=(teams[opp_id].get('name') or teams[opp_id].get('abbrev')) if opp_id else '?',
                score=(mine_score, opp_score))


def load_demo():
    """practice-draft league from analysis/data/practice, players from ESPN's public feed"""
    feed = get(f'{BASE}/segments/0/leaguedefaults/1?view=kona_player_info', None,
               {"players": {"limit": 500, "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}})
    by = {key(x['player']['fullName']): x['player'] for x in feed['players']}
    rows = list(csv.DictReader(open(os.path.join(ROOT, 'analysis', 'data', 'practice', 'draft-log-practice-2026-09-25.csv'), encoding='utf-8')))
    def team(mgr):
        out = []
        for i, r in enumerate([r for r in rows if r['manager'] == mgr]):
            pl = by.get(key(r['player']))
            if pl: out.append(player(pl, [0, 1, 2, 3, 4, 5, 6, 11, 11, 11, 12, 12, 12, 12, 12][min(i, 14)]))
        return out
    drafted = {key(r['player']) for r in rows}
    fa = [player(p) for k, p in by.items() if k not in drafted][:120]
    return dict(mine=team('Tyler'), opp=team('Saksham'), fa=fa, opp_name='Saksham (practice)', score=(None, None))


# ---------------------------------------------------------------- valuing
Z = ZMap(app_players())
def z_of(p): return Z.z(p['line']) if p['line'] else [-1.0] * 9
def per_game_value(p): return sum(z_of(p))
def season_value(p): return per_game_value(p) * min(1.0, p['G'] / 72) if p['line'] else -9


def games_between(p, sched, start, end):
    return sum(1 for d in sched.get(p['pro'], ()) if start <= d <= end)


def plays(p, sched, day): return day in sched.get(p['pro'], ())


# ---------------------------------------------------------------- alerts
def lineup_alerts(mine, sched, today):
    out = []
    healthy = lambda p: p['inj'] not in OUT
    starters = [p for p in mine if p['slot'] in STARTING]
    bench = [p for p in mine if p['slot'] == 12 and healthy(p) and plays(p, sched, today)]
    for s in sorted(starters, key=season_value):
        if plays(s, sched, today) and healthy(s): continue
        swap = [b for b in bench if s['slot'] in b['elig']]
        if swap:
            b = max(swap, key=per_game_value); bench.remove(b)
            why = 'is OUT' if not healthy(s) else 'has no game today'
            out.append(f"Start **{b['name']}** over {s['name']} ({SLOT[s['slot']]}) - {s['name']} {why}.")
    return out


def ir_alerts(mine, fa, sched, week):
    out = []
    in_ir = sum(1 for p in mine if p['slot'] == 13)
    for p in mine:
        if p['inj'] in OUT and p['slot'] != 13:
            if in_ir < IR_SLOTS:
                in_ir += 1
                best = max(fa, key=lambda f: per_game_value(f) * games_between(f, sched, *week), default=None)
                add = f" Then pick up **{best['name']}** ({games_between(best, sched, *week)} games this week)." if best else ''
                out.append(f"**{p['name']}** is {p['inj'].replace('_', ' ').lower()}: move him to IR.{add}")
            else:
                out.append(f"**{p['name']}** is {p['inj'].replace('_', ' ').lower()} but your 3 IR spots are full.")
    return out


def week_totals(team, sched, start, end):
    t = [0.0] * 11
    for p in team:
        if not p['line'] or p['inj'] in OUT or p['slot'] == 13: continue
        g = games_between(p, sched, start, end)
        for i in range(11): t[i] += p['line'][i] * g
    return t


def cats(t):
    return [t[0], t[1], t[2], t[3], t[4], t[5], t[6] / t[7] if t[7] else 0, t[8] / t[9] if t[9] else 0, t[10]]


NAMES = ['PTS', 'REB', 'AST', 'STL', 'BLK', '3PM', 'FG%', 'FT%', 'TO']


def matchup_alert(L, sched, today, week):
    rest = (today, week[1])
    m, o = cats(week_totals(L['mine'], sched, *rest)), cats(week_totals(L['opp'], sched, *rest))
    sm, so = L['score']
    if sm and so:   # add what's already happened this week (ESPN stat ids)
        ids = ['0', '6', '3', '2', '1', '17', '19', '20', '11']
        for q, sid in enumerate(ids):
            a, b = (sm.get(sid) or {}).get('score'), (so.get(sid) or {}).get('score')
            if a is None or b is None: continue
            if q in (6, 7): m[q], o[q] = a, b          # percentages so far (good enough mid-week)
            else: m[q] += a; o[q] += b
    win = lose = 0; close = []
    for q, n in enumerate(NAMES):
        a, b = m[q], o[q]
        better = a < b if n == 'TO' else a > b
        margin = abs(a - b) / max(1e-9, max(abs(a), abs(b)))
        if margin < (0.012 if q in (6, 7) else 0.06): close.append(n)
        elif better: win += 1
        else: lose += 1
    games_me, games_opp = sum(games_between(p, sched, *rest) for p in L['mine'] if p['inj'] not in OUT), \
        sum(games_between(p, sched, *rest) for p in L['opp'] if p['inj'] not in OUT)
    line = f"vs {L['opp_name']}: projected {win}-{lose}" + (f", close in {', '.join(close)}" if close else '')
    line += f". Games left: you {games_me}, them {games_opp}."
    return line, close, games_me - games_opp


def stream_alert(L, sched, week, today, close, keep=()):
    rest = (today, week[1])
    keepers = sorted(L['mine'], key=season_value, reverse=True)[:6]
    drop = min([p for p in L['mine'] if p not in keepers and p['slot'] != 13 and p['name'] not in keep], key=season_value, default=None)
    idx = {n: q for q, n in enumerate(NAMES)}
    def score(f):
        z = z_of(f); g = games_between(f, sched, *rest)
        boost = sum(max(0, z[idx[c]]) for c in close)   # help the close categories
        return (sum(z) + 1.5 * boost) * g
    top = sorted((f for f in L['fa'] if f['line'] and f['inj'] not in OUT), key=score, reverse=True)[:3]
    if not top or not drop: return None
    tops = ', '.join(f"{f['name']} ({games_between(f, sched, *rest)} g)" for f in top)
    return f"Stream: best pickups this week are {tops}. Drop candidate: {drop['name'].rstrip('.')}."


def waiver_alert(L):
    worst = min((p for p in L['mine'] if p['slot'] != 13), key=season_value, default=None)
    best = max((f for f in L['fa'] if f['inj'] not in OUT), key=season_value, default=None)
    if worst and best and season_value(best) - season_value(worst) >= 1.0:
        return f"Upgrade: **{best['name']}** (value {season_value(best):+.1f}) is better than {worst['name']} ({season_value(worst):+.1f})."
    return None


# ---------------------------------------------------------------- main
def load_secrets():
    s = {}
    p = os.path.join(HERE, 'secrets.local.json')
    if os.path.exists(p): s = json.load(open(p, encoding='utf-8'))
    for k in ('ESPN_S2', 'ESPN_SWID'):
        if os.environ.get(k): s[k] = os.environ[k]
    return s


def main():
    dry, demo = '--dry-run' in sys.argv, '--demo' in sys.argv
    try:
        sched = schedule()
        if demo:
            L = load_demo()
            first = min(min(v) for v in sched.values())
            today = first
        else:
            cfgp = os.path.join(HERE, 'config.json'); sec = load_secrets()
            if not os.path.exists(cfgp) or not sec.get('ESPN_S2') or not sec.get('ESPN_SWID'):
                print('Not set up yet (needs inseason/config.json and ESPN cookies): skipping.'); return
            cfg = json.load(open(cfgp, encoding='utf-8'))
            L = load_league(cfg, (sec['ESPN_S2'], sec['ESPN_SWID']))
            today = datetime.datetime.now(TZ).date()
        week = (today - datetime.timedelta(days=today.weekday()), today + datetime.timedelta(days=6 - today.weekday()))
        parts = []
        la = lineup_alerts(L['mine'], sched, today); parts += la
        starting = {p['name'] for p in L['mine'] if any(f"**{p['name']}**" in a for a in la)}
        parts += ir_alerts(L['mine'], L['fa'], sched, (today, week[1]))
        mline, close, gap = matchup_alert(L, sched, today, week)
        parts.append(mline)
        if today.weekday() <= 2 or gap <= -3:
            s = stream_alert(L, sched, week, today, close, starting)
            if s: parts.append(s)
        if today.weekday() == 0:
            w = waiver_alert(L)
            if w: parts.append(w)
        msg = f"**Hoops checkup, {today:%a %b %d}**\n" + '\n'.join('- ' + p for p in parts)
    except PermissionError:
        msg = ("ESPN login expired. Update the ESPN_S2 and ESPN_SWID secrets (Chrome: F12 > Application > "
               "Cookies > espn.com) and re-run the checkup.")
    except Exception as e:   # tell Tyler rather than fail silently
        msg = f"Hoops checkup failed: {type(e).__name__}: {e}"
        if dry: raise
    if dry: print(msg)
    else: print('sent' if notify.send(msg) else 'failed to send')


if __name__ == '__main__':
    main()
