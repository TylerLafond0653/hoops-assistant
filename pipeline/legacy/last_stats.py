"""2025-26 actual per-game stats for every player in the app: ESPN's feed (season 2026, actual, full
season), falling back to Basketball Reference's 2025-26 per-game table. Cross-checks the two sources.
Writes last_block.js: const LAST={name:[G,MIN,PTS,REB,AST,STL,BLK,3PM,FG%,FT%,TO],...}"""
import json, re, sys
sys.path.insert(0, r"C:\Users\tyler\AppData\Local\Temp\claude\C--Users-tyler-OneDrive---The-University-of-Western-Ontario-Year-4-projects\1cc0017a-8b78-4519-8820-cc081b6e1adc\scratchpad")
from aging import parse, key, SCR
APP = r"C:\Users\tyler\OneDrive - The University of Western Ontario\Year 4\projects\fantasy-draft\draft-room.html"
app = open(APP, encoding='utf-8').read()
i0 = app.index('const DATA=['); i1 = app.index('\n];', i0)
rows = [json.loads(l.strip().rstrip(',')) for l in app[i0:i1].split('\n') if l.strip().startswith('["')]
EXP = json.loads(re.search(r'const EXP=(\{.*?\});', app).group(1))

d = json.load(open(SCR + r"\espn_now.json", encoding='utf-8'))
espn = {}
for p in d['players']:
    pl = p['player']
    a = [s for s in pl.get('stats', []) if s.get('seasonId') == 2026 and s.get('statSourceId') == 0 and s.get('statSplitTypeId') == 0 and s.get('averageStats')]
    if not a: continue
    s = a[0]['averageStats']; g = lambda k: float(s.get(k, 0) or 0)
    if g('42') <= 0: continue
    espn[key(pl['fullName'])] = [int(g('42')), round(g('40')), round(g('0'), 1), round(g('6'), 1), round(g('3'), 1), round(g('2'), 1), round(g('1'), 1),
                                 round(g('17'), 1), round(g('13') / g('14'), 3) if g('14') else None, round(g('15') / g('16'), 3) if g('16') else None, round(g('11'), 1)]
bb = parse(2026)
def bbrow(r):
    f = lambda a, b: round(r[a] / r[b], 3) if r.get(a) is not None and r.get(b) else None
    return [int(r['G']), round(r['MP'] or 0), r['PTS'], r['TRB'], r['AST'], r['STL'], r['BLK'], r['TP'], f('FG', 'FGA'), f('FT', 'FTA'), r['TOV']]

LAST, src, gaps, checks = {}, {'espn': 0, 'bbref': 0}, [], []
for r in rows:
    k = key(r[0])
    if k in espn:
        LAST[r[0]] = espn[k]; src['espn'] += 1
        if k in bb and bb[k]['G']:
            b = bbrow(bb[k]); checks.append((r[0], abs(espn[k][2] - b[2]), abs(espn[k][0] - b[0])))
    elif k in bb and bb[k]['G']:
        LAST[r[0]] = bbrow(bb[k]); src['bbref'] += 1
    else:
        gaps.append((r[0], 'rookie' if EXP.get(r[0]) == 0 else 'no 2025-26 NBA games'))
print('sources', src, '| none', len(gaps))
print('no stats:', gaps)
big = sorted(checks, key=lambda x: -x[1])[:6]
print('ESPN vs BBRef cross-check on', len(checks), 'players: points gap median', sorted(c[1] for c in checks)[len(checks) // 2], 'worst', big)
print('games gap worst', sorted(checks, key=lambda x: -x[2])[:5])
for n in ('Cade Cunningham', 'Anthony Edwards', 'Victor Wembanyama'): print(n, LAST.get(n))
open(SCR + r"\last_block.js", 'w', encoding='utf-8').write(
    "// Last season's actual per-game stats (2025-26), for the board's \"Last season\" view: ESPN's stats feed, pulled\n"
    "// Sept 25, 2026, with Basketball Reference's 2025-26 per-game table for players ESPN doesn't list.\n"
    "// [games, minutes, PTS, REB, AST, STL, BLK, 3PM, FG%, FT%, TO]. Rookies and players who didn't play have none.\n"
    "const LAST=" + json.dumps(LAST, ensure_ascii=False, separators=(',', ':')) + ";\n")
