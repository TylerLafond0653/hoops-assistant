"""Grow the app's player list past 150.

1. Fit the app's 9-cat z-scores as a linear function of the projected per-game stats, using the
   existing 150 FanScout players (so every new player lands on exactly the same scale).
2. Young players: FanScout's rookie, sophomore, third- and fourth-year projections.
3. Veterans FanScout doesn't project: their 2025-26 per-game line (Basketball Reference), turned into
   z-scores, then the measured aging step for their age and the measured pull back toward average
   (value * -0.12 per season, from the same 1,426 player-seasons). Games: blend of last season's
   games and a typical 68.
4. Teams and positions from FantasyPros where it lists the player (current), else Basketball
   Reference (2025-26); rookies from Wikipedia's 2026 draft table. Rookie ages from class year.
Writes rows in the app's DATA format plus ages, then rebuilds the ADP block.
"""
import re, json, html, unicodedata, statistics as st
SCR = r"C:\Users\tyler\AppData\Local\Temp\claude\C--Users-tyler-OneDrive---The-University-of-Western-Ontario-Year-4-projects\1cc0017a-8b78-4519-8820-cc081b6e1adc\scratchpad"
APP = r"C:\Users\tyler\OneDrive - The University of Western Ontario\Year 4\projects\fantasy-draft\draft-room.html"

def key(s):
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = re.sub(r'\b(jr|sr|ii|iii|iv)\b\.?', '', s)
    return re.sub(r'[^a-z]', '', s)

app = open(APP, encoding='utf-8').read()
data = app[app.find('const DATA=['):]
data = data[:data.find('\n];')]
rows = []
for line in data.split('\n')[1:]:
    line = line.strip().rstrip(',')
    if line.startswith('['): rows.append(json.loads(line))
print('existing rows', len(rows))
have = {key(r[0]) for r in rows}
AGE = json.loads(re.search(r'const AGE=(\{.*?\});', app).group(1))
STEP = {int(k): v for k, v in json.loads(re.search(r'const AGE_STEP=(\{.*?\});', app).group(1)).items()}
ageStep = lambda a: STEP[max(20, min(35, a))]

# ---- 1. stats -> z, fitted on the existing 150 ------------------------------------------------
def lstsq(X, y):
    n = len(X[0]); A = [[sum(r[i] * r[j] for r in X) for j in range(n)] for i in range(n)]
    b = [sum(r[i] * t for r, t in zip(X, y)) for i in range(n)]
    for i in range(n):                       # Gaussian elimination
        p = max(range(i, n), key=lambda k: abs(A[k][i])); A[i], A[p] = A[p], A[i]; b[i], b[p] = b[p], b[i]
        for k in range(i + 1, n):
            f = A[k][i] / A[i][i]; A[k] = [a - f * c for a, c in zip(A[k], A[i])]; b[k] -= f * b[i]
    x = [0] * n
    for i in reversed(range(n)): x[i] = (b[i] - sum(A[i][j] * x[j] for j in range(i + 1, n))) / A[i][i]
    return x
# stats: [PTS,REB,AST,STL,BLK,3PM,FG%,FT%,TO,FGA,FTA]; z: [PTS,REB,AST,STL,BLK,3PM,FG,FT,TO]
feat = [lambda s: [1, s[0]], lambda s: [1, s[1]], lambda s: [1, s[2]], lambda s: [1, s[3]], lambda s: [1, s[4]],
        lambda s: [1, s[5]], lambda s: [1, s[6] * s[9], s[9]], lambda s: [1, s[7] * s[10], s[10]], lambda s: [1, s[8]]]
coef, fit_err = [], []
for c in range(9):
    X = [feat[c](r[5]) for r in rows]; y = [r[6][c] for r in rows]
    w = lstsq(X, y); coef.append(w)
    pred = [sum(a * b for a, b in zip(w, x)) for x in X]
    fit_err.append(round(max(abs(p - t) for p, t in zip(pred, y)), 3))
print('stats->z fit, worst error per category:', fit_err)
toz = lambda s: [round(sum(a * b for a, b in zip(coef[c], feat[c](s))), 2) for c in range(9)]

