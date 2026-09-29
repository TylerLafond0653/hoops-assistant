"""Refresh everything the app takes from ESPN, then write it into draft-room.html.

  ESPN_MKT     {name: [ESPN live ADP, ESPN category-league rank]} for the app's players: where ESPN
               managers actually draft (the opponent model and the market view use these)
  ESPN_OTHERS  [[name, ESPN live ADP, category rank]] for players outside the app's list that ESPN managers
               still draft (they use up other teams' picks in the simulator)
  LAST         last season's actual per-game stats (the board's "2025-26 actual" view)
  teams        every player's current NBA team, from ESPN (written into the app's player rows)

Then it prints an injury check built from ESPN's official NBA injury report (the one on ESPN.com, with
dates and comments), compared with the app's hand-checked injury notes (NEWS):
  NEW    on the report, but the app has no note yet
  CHECK  ESPN has newer news than the app's note, or ESPN says Out while the app says watch/ok
  noted  the app already has it
Day-to-day entries older than 10 days are counted but not listed: many are leftovers from last season or
the summer. (ESPN's fantasy feed also tags about 45 players "day-to-day" with its own "injured" flag off;
those tags are ignored.) Injury notes stay hand-checked: read the NEW/CHECK lines and update the notes.

Run before the draft:   python pipeline/refresh_espn.py            (fetches fresh data)
                        python pipeline/refresh_espn.py --cached   (re-uses the newest cached data)
"""
import datetime, glob, json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, os.path.join(ROOT, 'analysis'))
from common import key, ESPN_TEAM, load_bbref   # noqa: E402

APP = os.path.join(ROOT, 'draft-room.html')
DATA = os.path.join(ROOT, 'analysis', 'data')
URL = 'https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/2027/segments/0/leaguedefaults/1?view=kona_player_info'
INJ_URL = 'https://site.web.api.espn.com/apis/site/v2/sports/basketball/nba/injuries'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36'
# ESPN's default leagues draft 10 teams x 13 rounds, so its ADP bunches up near 130-140 for anyone rarely
# drafted. Past this point only the category rank is used.
ADP_RELIABLE = 115
RECENT_DAYS = 10
MONTHS = {m: i for i, m in enumerate(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], 1)}
NEWS_ROW = re.compile(r"\['((?:[^'\\]|\\.)+)','(out|watch|ok)','((?:[^'\\]|\\.)*)','([A-Z][a-z]{2}) (\d{1,2})'\]")


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


def fetch_injuries(cached):
    """ESPN's official NBA injury report, cached by date. None if it can't be fetched."""
    files = sorted(glob.glob(os.path.join(DATA, 'nba_injuries_20??-??-??.json')))
    path = files[-1] if cached and files else os.path.join(DATA, f'nba_injuries_{datetime.date.today().isoformat()}.json')
    try:
        if not (cached and files):
            subprocess.run(['curl', '-sL', '-A', UA, '-o', path, '--max-time', '60', INJ_URL], check=True)
        d = json.load(open(path, encoding='utf-8'))
        if 'injuries' not in d: raise ValueError('unexpected format')
        return d
    except Exception as e:
        print(f"(ESPN's injury report was unavailable: {e}. Draft data and teams were still updated.)")
        return None


def app_news(app, today):
    """the app's hand-checked injury notes: {key: (name, flag, text, date of the note)}"""
    out = {}
    for m in NEWS_ROW.finditer(app):
        mon, day = MONTHS[m.group(4)], int(m.group(5))
        yr = today.year if (mon, day) <= (today.month, today.day) else today.year - 1
        name = m.group(1).replace("\\'", "'")
        out[key(name)] = (name, m.group(2), m.group(3), datetime.date(yr, mon, day))
    return out


