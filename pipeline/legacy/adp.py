import re, html, json, unicodedata

SCR = r"C:\Users\tyler\AppData\Local\Temp\claude\C--Users-tyler-OneDrive---The-University-of-Western-Ontario-Year-4-projects\1cc0017a-8b78-4519-8820-cc081b6e1adc\scratchpad"
APP = r"C:\Users\tyler\OneDrive - The University of Western Ontario\Year 4\projects\fantasy-draft\draft-room.html"
ABBR = {'PHO': 'PHX', 'UTH': 'UTA', 'NOR': 'NOP', 'GS': 'GSW', 'NY': 'NYK', 'SA': 'SAS', 'NO': 'NOP'}

def key(s):
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = re.sub(r'\b(jr|sr|ii|iii|iv)\b\.?', '', s)
    return re.sub(r'[^a-z]', '', s)

fp = open(SCR + r"\www_fantasypros_com_nba_adp_overall_php.html", encoding='utf-8', errors='replace').read()
body = fp[fp.find('<table'):]
body = body[:body.find('</table>')]
num = lambda x: float(x) if re.match(r'^\s*[\d.]+\s*$', x) else None
fpd = {}
# one row at a time, so an injury tag can't make the pattern run into the next player
for row in body.split('<tr>')[2:]:
    m = re.search(r'fp-player-name="([^"]+)"', row)
    if not m: continue
    name = html.unescape(m.group(1))
    tp = re.search(r'<small>\(([^)]*)\)</small>', row)
    team = tp.group(1).split(' - ')[0] if tp else ''
    team = ABBR.get(team, team)
    inj = re.search(r'<small[^>]*title="([^"]*)"[^>]*>([A-Z-]+)</small>', row)
    cells = re.findall(r'<td>([^<]*)</td>', row)
    rank, yh, es, avg = (cells + [None] * 4)[:4]
    fpd[key(name)] = dict(name=name, rank=int(rank), team=team, yahoo=num(yh or ''), espn=num(es or ''), avg=num(avg or ''),
                          status=inj.group(2) if inj else '', injury=inj.group(1).lstrip(': ').strip() if inj else '')
print('fantasypros rows', len(fpd))

app = open(APP, encoding='utf-8').read()
data = app[app.find('const DATA=['):]
data = data[:data.find('\n];')]
players = re.findall(r'^\["([^"]+)", "([^"]+)"', data, re.M)
out, missing, teamdiff = {}, [], []
for name, team in players:
    r = fpd.get(key(name))
    if not r:
        missing.append(name); continue
    out[name] = r
    if r['team'] != team:
        teamdiff.append((name, 'app ' + team, 'fp ' + r['team']))
print('matched', len(out), 'of', len(players))
print('missing', missing)
print('team differs:', teamdiff)
print('injury tags:', [(n, r['status'], r['injury'], r['avg']) for n, r in out.items() if r['status']])
json.dump(out, open(SCR + r"\adp_fp.json", 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
appkeys = {key(n) for n, _ in players}
extra = sorted((v['avg'] or 999, v['name'], v['team'], v['status']) for k, v in fpd.items() if k not in appkeys and (v['avg'] or 999) <= 150)
print('ADP top 150 but not in app:', extra)
