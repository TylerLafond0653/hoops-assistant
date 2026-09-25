import re, html, json
SCR = r"C:\Users\tyler\AppData\Local\Temp\claude\C--Users-tyler-OneDrive---The-University-of-Western-Ontario-Year-4-projects\1cc0017a-8b78-4519-8820-cc081b6e1adc\scratchpad"
s = open(SCR + r"\hb_400.html", encoding='utf-8', errors='replace').read()
t = s[s.find('id="ContentPlaceHolder1_GridView1"'):]
t = t[:t.find('</table>')]
txt = lambda h: re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', h))).strip()
rows = re.findall(r'<tr[^>]*>(.*?)</tr>', t, re.S)
head = [txt(h) for h in re.findall(r'<th[^>]*>(.*?)</th>', rows[0], re.S)]
print('header:', head)
data = []
for r in rows[1:]:
    cells = [txt(c) for c in re.findall(r'<td[^>]*>(.*?)</td>', r, re.S)]
    if len(cells) == len(head): data.append(dict(zip(head, cells)))
print('rows', len(data))
for d in data[:3] + data[200:202]: print(d)
json.dump({'head': head, 'rows': data}, open(SCR + r"\hb_rows.json", 'w', encoding='utf-8'), ensure_ascii=False)