# ---- sources ---------------------------------------------------------------------------------
fs = json.load(open(SCR + r"\fs_all.json", encoding='utf-8'))
exec(open(SCR + r"\adp.py", encoding='utf-8').read().split("print('fantasypros rows'")[0])  # -> fpd
# FantasyPros positions (the ADP parser keeps team only; read positions from the same rows)
fpraw = open(SCR + r"\www_fantasypros_com_nba_adp_overall_php.html", encoding='utf-8', errors='replace').read()
fppos = {}
for row in fpraw[fpraw.find('<table'):].split('<tr>')[2:]:
    m = re.search(r'fp-player-name="([^"]+)".*?<small>\(([^)]*)\)</small>', row, re.S)
    if m and ' - ' in m.group(2): fppos[key(html.unescape(m.group(1)))] = m.group(2).split(' - ')[1].replace(',', '/')
draft = json.load(open(SCR + r"\draft2026_rows.json", encoding='utf-8'))
dinfo = {}
for r in draft:
    nm = r[2].replace('#', '').replace('*', '').replace('+', '').strip()
    cls = re.search(r'\((\s*(Fr|So|Jr|Sr|Gr)\.?\s*)\)', r[-1])
    dinfo[key(nm)] = dict(pos=r[3].replace('G/F', 'SG/SF'), cls=cls.group(2) if cls else None, pick=int(r[1]))

def bbref(year):
    s = open(SCR + rf"\bbref_{year}_per_game.html", encoding='utf-8', errors='replace').read()
    t = s[s.find('id="per_game_stats"'):]; t = t[:t.find('</table>')]
    out = {}
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', t, re.S):
        cells = dict(re.findall(r'data-stat="([^"]+)"[^>]*>(.*?)</t[dh]>', tr, re.S))
        name = html.unescape(re.sub(r'<[^>]+>', '', cells.get('name_display', '')).strip())
        if not name or name == 'Player' or key(name) in out: continue
        g = lambda f: (lambda v: float(v) if re.match(r'^-?[\d.]+$', v) else None)(re.sub(r'<[^>]+>', '', cells.get(f, '')).strip())
        out[key(name)] = dict(name=name, age=g('age'), team=re.sub(r'<[^>]+>', '', cells.get('team_name_abbr', '')).strip(),
                              pos=re.sub(r'<[^>]+>', '', cells.get('pos', '')).strip(), G=g('games'), MP=g('mp_per_g'),
                              PTS=g('pts_per_g'), TRB=g('trb_per_g'), AST=g('ast_per_g'), STL=g('stl_per_g'), BLK=g('blk_per_g'),
                              TP=g('fg3_per_g'), FGP=g('fg_pct'), FTP=g('ft_pct'), TOV=g('tov_per_g'), FGA=g('fga_per_g'), FTA=g('fta_per_g'))
    return out
b26, b25 = bbref(2026), bbref(2025)
FIX = {'CHO': 'CHA', 'BRK': 'BKN', 'PHO': 'PHX', '2TM': None, '3TM': None, '4TM': None}
POSMAP = {'G': 'PG/SG', 'F': 'SF/PF', 'G-F': 'SG/SF', 'F-G': 'SF/SG', 'F-C': 'PF/C', 'C-F': 'C/PF', 'PG-SG': 'PG/SG', 'SG-PG': 'SG/PG', 'SF-PF': 'SF/PF', 'PF-SF': 'PF/SF', 'PF-C': 'PF/C', 'C-PF': 'C/PF', 'SG-SF': 'SG/SF', 'SF-SG': 'SF/SG'}
normpos = lambda p: POSMAP.get(p, p) if p else 'UTIL'
CLS_AGE = {'Fr': 20, 'So': 21, 'Jr': 22, 'Sr': 23, 'Gr': 24}
# long absences reported on ESPN's injury page (Sept 2026) for players FanScout doesn't project
OUT_GAMES = {'shaedonsharpe': 25, 'markwilliams': 30, 'dontedivincenzo': 5, 'mosesmoody': 50}

new, ages = [], {}
def team_pos(k, fallback_team='', fallback_pos=''):
    t = fpd[k]['team'] if k in fpd and fpd[k]['team'] not in ('', 'FA') else FIX.get(fallback_team, fallback_team) or 'FA'
    p = fppos.get(k) or (dinfo[k]['pos'] if k in dinfo else None) or normpos(fallback_pos)
    return t, p
def age_of(k, exp):
    if k in b26 and b26[k]['age']: return int(b26[k]['age']) + 1
    if k in b25 and b25[k]['age']: return int(b25[k]['age']) + 2
    if k in dinfo and dinfo[k]['cls']: return CLS_AGE[dinfo[k]['cls']]
    return 21 + int(exp or 0) if exp is not None else 25

