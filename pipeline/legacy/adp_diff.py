import re, html
SCR = r"C:\Users\tyler\AppData\Local\Temp\claude\C--Users-tyler-OneDrive---The-University-of-Western-Ontario-Year-4-projects\1cc0017a-8b78-4519-8820-cc081b6e1adc\scratchpad"

def parse(fn):
    s = open(SCR + '\\' + fn, encoding='utf-8', errors='replace').read()
    body = s[s.find('<table'):]; body = body[:body.find('</table>')]
    out = {}
    for row in body.split('<tr>')[2:]:
        m = re.search(r'fp-player-name="([^"]+)"', row)
        if not m: continue
        cells = re.findall(r'<td>([^<]*)</td>', row)
        out[html.unescape(m.group(1))] = tuple(c.strip() for c in cells[1:4])  # yahoo, espn, avg
    return out

old, new = parse('fp_old.html'), parse('fp_new.html')
print('players old', len(old), 'new', len(new))
changed = [(n, old[n], new[n]) for n in new if n in old and old[n] != new[n]]
print('changed values:', len(changed))
for c in changed[:15]: print(' ', c)
print('added:', [n for n in new if n not in old][:10], '| removed:', [n for n in old if n not in new][:10])
