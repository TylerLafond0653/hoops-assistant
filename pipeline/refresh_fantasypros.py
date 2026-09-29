"""Refresh what the app takes from FantasyPros, then write it into draft-room.html.

  EXPERTS          {name: [consensus rank, best rank, worst rank]}: FantasyPros' expert consensus for roto /
                   category leagues (Yahoo's analysts, Razzball, FantasyPros and others). Last season it predicted
                   real 9-cat value about as well as ESPN's projections, and blending the two beat either one
                   (analysis/backtest_sources.py); in a league drafting off it, meeting it halfway won the most weeks
                   (analysis/backtest_experts_league.py). The app uses it as the market and to predict who
                   experienced leaguemates take.
  EXPERTS_OTHERS   [[name, consensus rank]] for players outside the app's list the experts rank in their top 170
  ADP, ADP_OTHERS  Yahoo and ESPN ADP from FantasyPros' ADP page: {name: [Yahoo, ESPN]}

Run on its own:  python pipeline/refresh_fantasypros.py [--cached]
It also runs as part of python pipeline/refresh_espn.py.
"""
import datetime, glob, html, json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, os.path.join(ROOT, 'analysis'))
from common import key   # noqa: E402

APP = os.path.join(ROOT, 'draft-room.html')
DATA = os.path.join(ROOT, 'analysis', 'data')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36'
ECR_URL = 'https://www.fantasypros.com/nba/rankings/overall.php'
ADP_URL = 'https://www.fantasypros.com/nba/adp/overall.php'


def fetch(url, stem, cached):
    files = sorted(glob.glob(os.path.join(DATA, f'{stem}_20??-??-??.html')))
    if cached and files: return files[-1]
    path = os.path.join(DATA, f'{stem}_{datetime.date.today().isoformat()}.html')
    subprocess.run(['curl', '-sL', '--compressed', '-A', UA, '-o', path, '--max-time', '90', url], check=True)
    return path


def parse_ecr(path):
    s = open(path, encoding='utf-8', errors='replace').read()
    i = s.index('ecrData =') + len('ecrData ='); j = s.index('};', i) + 1
    d = json.loads(s[i:j].strip())
    rows = {key(p['player_name']): (p['player_name'], float(p['rank_ecr']), int(p['rank_min']), int(p['rank_max'])) for p in d['players']}
    return rows, d


def parse_adp(path):
    s = open(path, encoding='utf-8', errors='replace').read()
    body = s[s.find('<table'):]; body = body[:body.find('</table>')]
    num = lambda x: float(x) if re.match(r'^\s*[\d.]+\s*$', x or '') else None
    out = {}
    for row in body.split('<tr>')[2:]:          # one row at a time, so an injury tag can't shift the columns
        m = re.search(r'fp-player-name="([^"]+)"', row)
        if not m: continue
        cells = re.findall(r'<td>([^<]*)</td>', row)
        _, yh, es, avg = (cells + [None] * 4)[:4]
        out[key(html.unescape(m.group(1)))] = (html.unescape(m.group(1)), num(yh), num(es), num(avg))
    return out


def replace_block(app, name, js):
    pat = re.compile(r'^const %s=.*?;\n' % re.escape(name), re.M | re.S)
    line = f'const {name}={js};\n'
    if pat.search(app): return pat.sub(lambda m: line, app, count=1)
    anchor = app.index('// Injury and role news that matters on draft day')
    return app[:anchor] + line + app[anchor:]


def main(cached=False):
    app = open(APP, encoding='utf-8').read()
    i0 = app.index('const DATA=['); i1 = app.index('\n];', i0)
    names = {key(json.loads(l.strip().rstrip(','))[0]): json.loads(l.strip().rstrip(','))[0]
             for l in app[i0:i1].split('\n') if l.strip().startswith('["')}
    try:
        ecr, meta = parse_ecr(fetch(ECR_URL, 'fp_ecr', cached))
        adp = parse_adp(fetch(ADP_URL, 'fp_adp', cached))
    except Exception as e:
        print(f"(FantasyPros was unavailable: {e}. The app keeps its previous experts and ADP data.)")
        return
    f = lambda v: None if v is None else (int(v) if float(v).is_integer() else v)
    experts = {names[k]: [f(r[1]), r[2], r[3]] for k, r in ecr.items() if k in names}
    others = sorted([r[0], f(r[1])] for k, r in ecr.items() if k not in names and r[1] <= 170)
    adp_app = {names[k]: [f(r[1]), f(r[2])] for k, r in adp.items() if k in names and (r[1] is not None or r[2] is not None)}
    adp_oth = sorted(([r[0], f(r[1]), f(r[2])] for k, r in adp.items() if k not in names and (r[3] or 999) <= 170), key=lambda x: x[0])
    today = datetime.date.today().strftime('%b %d, %Y').replace(' 0', ' ')
    j = lambda v: json.dumps(v, ensure_ascii=False, separators=(',', ':'))
    app = replace_block(app, 'EXPERTS_ASOF', json.dumps(f"{meta.get('last_updated', '?')} ({meta.get('total_experts', '?')} experts)"))
    app = replace_block(app, 'EXPERTS', j(experts))
    app = replace_block(app, 'EXPERTS_OTHERS', j(others))
    app = replace_block(app, 'ADP_ASOF', json.dumps(today))
    app = replace_block(app, 'ADP', j(adp_app))
    app = replace_block(app, 'ADP_OTHERS', j(adp_oth))
    open(APP, 'w', encoding='utf-8', newline='\n').write(app)
    print(f"FantasyPros: expert consensus for {len(experts)} app players ({meta.get('total_experts')} experts, updated "
          f"{meta.get('last_updated')}), {len(others)} other players the experts rank top 170; ADP for {len(adp_app)} app players")


if __name__ == '__main__':
    main('--cached' in sys.argv)
