"""Blend FanScout (and our veteran estimates) with ESPN's 2026-27 projections.

- ESPN stat lines -> the app's 9-cat values with the same linear formula fitted on the first 150
  FanScout rows (so both sources sit on one scale).
- Weights: FanScout 50 / ESPN 50 (no evidence either is more accurate; averaging cuts error). For our
  own estimates (EST 'e'): ESPN 60 / estimate 40, ESPN's projection being the better-informed one.
- Stat lines are blended the same way (FG%/FT% from blended makes and attempts); games = the average.
- DISAGREE[name] = |FanScout value - ESPN value| (9-cat total) for every blended player.
Players ESPN doesn't project keep their original numbers.
"""
import re, json, unicodedata
SCR = r"C:\Users\tyler\AppData\Local\Temp\claude\C--Users-tyler-OneDrive---The-University-of-Western-Ontario-Year-4-projects\1cc0017a-8b78-4519-8820-cc081b6e1adc\scratchpad"
APP = r"C:\Users\tyler\OneDrive - The University of Western Ontario\Year 4\projects\fantasy-draft\draft-room.html"
def key(s):
    s = unicodedata.normalize('NFKD', s); s = ''.join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = re.sub(r'\b(jr|sr|ii|iii|iv)\b\.?', '', s); return re.sub(r'[^a-z]', '', s)

app = open(APP, encoding='utf-8').read()
assert 'const DISAGREE=' not in app, 'already blended'
i0 = app.index('const DATA=['); i1 = app.index('\n];', i0)
block = app[i0:i1]
lines = block.split('\n')
rows = []  # (line index, parsed row)
for li, line in enumerate(lines):
    t = line.strip()
    if t.startswith('["'):
        rows.append((li, json.loads(t.rstrip(','))))
EST = json.loads(re.search(r'const EST=(\{.*?\});', app).group(1))
print('rows', len(rows))

# fit stats -> z on the first 150 (pure FanScout)
def lstsq(X, y):
    n = len(X[0]); A = [[sum(r[i]*r[j] for r in X) for j in range(n)] for i in range(n)]; b = [sum(r[i]*t for r, t in zip(X, y)) for i in range(n)]
    for i in range(n):
        p = max(range(i, n), key=lambda k: abs(A[k][i])); A[i], A[p] = A[p], A[i]; b[i], b[p] = b[p], b[i]
        for k in range(i+1, n):
            f = A[k][i]/A[i][i]; A[k] = [a - f*c for a, c in zip(A[k], A[i])]; b[k] -= f*b[i]
    x = [0]*n
    for i in reversed(range(n)): x[i] = (b[i] - sum(A[i][j]*x[j] for j in range(i+1, n)))/A[i][i]
    return x
feat = [lambda s: [1, s[0]], lambda s: [1, s[1]], lambda s: [1, s[2]], lambda s: [1, s[3]], lambda s: [1, s[4]],
        lambda s: [1, s[5]], lambda s: [1, s[6]*s[9], s[9]], lambda s: [1, s[7]*s[10], s[10]], lambda s: [1, s[8]]]
base = [r for _, r in rows[:150]]
coef = [lstsq([feat[c](r[5]) for r in base], [r[6][c] for r in base]) for c in range(9)]
toz = lambda s: [round(sum(a*b for a, b in zip(coef[c], feat[c](s))), 2) for c in range(9)]

# ESPN projections (2026-27 = seasonId 2027, projected = statSourceId 1, season split 0)
d = json.load(open(SCR + r"\espn_proj.json", encoding='utf-8'))
espn = {}
for p in d['players']:
    pl = p['player']
    proj = [s for s in pl.get('stats', []) if s.get('seasonId') == 2027 and s.get('statSourceId') == 1 and s.get('statSplitTypeId') == 0]
    if not proj or not proj[0].get('averageStats'): continue
    a = proj[0]['averageStats']; g = lambda k: float(a.get(k, 0) or 0)
    if g('14') <= 0 or g('42') <= 0: continue
    espn[key(pl['fullName'])] = dict(name=pl['fullName'], G=g('42'), MIN=g('40'),
        s=[g('0'), g('6'), g('3'), g('2'), g('1'), g('17'), g('13')/g('14'), (g('15')/g('16') if g('16') > 0 else 0.75), g('11'), g('14'), g('16')],
        fgm=g('13'), ftm=g('15'))
print('ESPN projections', len(espn))

dis, blended, only_fs, notes = {}, 0, [], []
for li, r in rows:
    name, team, pos, G, MIN, s, z = r
    e = espn.get(key(name))
    if not e:
        only_fs.append(name); continue
    wE = 0.6 if EST.get(name) == 'e' else 0.5
    ze = toz(e['s'])
    dis[name] = round(abs(sum(z) - sum(ze)), 2)
    zb = [round((1-wE)*a + wE*b, 2) for a, b in zip(z, ze)]
    # blended stat line: counting stats averaged; FG%/FT% from blended makes and attempts
    cnt = lambda k: (1-wE)*s[k] + wE*e['s'][k]
    fga, fta = cnt(9), cnt(10)
    fgm = (1-wE)*s[6]*s[9] + wE*e['fgm']; ftm = (1-wE)*s[7]*s[10] + wE*e['ftm']
    sb = [round(cnt(0), 1), round(cnt(1), 1), round(cnt(2), 1), round(cnt(3), 1), round(cnt(4), 1), round(cnt(5), 1),
          round(fgm/fga, 3) if fga else s[6], round(ftm/fta, 3) if fta else s[7], round(cnt(8), 1), round(fga, 1), round(fta, 1)]
    Gb = int(round((1-wE)*G + wE*e['G'])); Mb = int(round((1-wE)*MIN + wE*e['MIN']))
    lines[li] = '[%s, %s, %s, %d, %d, %s, %s],' % (json.dumps(name, ensure_ascii=False), json.dumps(team), json.dumps(pos), Gb, Mb, json.dumps(sb), json.dumps(zb))
    blended += 1
# the last row must not end with a comma issue: keep original trailing comma state
last_li = rows[-1][0]
if not block.split('\n')[last_li].rstrip().endswith(','):
    lines[last_li] = lines[last_li].rstrip(',')
print('blended', blended, '| FanScout/estimate only', len(only_fs), only_fs[:12])
big = sorted(dis.items(), key=lambda x: -x[1])[:15]
print('biggest disagreements:', big)
new_block = '\n'.join(lines)
app = app[:i0] + new_block + app[i1:]
hdr = ("// Projections are blended (Sept 25, 2026): FanScout 50% + ESPN's 2026-27 projections 50% (ESPN 60% for\n"
       "// players we estimated ourselves), category by category on one scale. Games are averaged.\n"
       "// DISAGREE = how far apart the two sources were on a player's 9-cat value; big gaps add uncertainty.\n"
       "const DISAGREE=" + json.dumps(dis, ensure_ascii=False, separators=(',', ':')) + ";\n")
k = app.index('const EST=')
k = app.rfind('\n', 0, app.rfind('// Where the added players', 0, k)) + 1
app = app[:k] + hdr + app[k:]
open(APP, 'w', encoding='utf-8', newline='\n').write(app)
import statistics as st
print('disagreement median', st.median(dis.values()), '90th pct', sorted(dis.values())[int(len(dis)*0.9)])
