"""Measure how 9-cat fantasy value changes with age, from five seasons of Basketball Reference per-game stats.

For each season: players with 20+ games, per-game 9-cat z-scores against the top 156 by minutes per game
(roughly the fantasy-relevant pool in 10-12 team leagues). FG% and FT% are volume-weighted impact
((pct - pool pct) * attempts); turnovers count against. Then pair each player's value with his next
season's and fit  change = a[age] + b * value  (b soaks up regression to the mean so a[age] is the
clean aging effect for an average player).
"""
import re, html, json, unicodedata, statistics as st
SCR = r"C:\Users\tyler\AppData\Local\Temp\claude\C--Users-tyler-OneDrive---The-University-of-Western-Ontario-Year-4-projects\1cc0017a-8b78-4519-8820-cc081b6e1adc\scratchpad"

def key(s):
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = re.sub(r'\b(jr|sr|ii|iii|iv)\b\.?', '', s)
    return re.sub(r'[^a-z]', '', s)

def parse(year):
    s = open(SCR + rf"\bbref_{year}_per_game.html", encoding='utf-8', errors='replace').read()
    t = s[s.find('id="per_game_stats"'):]
    t = t[:t.find('</table>')]
    rows = {}
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', t, re.S):
        cells = dict(re.findall(r'data-stat="([^"]+)"[^>]*>(.*?)</t[dh]>', tr, re.S))
        name = re.sub(r'<[^>]+>', '', cells.get('name_display', cells.get('player', ''))).strip()
        if not name or name == 'Player': continue
        name = html.unescape(name)
        k = key(name)
        if k in rows: continue            # first row is the season total for traded players
        def g(f):
            v = re.sub(r'<[^>]+>', '', cells.get(f, '')).strip()
            try: return float(v)
            except: return None
        rows[k] = dict(name=name, age=g('age'), G=g('games'), MP=g('mp_per_g'), PTS=g('pts_per_g'), TRB=g('trb_per_g'),
                       AST=g('ast_per_g'), STL=g('stl_per_g'), BLK=g('blk_per_g'), TP=g('fg3_per_g'), FGA=g('fga_per_g'),
                       FG=g('fg_per_g'), FTA=g('fta_per_g'), FT=g('ft_per_g'), TOV=g('tov_per_g'))
    return rows

def values(rows):
    ok = [r for r in rows.values() if r['G'] and r['G'] >= 20 and r['MP'] and None not in (r['PTS'], r['TRB'], r['AST'], r['STL'], r['BLK'], r['TP'], r['FGA'], r['FG'], r['FTA'], r['FT'], r['TOV'])]
    pool = sorted(ok, key=lambda r: -r['MP'])[:156]
    fgp = sum(r['FG'] for r in pool) / sum(r['FGA'] for r in pool)
    ftp = sum(r['FT'] for r in pool) / sum(r['FTA'] for r in pool)
    def raw(r):
        return dict(PTS=r['PTS'], REB=r['TRB'], AST=r['AST'], STL=r['STL'], BLK=r['BLK'], TPM=r['TP'],
                    FGI=r['FG'] - fgp * r['FGA'], FTI=r['FT'] - ftp * r['FTA'], TO=-r['TOV'])
    cats = list(raw(pool[0]).keys())
    mu = {c: st.mean(raw(r)[c] for r in pool) for c in cats}
    sd = {c: st.pstdev(raw(r)[c] for r in pool) for c in cats}
    out = {}
    for r in ok:
        x = raw(r)
        out[key(r['name'])] = dict(name=r['name'], age=r['age'], v=sum((x[c] - mu[c]) / sd[c] for c in cats))
    return out

seasons = {y: values(parse(y)) for y in (2022, 2023, 2024, 2025, 2026)}
pairs = []
for y in (2022, 2023, 2024, 2025):
    a, b = seasons[y], seasons[y + 1]
    for k, r in a.items():
        if k in b and r['age']:
            pairs.append((int(r['age']), r['v'], b[k]['v'] - r['v']))
print('pairs', len(pairs))

# least squares: change = a[age bin] + b * value, solved by alternating (small problem, no numpy needed)
binof = lambda age: max(20, min(35, age))
bins = sorted({binof(p[0]) for p in pairs})
b = 0.0
for _ in range(50):
    a = {k: st.mean(d - b * v for age, v, d in pairs if binof(age) == k) for k in bins}
    num = sum(v * (d - a[binof(age)]) for age, v, d in pairs); den = sum(v * v for age, v, d in pairs)
    b = num / den
n = {k: sum(1 for p in pairs if binof(p[0]) == k) for k in bins}
# light smoothing across neighbouring ages, weighted by sample size
sm = {}
for k in bins:
    ks = [j for j in (k - 1, k, k + 1) if j in a]
    w = [n[j] * (2 if j == k else 1) for j in ks]
    sm[k] = sum(a[j] * wj for j, wj in zip(ks, w)) / sum(w)
# how our z scale compares with FanScout's (sd of total value over the top 150)
fs_scale = None
print('b (regression to mean per z of value):', round(b, 3))
for k in bins:
    print(f'age {k:>2}{"-" if k==20 else "+" if k==35 else " "}: n={n[k]:>3}  raw change {a[k]:+.2f}  smoothed {sm[k]:+.2f}')
top = sorted(seasons[2026].values(), key=lambda r: -r['v'])[:150]
sd_ours = st.pstdev(r['v'] for r in top)
json.dump({'b': b, 'curve': sm, 'n': n, 'sd_top150': sd_ours}, open(SCR + r"\aging.json", 'w'))
print('sd of total value, our top 150 (2025-26):', round(sd_ours, 2))
