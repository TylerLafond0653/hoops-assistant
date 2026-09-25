import re, json, unicodedata
SCR = r"C:\Users\tyler\AppData\Local\Temp\claude\C--Users-tyler-OneDrive---The-University-of-Western-Ontario-Year-4-projects\1cc0017a-8b78-4519-8820-cc081b6e1adc\scratchpad"
APP = r"C:\Users\tyler\OneDrive - The University of Western Ontario\Year 4\projects\fantasy-draft\draft-room.html"
exec(open(SCR + r"\adp.py", encoding='utf-8').read().split("print('fantasypros rows'")[0])  # -> fpd, key
ex = json.load(open(SCR + r"\expand_out.json", encoding='utf-8'))
s = open(APP, encoding='utf-8').read()
assert 'const EST=' not in s, 'already expanded'

# 1) append the new players to DATA (ids follow DATA order, so existing picks keep their players)
i = s.index('const DATA=['); j = s.index('\n];', i)
block = '\n// ---- added 2026-09-25: players 151+ ----\n' + '\n'.join(ex['lines'])
s = s[:j] + block + s[j:]
s = s.replace("// FanScout 2026-27 projections, pulled 2026-09-24 (https://fanscout.pro/projections).",
  "// FanScout 2026-27 projections, pulled 2026-09-24 (https://fanscout.pro/projections). Players 151+ were added\n"
  "// 2026-09-25: FanScout's rookie / sophomore / third- and fourth-year projections, and for veterans\n"
  "// FanScout doesn't project, an estimate from their 2025-26 line (see EST).")

# 2) where each added player's numbers come from
code = {}
for n, src in ex['src'].items():
    code[n] = 'e' if src.startswith('estimate') else 'r' if 'rookie' in src else 'y'
est = ("// Where the added players' numbers come from: r = FanScout rookie projection, y = FanScout young-player\n"
       "// projection (years 2-4), e = estimate from the 2025-26 line: stats turned into 9-cat values with the same\n"
       "// formula as the first 150 (fitted to within 0.2 per category), then the measured aging step for his age\n"
       "// and the measured 12% pull back toward average. Games blend last season's with a typical 68.\n"
       "const EST=" + json.dumps(code, ensure_ascii=False, separators=(',', ':')) + ";\n")
k = s.index('const ADP_ASOF=')
k = s.rfind('\n', 0, s.rfind('//', 0, k)) + 1
s = s[:k] + est + s[k:]

# 3) ages for the added players
m = re.search(r'const AGE=(\{.*?\});', s)
ages = json.loads(m.group(1)); ages.update(ex['ages'])
s = s[:m.start(1)] + json.dumps(ages, ensure_ascii=False, separators=(',', ':')) + s[m.end(1):]
s = s.replace("// 2026 rookies Boozer, Peterson and Caleb Wilson from their Wikipedia birthdates.",
  "// 2026 rookies Boozer, Peterson and Caleb Wilson from their Wikipedia birthdates; other 2026 rookies from\n"
  "// their final school year in Wikipedia's 2026 draft table (freshman 20, sophomore 21, junior 22, senior 23).")

# 4) rebuild ADP for the bigger list: everyone in the list, and the rest as "others"
data = s[s.find('const DATA=['):]; data = data[:data.find('\n];')]
names = re.findall(r'^\["([^"]+)"', data, re.M)
appkeys = {key(n) for n in names}
f = lambda v: 'null' if v is None else (str(int(v)) if float(v).is_integer() else str(v))
adp = ['%s:[%s,%s]' % (json.dumps(n, ensure_ascii=False), f(fpd[key(n)]['yahoo']), f(fpd[key(n)]['espn']))
       for n in names if key(n) in fpd and (fpd[key(n)]['yahoo'] is not None or fpd[key(n)]['espn'] is not None)]
oth = sorted((v for kk, v in fpd.items() if kk not in appkeys and (v['avg'] or 999) <= 170), key=lambda v: v['avg'])
s = re.sub(r'const ADP=\{.*?\};', lambda _: 'const ADP={' + ','.join(adp) + '};', s, count=1, flags=re.S)
s = re.sub(r'const ADP_OTHERS=\[.*?\];', lambda _: 'const ADP_OTHERS=[' + ','.join(
    '[%s,%s,%s]' % (json.dumps(v['name'], ensure_ascii=False), f(v['yahoo']), f(v['espn'])) for v in oth) + '];', s, count=1, flags=re.S)
open(APP, 'w', encoding='utf-8', newline='\n').write(s)
print('players', len(names), '| with ADP', len(adp), '| still off-list with ADP', len(oth), [v['name'] for v in oth])
