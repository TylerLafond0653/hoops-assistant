import json, re, unicodedata
SCR = r"C:\Users\tyler\AppData\Local\Temp\claude\C--Users-tyler-OneDrive---The-University-of-Western-Ontario-Year-4-projects\1cc0017a-8b78-4519-8820-cc081b6e1adc\scratchpad"
exec(open(SCR + r"\adp.py", encoding='utf-8').read().split("print('fantasypros rows'")[0])  # reuse the parser (fills fpd, key)

APP = r"C:\Users\tyler\OneDrive - The University of Western Ontario\Year 4\projects\fantasy-draft\draft-room.html"
app = open(APP, encoding='utf-8').read()
data = app[app.find('const DATA=['):]
data = data[:data.find('\n];')]
names = re.findall(r'^\["([^"]+)"', data, re.M)
appkeys = {key(n) for n in names}

f = lambda v: 'null' if v is None else (str(int(v)) if float(v).is_integer() else str(v))
adp = []
for n in names:
    r = fpd.get(key(n))
    if r and (r['yahoo'] is not None or r['espn'] is not None):
        adp.append('%s:[%s,%s]' % (json.dumps(n, ensure_ascii=False), f(r['yahoo']), f(r['espn'])))
others = sorted((v for k, v in fpd.items() if k not in appkeys and (v['avg'] or 999) <= 170), key=lambda v: v['avg'])
oth = ['[%s,%s,%s]' % (json.dumps(v['name'], ensure_ascii=False), f(v['yahoo']), f(v['espn'])) for v in others]

out = []
out.append("// Where other managers actually draft each player: 2026-27 ADP from FantasyPros")
out.append("// (https://www.fantasypros.com/nba/adp/overall.php), pulled 2026-09-25. [Yahoo, ESPN]; null = not ranked there.")
out.append("const ADP_ASOF='Sept 25, 2026';")
out.append("const ADP={" + ','.join(adp) + "};")
out.append("// players outside this list that other managers still draft (they use up picks): [name, Yahoo, ESPN]")
out.append("const ADP_OTHERS=[" + ','.join(oth) + "];")
open(SCR + r"\adp_block.js", 'w', encoding='utf-8').write('\n'.join(out) + '\n')
print(len(adp), 'app players with ADP;', len(oth), 'others;', sum(len(x) for x in out), 'chars')