# ---- 2. FanScout young players ---------------------------------------------------------------
for name, r in fs.items():
    k = key(name)
    if k in have: continue
    s = [r['p_pts'], r['p_reb'], r['p_ast'], r['p_stl'], r['p_blk'], r['p_tpm'], r['p_fgP'], r['p_ftP'], r['p_tov'], r['p_fga'], r['p_fta']]
    s = [round(x, 3 if i in (6, 7) else 1) for i, x in enumerate(s)]
    bb = b26.get(k) or b25.get(k) or {}
    team, pos = team_pos(k, r.get('team', ''), bb.get('pos', ''))
    if team == 'FA' and r.get('team'): team = r['team']
    new.append(dict(name=name, team=team, pos=pos, G=int(float(r['gamesPlayed'])), MIN=int(round(r['p_totalMinutes'])), s=s, z=toz(s),
                    src='FanScout ' + {'0': 'rookie', '1': 'sophomore', '2': 'third-year', '3': 'fourth-year'}.get(str(r.get('exp')), 'young-player') + ' projection'))
    ages[name] = age_of(k, r.get('exp'))
    have.add(k)

# ---- 3. veterans from last season ------------------------------------------------------------
for k, r in b26.items():
    if k in have or not r['G'] or r['G'] < 20 or not r['MP'] or r['MP'] < 14: continue
    if None in (r['PTS'], r['TRB'], r['AST'], r['STL'], r['BLK'], r['TP'], r['TOV'], r['FGA'], r['FTA']): continue
    fgp = r['FGP'] if r['FGP'] is not None else 0.45; ftp = r['FTP'] if r['FTP'] is not None else 0.75
    s = [r['PTS'], r['TRB'], r['AST'], r['STL'], r['BLK'], r['TP'], round(fgp, 3), round(ftp, 3), r['TOV'], r['FGA'], r['FTA']]
    age26 = int(r['age'])
    z = toz(s)
    # next season: measured pull back toward average (-12% of value) plus the aging step, spread over 9 cats
    z = [round(v * 0.88 + ageStep(age26) / 9, 2) for v in z]
    G = OUT_GAMES.get(k, int(round(min(76, max(30, 0.55 * r['G'] + 0.45 * 68)))))
    team, pos = team_pos(k, r['team'], r['pos'])
    new.append(dict(name=r['name'], team=team, pos=pos, G=G, MIN=int(round(r['MP'])), s=s, z=z, src='estimate from 2025-26 stats, adjusted for age'))
    ages[r['name']] = age26 + 1
    have.add(k)

# keep the useful ones: everyone valued at least as high as the ~350th player, plus anyone ESPN or
# Yahoo managers draft
tot = lambda z: sum(z)
allvals = sorted([tot(r[6]) for r in rows] + [tot(n['z']) for n in new], reverse=True)
cut = allvals[min(len(allvals) - 1, 349)]
keep = [n for n in new if tot(n['z']) >= cut or key(n['name']) in fpd]
keep.sort(key=lambda n: -tot(n['z']))
print('candidates', len(new), 'kept', len(keep), 'value cut', round(cut, 2), '-> total players', len(rows) + len(keep))
print('top new:', [(n['name'], n['team'], n['pos'], round(tot(n['z']), 1), ages[n['name']]) for n in keep[:25]])
for nm in ('AJ Dybantsa', 'Josh Hart', 'Draymond Green', 'Jordan Poole', 'Brook Lopez', 'Klay Thompson', 'Shaedon Sharpe', 'Tre Johnson', 'Mark Williams'):
    m = [n for n in keep if n['name'] == nm]
    print(' ', nm, (m[0]['team'], m[0]['pos'], m[0]['G'], round(tot(m[0]['z']), 1), m[0]['src']) if m else 'not kept')

lines = ['[%s, %s, %s, %d, %d, %s, %s],' % (json.dumps(n['name'], ensure_ascii=False), json.dumps(n['team']), json.dumps(n['pos']), n['G'], n['MIN'],
                                          json.dumps(n['s']), json.dumps(n['z'])) for n in keep]
json.dump({'lines': lines, 'ages': {n['name']: ages[n['name']] for n in keep}, 'src': {n['name']: n['src'] for n in keep}},
          open(SCR + r"\expand_out.json", 'w', encoding='utf-8'), ensure_ascii=False)