def injury_check(inj, names, news, today):
    ents = []
    for t in inj.get('injuries', []):
        for i in t.get('injuries', []):
            k = key(i['athlete']['displayName'])
            if k not in names: continue
            d = (i.get('date') or '')[:10]
            ents.append(dict(k=k, name=names[k][0], out=i.get('status') == 'Out',
                             date=datetime.date.fromisoformat(d) if d else None,
                             text=' '.join((i.get('shortComment') or '').split()),
                             back=((i.get('details') or {}).get('returnDate') or '')[:10]))

    def tag(e):
        n = news.get(e['k'])
        if not n: return 'NEW  '
        if e['out'] and n[1] != 'out': return 'CHECK'
        if e['date'] and e['date'] > n[3]: return 'CHECK'
        return 'noted'

    def fmt(e):
        text = e['text'] if len(e['text']) <= 150 else e['text'][:147] + '...'
        back = f", back ~{e['back']}" if e['back'] else ''
        when = f"{e['date']:%b %d}" if e['date'] else 'no date'
        return f"  [{tag(e)}] {e['name']} ({when}{back}): {text}"

    recent = lambda e: e['date'] is not None and (today - e['date']).days <= RECENT_DAYS
    outs = sorted((e for e in ents if e['out']), key=lambda e: e['date'] or today, reverse=True)
    dtd = sorted((e for e in ents if not e['out'] and recent(e)), key=lambda e: e['date'], reverse=True)
    older = [e for e in ents if not e['out'] and not recent(e)]
    lines = ["Injury check (ESPN's NBA injury report, players in the app):",
             " OUT:" if outs else " OUT: none"]
    lines += [fmt(e) for e in outs]
    lines.append(f" Day-to-day with news in the last {RECENT_DAYS} days:" if dtd else f" Day-to-day with news in the last {RECENT_DAYS} days: none")
    lines += [fmt(e) for e in dtd]
    lines.append(f" {len(older)} older day-to-day entries skipped (mostly leftovers from last season or the summer).")
    listed = {e['k'] for e in ents}
    gone = [n[0] for k, n in news.items() if n[1] in ('out', 'watch') and k not in listed and k in names
            and not n[2].startswith('Unsigned')]       # roster notes, not injuries
    if gone:
        lines.append(" In the app's notes but not on ESPN's injury report now (fine if the note is about risk, "
                     "not a current injury): " + ', '.join(gone))
    todo = sum(1 for e in outs + dtd if tag(e) != 'noted')
    lines.append(f" -> {todo} to look at (NEW/CHECK): send those lines to Claude to update the app's injury notes." if todo
                 else " -> Nothing new: the app's injury notes are up to date.")
    return lines


def apply_teams(app, teams):
    """write ESPN's current team into the app's player rows; returns (app, list of changes)"""
    i0 = app.index('const DATA=['); i1 = app.index('\n];', i0)
    lines = app[i0:i1].split('\n'); changes = []
    for li, l in enumerate(lines):
        t = l.strip()
        if not t.startswith('["'): continue
        r = json.loads(t.rstrip(','))
        new = teams.get(key(r[0]))
        if new and new != r[1]:
            changes.append(f"  {r[0]}: {r[1]} -> {new}")
            r[1] = new
            lines[li] = l[:len(l) - len(l.lstrip())] + '[%s, %s, %s, %d, %d, %s, %s]' % (
                json.dumps(r[0], ensure_ascii=False), json.dumps(r[1]), json.dumps(r[2]), r[3], r[4],
                json.dumps(r[5]), json.dumps(r[6])) + (',' if t.endswith(',') else '')
    return app[:i0] + '\n'.join(lines) + app[i1:], changes


def replace_block(app, name, js):
    """swap `const NAME=...;` (one line) for the new value, or insert it before the injury notes"""
    pat = re.compile(r'^const %s=.*?;\n' % re.escape(name), re.M | re.S)
    line = f'const {name}={js};\n'
    if pat.search(app):
        return pat.sub(lambda m: line, app, count=1)
    anchor = app.index('// Injury and role news that matters on draft day')
    return app[:anchor] + line + app[anchor:]


def main():
    cached = '--cached' in sys.argv
    path = newest_cached() if cached else fetch()
    asof = re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(path)).group(1)
    d = json.load(open(path, encoding='utf-8'))
    app = open(APP, encoding='utf-8').read()
    i0 = app.index('const DATA=['); i1 = app.index('\n];', i0)
    rows = [json.loads(l.strip().rstrip(',')) for l in app[i0:i1].split('\n') if l.strip().startswith('["')]
    names = {key(r[0]): r for r in rows}

    mkt, others, last, teams = {}, [], {}, {}
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
            if team: teams[k] = team
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
    app, changes = apply_teams(app, teams)
    open(APP, 'w', encoding='utf-8', newline='\n').write(app)
    print(f"ESPN data {asof}: {len(mkt)} app players with ESPN draft data "
          f"({sum(1 for v in mkt.values() if v[0])} with a reliable ADP, {sum(1 for v in mkt.values() if v[1])} with a category rank), "
          f"{len(others)} other drafted players, {len(last)} with last-season stats")
    print(f"Team changes applied: {len(changes)}" + (':' if changes else ''))
    for c in changes: print(c)
    inj = fetch_injuries(cached)
    if inj:
        print('\n'.join(injury_check(inj, names, app_news(app, dt), dt)))


if __name__ == '__main__':
    main()
