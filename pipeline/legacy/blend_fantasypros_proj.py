"""One-time (Sept 29, 2026): add FantasyPros' consensus projections ("we combine all the major basketball
projections into a consensus") as a third projection source.

Per-game stats and 9-cat values become FanScout 1/3, ESPN 1/3, FantasyPros 1/3 (the app's rows were already
FanScout/ESPN 50/50, so new = 2/3 old + 1/3 FantasyPros). For players the app estimated itself (EST 'e'),
FantasyPros gets half, since the estimate is the weakest source. Games are NOT blended: the app's games already
carry hand-checked injury news (FantasyPros' games run optimistic, like ESPN's).
FG%/FT% use the app's attempts with FantasyPros' percentages (FantasyPros doesn't publish attempts).
Why: averaging independent forecasts beats any one of them; last season, blending ESPN's projection with the
expert consensus beat both (analysis/backtest_sources.py).
"""
import html, json, os, re, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'analysis'))
from common import key, load_app, app_players, ZMap   # noqa: E402

APP = os.path.join(ROOT, 'draft-room.html')
SRC = os.path.join(ROOT, 'analysis', 'data', 'fp_proj_2026-09-29.html')
app = open(APP, encoding='utf-8').read()
assert '// FantasyPros consensus projections blended in' not in app, 'already blended'
Z = ZMap(app_players(load_app()))       # fitted on the app's current top 150 (same scale as everything else)

s = open(SRC, encoding='utf-8', errors='replace').read()
body = s[s.find('<table'):]; body = body[:body.find('</table>')]
num = lambda x: float(x.replace(',', '')) if re.match(r'^[\d,.]+$', x or '') else None
fp = {}
for row in body.split('<tr')[2:]:
    m = re.search(r'fp-player-name="([^"]+)"', row)
    if not m: continue
    c = [re.sub(r'<[^>]+>', '', x).strip() for x in re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)][1:]
    pts, reb, ast, blk, stl, fgp, ftp, tpm, gp, mins, to = (num(x) for x in c[:11])
    if gp: fp[key(html.unescape(m.group(1)))] = dict(pts=pts / gp, reb=reb / gp, ast=ast / gp, blk=blk / gp, stl=stl / gp,
                                                     fg=fgp, ft=ftp, tpm=tpm / gp, to=to / gp, mins=mins / gp)
print('FantasyPros projections:', len(fp))
EST = json.loads(re.search(r'const EST=(\{.*?\});', app).group(1))
i0 = app.index('const DATA=['); i1 = app.index('\n];', i0)
lines = app[i0:i1].split('\n'); n = 0; moved = []
for li, l in enumerate(lines):
    t = l.strip()
    if not t.startswith('["'): continue
    name, team, pos, g, mn, st, z = json.loads(t.rstrip(','))
    f = fp.get(key(name))
    if not f or f['fg'] is None or f['ft'] is None: continue
    w = 0.5 if EST.get(name) == 'e' else 1 / 3
    fga, fta = st[9], st[10]
    line = [f['pts'], f['reb'], f['ast'], f['stl'], f['blk'], f['tpm'], f['fg'] * fga, fga, f['ft'] * fta, fta, f['to']]
    zf = Z.z(line)
    z2 = [round((1 - w) * a + w * b, 2) for a, b in zip(z, zf)]
    st2 = [round((1 - w) * st[0] + w * f['pts'], 1), round((1 - w) * st[1] + w * f['reb'], 1), round((1 - w) * st[2] + w * f['ast'], 1),
           round((1 - w) * st[3] + w * f['stl'], 1), round((1 - w) * st[4] + w * f['blk'], 1), round((1 - w) * st[5] + w * f['tpm'], 1),
           round((1 - w) * st[6] + w * f['fg'], 3), round((1 - w) * st[7] + w * f['ft'], 3), round((1 - w) * st[8] + w * f['to'], 1), fga, fta]
    mn2 = int(round((1 - w) * mn + w * f['mins']))
    moved.append((round(sum(z2) - sum(z), 2), name))
    comma = t.endswith(',')
    lines[li] = l[:len(l) - len(l.lstrip())] + '[%s, %s, %s, %d, %d, %s, %s]' % (
        json.dumps(name, ensure_ascii=False), json.dumps(team), json.dumps(pos), g, mn2, json.dumps(st2), json.dumps(z2)) + (',' if comma else '')
    n += 1
app = app[:i0] + '\n'.join(lines) + app[i1:]
note = ("// FantasyPros consensus projections blended in (Sept 29, 2026): per-game stats and values are now FanScout,\n"
        "// ESPN and FantasyPros' consensus in equal parts (FantasyPros half for our own estimates); games unchanged.\n")
k = app.index('const DISAGREE=')
app = app[:k] + note + app[k:]
open(APP, 'w', encoding='utf-8', newline='\n').write(app)
moved.sort()
print('blended', n, 'players | biggest drops:', moved[:6], '| biggest rises:', moved[-6:])
