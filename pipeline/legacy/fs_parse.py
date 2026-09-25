"""Pull player projection records out of FanScout's Next.js pages. The data is JSON inside the HTML;
each player is one object starting with {"gamesPlayed":..., so split on that and read fields from
that record only (never a neighbour's)."""
import re, json, sys
SCR = r"C:\Users\tyler\AppData\Local\Temp\claude\C--Users-tyler-OneDrive---The-University-of-Western-Ontario-Year-4-projects\1cc0017a-8b78-4519-8820-cc081b6e1adc\scratchpad"

def records(path):
    s = open(path, encoding='utf-8', errors='replace').read()
    s = s.replace('\\\\"', '"').replace('\\"', '"')
    # the projections block inside each player also starts with {"gamesPlayed":, so require playerId
    starts = [m.start() for m in re.finditer(r'\{"gamesPlayed":[\d.]+,"playerId"', s)]
    out = {}
    for a, b in zip(starts, starts[1:] + [len(s)]):
        rec_s = s[a:min(b, a + 6000)]
        nm = re.search(r'"playerName":"([^"]+)"', rec_s)
        if not nm: continue
        rec = {'name': nm.group(1)}
        for fld in ('gamesPlayed', 'playerId', 'team', 'exp', 'position', 'positions', 'age', 'birthDate', 'draftPick', 'draftYear'):
            mm = re.search(r'"%s":"?([^",}\]]*)' % fld, rec_s)
            if mm: rec[fld] = mm.group(1)
        pj = re.search(r'"projections":\{(.*?)\}', rec_s)
        if pj:
            for k, v in re.findall(r'"(\w+)":(-?[\d.eE+-]+)', pj.group(1)):
                rec['p_' + k] = float(v)
        if 'p_pts' in rec and (rec['name'] not in out or len(rec) > len(out[rec['name']])):
            out[rec['name']] = rec
    return out

if __name__ == '__main__':
    allr = {}
    for f in sys.argv[1:]:
        r = records(SCR + '\\' + f)
        print(f, 'players', len(r))
        for k, v in r.items(): allr.setdefault(k, dict(v, src=f))
    print('distinct players', len(allr))
    one = allr.get('AJ Dybantsa') or next(iter(allr.values()))
    print('fields:', sorted(one.keys()))
    for n in ('AJ Dybantsa', 'Walker Kessler', 'Tre Johnson', 'Mikel Brown Jr.'):
        if n in allr: print(n, {k: allr[n][k] for k in allr[n] if not k.startswith('p_z')})
    json.dump(allr, open(SCR + r"\fs_all.json", 'w', encoding='utf-8'), ensure_ascii=False)
