"""Save your ESPN cookies into inseason/secrets.local.json (never uploaded: .gitignore skips it).

Run:  python inseason/save_cookies.py
Then paste each value when asked (nothing shows while you paste; that's on purpose) and press Enter.
Where to find them: Chrome, logged in to ESPN Fantasy > F12 > Application > Cookies > https://fantasy.espn.com
  espn_s2  a long string of letters, numbers and % signs
  SWID     looks like {1A2B3C4D-....}, braces included
"""
import getpass, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, 'secrets.local.json')

s2 = getpass.getpass('Paste espn_s2, then Enter: ').strip().strip('"')
swid = getpass.getpass('Paste SWID, then Enter: ').strip().strip('"')
problems = []
if len(s2) < 100: problems.append(f'espn_s2 looks too short ({len(s2)} characters; it is usually 200-400)')
if not (swid.startswith('{') and swid.endswith('}') and len(swid) == 38):
    problems.append('SWID should look like {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}, braces included')
if problems:
    print('Not saved:\n  ' + '\n  '.join(problems) + '\nCopy the values again and rerun.')
    raise SystemExit(1)
data = json.load(open(PATH, encoding='utf-8')) if os.path.exists(PATH) else {}
data.update(ESPN_S2=s2, ESPN_SWID=swid)
json.dump(data, open(PATH, 'w', encoding='utf-8'), indent=2)
print(f'Saved (espn_s2: {len(s2)} characters, SWID: {swid[:3]}...{swid[-2:]}). Now tell Claude "cookies saved".')
