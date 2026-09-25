"""After the draft: which ranking did your leaguemates actually follow, and how loosely?

Reads the CSV from the app's Draft log -> Export button. For every pick your leaguemates made (keepers and
your own picks are skipped), it asks how likely that pick was under each ranking: each available player is
chosen with probability proportional to exp(-rank / tau), with tau (the looseness) fitted per ranking.
The ranking with the highest likelihood is the one your league drafts from; the best mix of ESPN's ADP and
ESPN's category rank gives TUNE.catRank; tau gives a scatter to compare with the app's 1.5 + 0.12 x ADP.

Run: python analysis/fit_opponent_model.py draft-log-2026-10-01.csv [--me Tyler]
"""
import csv, math, sys
from common import load_app, app_players

def main():
    path = sys.argv[1]
    me = sys.argv[sys.argv.index('--me') + 1] if '--me' in sys.argv else 'Tyler'
    A = load_app(); P = app_players(A); MKT = A['MKT']
    picks = list(csv.DictReader(open(path, encoding='utf-8')))
    by_name = {p['name']: p for p in P}
    BIG = 250.0
    def espn_adp(p): m = MKT.get(p['name']); return m[0] if m and m[0] is not None else None
    def espn_cat(p): m = MKT.get(p['name']); return m[1] if m and m[1] is not None else None
    def mix(w):
        def f(p):
            a, c = espn_adp(p), espn_cat(p)
            if a is not None and c is not None: return w * c + (1 - w) * a
            return c if c is not None else a
        return f
    rankers = {
        'ESPN live ADP': espn_adp,
        'ESPN category rank': espn_cat,
        'Yahoo ADP (FantasyPros)': lambda p: p['adp'][0] if p['adp'] else None,
        'ESPN ADP (FantasyPros)': lambda p: p['adp'][1] if p['adp'] else None,
        "app's projection rank": lambda p: p['rank'],
    }
    for w in (0.25, 0.5, 0.75): rankers[f'ESPN mix (category rank weight {w})'] = mix(w)

    taken = set(); events = []
    for row in picks:
        name = row['player']
        if row['kept'] == '1' or row['manager'] == me or name not in by_name:
            taken.add(name); continue
        events.append((name, [p for p in P if p['name'] not in taken]))
        taken.add(name)
    print(f"{len(events)} leaguemate picks scored (your picks, keepers and unknown players skipped)\n")

    results = []
    for label, f in rankers.items():
        def ll(tau):
            t = 0.0
            for name, av in events:
                xs = [(f(p) if f(p) is not None else BIG) for p in av]
                lo = min(xs); z = sum(math.exp(-(x - lo) / tau) for x in xs)
                x = f(by_name[name]); x = x if x is not None else BIG
                t += -(x - lo) / tau - math.log(z)
            return t
        best = max(((ll(tau), tau) for tau in (1, 2, 3, 4, 5, 6, 8, 10, 13, 16, 20, 25, 32, 40)), key=lambda r: r[0])
        top3 = sum(1 for name, av in events if sorted((f(p) if f(p) is not None else BIG, p['name']) for p in av).index(
            (f(by_name[name]) if f(by_name[name]) is not None else BIG, name)) < 3) / max(1, len(events))
        results.append((best[0], label, best[1], top3))
    results.sort(reverse=True)
    print(f"{'ranking':40s} {'log-likelihood':>15s} {'looseness':>10s} {'pick was top-3 left':>20s}")
    for llv, label, tau, top3 in results:
        print(f"{label:40s} {llv:15.1f} {tau:10.0f} {top3:20.0%}")
    print(f"\nBest fit: {results[0][1]}. Set TUNE.catRank from the best ESPN mix, and compare the looseness with the"
          " app's scatter (about 3 picks at ADP 15, 8 at ADP 50, 14 at ADP 100).")

if __name__ == '__main__':
    main()
