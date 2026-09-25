import re
SCR = r"C:\Users\tyler\AppData\Local\Temp\claude\C--Users-tyler-OneDrive---The-University-of-Western-Ontario-Year-4-projects\1cc0017a-8b78-4519-8820-cc081b6e1adc\scratchpad"
s = open(SCR + r"\fs_rookie-projections.html", encoding='utf-8', errors='replace').read()
s = s.replace('\\\\"', '"').replace('\\"', '"')
starts = [m.start() for m in re.finditer(r'\{"gamesPlayed":', s)]
print('starts', len(starts))
a = starts[0]
rec_s = s[a:a + 1500]
print(ascii(rec_s[:900]))
pj = re.search(r'"projections":\{(.*?)\}', rec_s)
print('pj', bool(pj), ascii(pj.group(1)[:200]) if pj else '')
