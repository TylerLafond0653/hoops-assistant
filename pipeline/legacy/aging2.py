import re, json, statistics as st
SCR = r"C:\Users\tyler\AppData\Local\Temp\claude\C--Users-tyler-OneDrive---The-University-of-Western-Ontario-Year-4-projects\1cc0017a-8b78-4519-8820-cc081b6e1adc\scratchpad"
APP = r"C:\Users\tyler\OneDrive - The University of Western Ontario\Year 4\projects\fantasy-draft\draft-room.html"
exec(open(SCR + r"\aging.py", encoding='utf-8').read().split("pairs = []")[0])

# 1) aging curve: change relative to all draftable players (removes the "had a good year, comes back
#    down" effect that FanScout's projections already account for), smoothed across neighbouring ages
rows = []
for y in (2022, 2023, 2024, 2025):
    a, b = seasons[y], seasons[y + 1]
    cut = sorted((r['v'] for r in a.values()), reverse=True)[179]
    for k, r in a.items():
        if r['v'] >= cut and r['age'] and k in b:
            rows.append((max(20, min(35, int(r['age']))), b[k]['v'] - r['v']))
overall = st.mean(d for _, d in rows)
n = {k: sum(1 for a, _ in rows if a == k) for k in range(20, 36)}
rel = {k: st.mean(d for a, d in rows if a == k) - overall for k in range(20, 36)}
sm = {}
for k in range(20, 36):
    ks = [j for j in (k - 1, k, k + 1) if j in rel]
    w = [n[j] * (2 if j == k else 1) for j in ks]
    sm[k] = sum(rel[j] * wj for j, wj in zip(ks, w)) / sum(w)

# 2) put it on FanScout's scale: compare spread of total value over each top 150
app = open(APP, encoding='utf-8').read()
data = app[app.find('const DATA=['):]
data = data[:data.find('\n];')]
fs = []
for line in data.split('\n')[1:]:
    m = re.match(r'\["([^"]+)".*\[([-\d., ]+)\]\],?$', line.strip())
    if m: fs.append((m.group(1), sum(float(x) for x in m.group(2).split(','))))
sd_fs = st.pstdev(v for _, v in fs)
top = sorted(seasons[2026].values(), key=lambda r: -r['v'])[:150]
sd_ours = st.pstdev(r['v'] for r in top)
scale = sd_fs / sd_ours
curve = {k: round(sm[k] * scale, 2) for k in range(20, 36)}
print('overall change of draftable players (removed):', round(overall, 2))
print('scale to FanScout units:', round(scale, 2), '(FanScout sd', round(sd_fs, 2), '/ ours', round(sd_ours, 2), ')')
print('per-year change in FanScout value by age:', curve)
print('samples per age:', n)

# 3) 2026-27 ages: Basketball Reference lists age on Feb 1 of the season, so add one for 2026-27
ages, missing = {}, []
for name, _ in fs:
    r = seasons_rows = None
    k = key(name)
    raw = parse(2026).get(k) or parse(2025).get(k)
    if raw and raw['age']:
        ages[name] = int(raw['age']) + (1 if k in parse(2026) else 2)
    else:
        missing.append(name)
print('ages found', len(ages), 'missing', missing)
json.dump({'curve': curve, 'ages': ages, 'missing': missing, 'n': n}, open(SCR + r"\aging_out.json", 'w', encoding='utf-8'), ensure_ascii=False)
