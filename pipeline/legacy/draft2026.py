import re, html, json
SCR = r"C:\Users\tyler\AppData\Local\Temp\claude\C--Users-tyler-OneDrive---The-University-of-Western-Ontario-Year-4-projects\1cc0017a-8b78-4519-8820-cc081b6e1adc\scratchpad"
s = open(SCR + r"\en_wikipedia_org_wiki_2026_NBA_draft.html", encoding='utf-8').read()
txt = lambda h: re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', h))).strip()
out = []
for tb in re.findall(r'<table class="[^"]*wikitable[^"]*".*?</table>', s, re.S):
    head = [txt(h) for h in re.findall(r'<th[^>]*>(.*?)</th>', tb.split('</tr>')[0], re.S)]
    if not any('Player' in h for h in head): continue
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', tb, re.S)[1:]:
        cells = [txt(c) for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S)]
        if len(cells) >= 5: out.append(cells)
    print('table head:', head)
print(len(out))
for r in out[:12]: print(r)
json.dump(out, open(SCR + r"\draft2026_rows.json", 'w', encoding='utf-8'), ensure_ascii=False)
