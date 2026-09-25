SCR = r"C:\Users\tyler\AppData\Local\Temp\claude\C--Users-tyler-OneDrive---The-University-of-Western-Ontario-Year-4-projects\1cc0017a-8b78-4519-8820-cc081b6e1adc\scratchpad"
APP = r"C:\Users\tyler\OneDrive - The University of Western Ontario\Year 4\projects\fantasy-draft\draft-room.html"
raw = open(APP, 'rb').read().decode('utf-8')
crlf = '\r\n' in raw
s = raw.replace('\r\n', '\n')
assert 'const ADP=' not in s, 'already inserted'
i = s.index('const DATA=[')
j = s.index('\n];', i) + len('\n];')
block = '\n' + open(SCR + r"\adp_block.js", encoding='utf-8').read() + open(SCR + r"\news_block.js", encoding='utf-8').read().rstrip('\n')
s = s[:j] + block + s[j:]
if crlf:
    s = s.replace('\n', '\r\n')
open(APP, 'wb').write(s.encode('utf-8'))
print('inserted', len(block), 'chars; crlf =', crlf)
