import re, html, urllib.request, urllib.parse, http.cookiejar
SCR = r"C:\Users\tyler\AppData\Local\Temp\claude\C--Users-tyler-OneDrive---The-University-of-Western-Ontario-Year-4-projects\1cc0017a-8b78-4519-8820-cc081b6e1adc\scratchpad"
URL = "https://hashtagbasketball.com/fantasy-basketball-projections"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"}
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
page = op.open(urllib.request.Request(URL, headers=UA), timeout=40).read().decode('utf-8', 'replace')
form = {}
for m in re.finditer(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', page):
    form[html.unescape(m.group(1))] = html.unescape(m.group(2))
for m in re.finditer(r'<select name="([^"]+)"(.*?)</select>', page, re.S):
    sel = re.search(r'<option selected="selected" value="([^"]*)"', m.group(2))
    if sel: form[html.unescape(m.group(1))] = sel.group(1)
form['ctl00$ContentPlaceHolder1$DDSHOW'] = '400'
form['__EVENTTARGET'] = 'ctl00$ContentPlaceHolder1$DDSHOW'
data = urllib.parse.urlencode(form).encode()
res = op.open(urllib.request.Request(URL, data=data, headers=dict(UA, **{'Content-Type': 'application/x-www-form-urlencoded', 'Referer': URL})), timeout=60).read().decode('utf-8', 'replace')
open(SCR + r"\hb_400.html", 'w', encoding='utf-8').write(res)
rows = re.findall(r'<tr[^>]*>.*?</tr>', res[res.find('GridView1'):], re.S)
print('bytes', len(res), 'table rows', len(rows))
