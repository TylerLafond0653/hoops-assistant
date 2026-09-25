"""Refresh everything the app takes from ESPN, then write it into draft-room.html.

  ESPN_MKT     {name: [ESPN live ADP, ESPN category-league rank]} for the app's players: where ESPN
               managers actually draft (the opponent model and the market view use these)
  ESPN_OTHERS  [[name, ESPN live ADP, category rank]] for players outside the app's list that ESPN managers
               still draft (they use up other teams' picks in the simulator)
  LAST         last season's actual per-game stats (the board's "2025-26 actual" view)

It also prints a report of team changes and ESPN injury statuses for players in the app, so NEWS can be
checked by hand (ESPN's preseason day-to-day tags are mostly stale, so they are not written automatically).

Run before the draft:   python pipeline/refresh_espn.py            (fetches a fresh feed)
                        python pipeline/refresh_espn.py --cached   (re-uses the newest cached feed)
"""
import datetime, glob, json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, os.path.join(ROOT, 'analysis'))
from common import key, ESPN_TEAM, load_bbref, ESPN_KEYS   # noqa: E402

APP = os.path.join(ROOT, 'draft-room.html')
DATA = os.path.join(ROOT, 'analysis', 'data')
URL = 'https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/2027/segments/0/leaguedefaults/1?view=kona_player_info'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36'
# ESPN's default leagues draft 10 teams x 13 rounds, so its ADP bunches up near 130-140 for anyone rarely
# drafted. Past this point only the category rank is used.
ADP_RELIABLE = 115


def fetch():
    today = datetime.date.today().isoformat()
    path = os.path.join(DATA, f'espn_feed_{today}.json')
    flt = json.dumps({"players": {"limit": 600, "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}})
    subprocess.run(['curl', '-sL', '-A', UA, '-H', f'x-fantasy-filter: {flt}', '-o', path, '--max-time', '120', URL], check=True)
    json.load(open(path, encoding='utf-8'))            # fail loudly if it isn't JSON
    return path


def newest_cached():
    files = sorted(glob.glob(os.path.join(DATA, 'espn_feed_20??-??-??.json')))
    return files[-1]


def replace_block(app, name, js):
    """swap `const NAME=...;` (one line) for the new value, or insert it before ESPN_INSERT_BEFORE"""
    pat = re.compile(r'^const %s=.*?;\n' % re.escape(name), re.M | re.S)
    line = f'const {name}={js};\n'
    if pat.search(app):
        return pat.sub(lambda m: line, app, count=1)
    anchor = app.index('// Injury and role news that matters on draft day')
    return app[:anchor] + line + app[anchor:]


def main():
    path = newest_cached() if '--cached' in sys.argv else fetch()
    asof = re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(path)).group(1)
    d = json.load(open(path, encoding='utf-8'))
    app = open(APP, encoding='utf-8').read()
    i0 = app.index('const DATA=['); i1 = app.index('\n];', i0)
    rows = [json.loads(l.strip().rstrip(',')) for l in app[i0:i1].split('\n') if l.strip().startswith('["')]
    names = {key(r[0]): r for r in rows}

    mkt, others, last, report = {}, [], {}, []
    for x in d['players']:
        pl = x['player']
        adp = (pl.get('ownership') or {}).get('averageDraftPosition')
        cat = ((pl.get('draftRanksByRankType') or {}).get('ROTO') or {}).get('rank')
        adp = round(adp, 1) if adp and adp < ADP_RELIABLE else None
        k = key(pl['fullName'])
        if k in names:
            r = names[k]
            mkt[r[0]] = [adp, cat]
            team = ESPN_TEAM.get(pl.get('proTeamId'))
            if team and team != r[1]: report.append(f"team: {r[0]} app {r[1]} -> ESPN {team}")
            if pl.get('injuryStatus') not in (None, 'ACTIVE'): report.append(f"injury: {r[0]} ESPN {pl['injuryStatus']}")
            act = [s for s in pl.get('stats', []) if s.get('seasonId') == 2026 and s.get('statSourceId') == 0
                   and s.get('statSplitTypeId') == 0 and s.get('averageStats')]
            if act:
                a = act[0]['averageStats']; g = lambda q: float(a.get(q, 0) or 0)
                if g('42') > 0:
                    last[r[0]] = [int(g('42')), round(g('40')), round(g('0'), 1), round(g('6'), 1), round(g('3'), 1), round(g('2'), 1),
                                  round(g('1'), 1), round(g('17'), 1), round(g('13') / g('14'), 3) if g('14') else None,
                                  round(g('15') / g('16'), 3) if g('16') else None, round(g('11'), 1)]
        else:
            anchor = (adp + cat) / 2 if adp and cat else adp or cat
            if anchor and anchor <= 170: others.append([pl['fullName'], adp, cat])
    # players ESPN doesn't list keep last season's Basketball Reference line, if any
    bb = load_bbref(os.path.join(DATA, 'bbref_2025-26_per_game.html'))
    for r in rows:
        if r[0] in last: continue
        b = bb.get(key(r[0]))
        if b and b['G']:
            L = b['line']; f = lambda m, a: round(m / a, 3) if a else None
            last[r[0]] = [int(b['G']), round(b['MP']), L[0], L[1], L[2], L[3], L[4], L[5], f(L[6], L[7]), f(L[8], L[9]), L[10]]

    dt = datetime.date.fromisoformat(asof)
    label = dt.strftime('%b %d, %Y').replace(' 0', ' ')
    app = replace_block(app, 'ESPN_MKT_ASOF', json.dumps(label))
    app = replace_block(app, 'ESPN_MKT', json.dumps(mkt, ensure_ascii=False, separators=(',', ':')))
    app = replace_block(app, 'ESPN_OTHERS', json.dumps(others, ensure_ascii=False, separators=(',', ':')))
    app = replace_block(app, 'LAST', json.dumps(last, ensure_ascii=False, separators=(',', ':')))
    open(APP, 'w', encoding='utf-8', newline='\n').write(app)
    print(f"ESPN feed {asof}: {len(mkt)} app players with ESPN market data "
          f"({sum(1 for v in mkt.values() if v[0])} with a reliable ADP, {sum(1 for v in mkt.values() if v[1])} with a category rank), "
          f"{len(others)} other drafted players, {len(last)} with last-season stats")
    print('\n'.join(report) if report else 'no team changes or ESPN injury tags')


if __name__ == '__main__':
    main()
