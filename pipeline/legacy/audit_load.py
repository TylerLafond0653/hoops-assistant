"""Load the app's data blocks (the source of truth) for the audit."""
import json, re
APP = r"C:\Users\tyler\OneDrive - The University of Western Ontario\Year 4\projects\fantasy-draft\draft-room.html"
SCR = r"C:\Users\tyler\AppData\Local\Temp\claude\C--Users-tyler-OneDrive---The-University-of-Western-Ontario-Year-4-projects\1cc0017a-8b78-4519-8820-cc081b6e1adc\scratchpad"
CATS = ['PTS', 'REB', 'AST', 'STL', 'BLK', '3PM', 'FG', 'FT', 'TO']
app = open(APP, encoding='utf-8').read()
i0 = app.index('const DATA=['); i1 = app.index('\n];', i0)
ROWS = [json.loads(l.strip().rstrip(',')) for l in app[i0:i1].split('\n') if l.strip().startswith('["')]
def js(name):
    return json.loads(re.search(r'const %s=(\{.*?\});' % name, app).group(1))
ADP, AGE, EST, DIS, EXP, LAST, AGE_STEP = (js(n) for n in ('ADP', 'AGE', 'EST', 'DISAGREE', 'EXP', 'LAST', 'AGE_STEP'))
NEWS = {m.group(1).replace("\\'", "'"): m.group(2) for m in re.finditer(r"\['((?:[^'\\]|\\.)+)','(out|watch|ok)'", app)}
P = []
for i, (name, team, pos, g, mn, st, z) in enumerate(ROWS):
    P.append(dict(id=i + 1, name=name, team=team, pos=pos.split('/'), G=g, MIN=mn, st=st, z=z, v=sum(z),
                  adp=ADP.get(name), age=AGE.get(name), est=EST.get(name, ''), dis=DIS.get(name, 0), flag=NEWS.get(name, '')))
P.sort(key=lambda p: -p['v'])
for r, p in enumerate(P): p['rank'] = r + 1
