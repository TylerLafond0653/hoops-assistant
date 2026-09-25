"""Do rookies and sophomores improve faster than other players the same age?

Rookie season = first season a player appears in our 2021-22+ data, for seasons 2022-23 onward (so a
2021-22 veteran isn't mistaken for a rookie) and age <= 23. Change is to the next season, relative to
all players (same method as the aging curve, but over every player with 20+ games, since most rookies
aren't in the draftable top 180 yet)."""
import statistics as st
exec(open(r"C:\Users\tyler\AppData\Local\Temp\claude\C--Users-tyler-OneDrive---The-University-of-Western-Ontario-Year-4-projects\1cc0017a-8b78-4519-8820-cc081b6e1adc\scratchpad\aging.py", encoding='utf-8').read().split("pairs = []")[0])
first = {}
for y in (2022, 2023, 2024, 2025, 2026):
    for k in seasons[y]: first.setdefault(k, y)
rows = []  # (age, exp, change, value)
for y in (2023, 2024, 2025):
    a, b = seasons[y], seasons[y + 1]
    for k, r in a.items():
        if k in b and r['age']:
            exp = y - first[k] if first[k] >= 2023 else None       # None = veteran / unknown
            rows.append((int(r['age']), exp, b[k]['v'] - r['v'], r['v']))
overall = st.mean(d for _, _, d, _ in rows)
def grp(f):
    g = [r for r in rows if f(r)]
    return len(g), round(st.mean(r[2] for r in g) - overall, 2) if g else None
print('overall change (removed):', round(overall, 2))
for age in range(19, 24):
    print(f'age {age}: rookie year->2nd', grp(lambda r: r[0] == age and r[1] == 0),
          '| 2nd->3rd', grp(lambda r: r[0] == age and r[1] == 1),
          '| everyone else this age', grp(lambda r: r[0] == age and r[1] not in (0, 1)))
print('ALL rookies (<=23)', grp(lambda r: r[0] <= 23 and r[1] == 0), '| ALL sophomores', grp(lambda r: r[0] <= 23 and r[1] == 1),
      '| same-age others', grp(lambda r: r[0] <= 23 and r[1] not in (0, 1)))
# rookies who already had a real role (top half of rookie values) vs the rest
rk = sorted([r for r in rows if r[1] == 0 and r[0] <= 23], key=lambda r: -r[3])
half = len(rk) // 2
print('rookies with bigger roles:', len(rk[:half]), round(st.mean(r[2] for r in rk[:half]) - overall, 2),
      '| smaller roles:', len(rk[half:]), round(st.mean(r[2] for r in rk[half:]) - overall, 2))
