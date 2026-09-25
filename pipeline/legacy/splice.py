import sys
p = 'draft-room.html'
s = open(p, encoding='utf-8').read()
new = open(sys.argv[1], encoding='utf-8').read()
a = "  // build model: which build to lean into, given your picks and everyone else's"
b = "${build}<ol class=\"picks3\">${picks}</ol>${more}${strategy}`;\n}\n"
i = s.index(a)
j = s.index(b, i) + len(b)
s = s[:i] + new + s[j:]
open(p, 'w', encoding='utf-8').write(s)
print('spliced', i, j)
