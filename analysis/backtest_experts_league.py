"""2025-26 draft backtest in a league of experienced drafters: the other nine teams draft off the real preseason
expert consensus (Oct 18, 2025), and each strategy for your pick uses that consensus as its market.
Compares projection-only value, projection met halfway with the experts (the app's approach), following the
experts, the don't-reach rule and whole-team picking. Week-bootstrap intervals as in backtest_robustness.py.
Run: BT_SEASON=2026 python analysis/backtest_experts_league.py [drafts=150]"""
import os, sys
os.environ.setdefault('BT_SEASON', '2026')
import backtest_2025 as B
from backtest_robustness import run, compare
ND = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 150
B.set_market('experts')
SIG = B.fit_sigma([w for i, w in enumerate(B.WEEKS) if i % 2 == 0])
names = ['ADP', 'VALUE_G', 'VALUE_GM', 'WAIT', 'TEAM_5']
labels = {'ADP': 'follow the experts', 'VALUE_G': 'projection only', 'VALUE_GM': 'projection + experts (app)',
          'WAIT': 'app + don\'t-reach rule', 'TEAM_5': 'app + whole-team picks'}
strats = [(n, B.make_strategy(n, SIG)) for n in names]
for slot in (4, 0, 9):
    res = run(strats, 'experts', ND if slot == 4 else ND // 2, slot)
    print(f"\n== league drafting off the expert consensus, you pick {slot + 1} ==")
    for n in names: print(f"   {labels[n]:28s} weekly win {sum(res[n]) / len(res[n]):.1%}")
    for a, b in (('VALUE_GM', 'VALUE_G'), ('VALUE_GM', 'ADP'), ('WAIT', 'VALUE_GM'), ('TEAM_5', 'VALUE_GM')):
        m, lo, hi = compare(res, a, b)
        print(f"   {labels[a]:28s} vs {labels[b]:28s} {m:+.1%} ({lo:+.1%} to {hi:+.1%}){'  <- clear' if lo > 0 or hi < 0 else ''}")
