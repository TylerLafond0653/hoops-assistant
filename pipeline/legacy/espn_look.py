import json
SCR = r"C:\Users\tyler\AppData\Local\Temp\claude\C--Users-tyler-OneDrive---The-University-of-Western-Ontario-Year-4-projects\1cc0017a-8b78-4519-8820-cc081b6e1adc\scratchpad"
d = json.load(open(SCR + r"\espn_proj.json", encoding='utf-8'))
ps = d['players']
print('players', len(ps))
for want in ('Victor Wembanyama', 'Walker Kessler'):
    p = next(x for x in ps if x['player']['fullName'] == want)
    print(want, 'proTeamId', p['player'].get('proTeamId'), 'injury', p['player'].get('injuryStatus'))
    for s in p['player'].get('stats', []):
        print('  season', s.get('seasonId'), 'source', s.get('statSourceId'), 'split', s.get('statSplitTypeId'), 'id', s.get('id'),
              'avg keys', sorted((s.get('averageStats') or {}).keys(), key=int)[:30])
    proj = [s for s in p['player']['stats'] if s.get('seasonId') == 2027 and s.get('statSourceId') == 1 and s.get('statSplitTypeId') == 0]
    if proj: print('  projected averages:', {k: round(v, 3) for k, v in proj[0]['averageStats'].items()})
