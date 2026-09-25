"""Build the post-back body from a page fetched by curl (hb_get.html), asking for 400 players."""
import re, html, urllib.parse
SCR = r"C:\Users\tyler\AppData\Local\Temp\claude\C--Users-tyler-OneDrive---The-University-of-Western-Ontario-Year-4-projects\1cc0017a-8b78-4519-8820-cc081b6e1adc\scratchpad"
page = open(SCR + r"\hb_get.html", encoding='utf-8', errors='replace').read()
form = {}
for m in re.finditer(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', page):
    form[html.unescape(m.group(1))] = html.unescape(m.group(2))
for m in re.finditer(r'<select name="([^"]+)"(.*?)</select>', page, re.S):
    if 'disabled="disabled"' in m.group(2).split('>')[0]: continue   # browsers don't send disabled fields
    sel = re.search(r'<option selected="selected" value="([^"]*)"', m.group(2)) or re.search(r'<option value="([^"]*)"', m.group(2))
    if sel: form[html.unescape(m.group(1))] = sel.group(1)
form['ctl00$ContentPlaceHolder1$DDSHOW'] = '400'
form['__EVENTTARGET'] = 'ctl00$ContentPlaceHolder1$DDSHOW'
open(SCR + r"\hb_body.txt", 'w', encoding='utf-8').write(urllib.parse.urlencode(form))
print('fields', len(form))
