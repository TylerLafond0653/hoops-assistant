"""One-time (Sept 29, 2026): bring the app's explanations and comments in line with the expert-consensus model."""
import os
APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'draft-room.html')
s = open(APP, encoding='utf-8').read()
def rep(a, b):
    global s
    n = s.count(a); assert n == 1, (n, a[:90]); s = s.replace(a, b)

# board source note: accurate sources, with dates that follow the data
i = s.index('<p class="src">Projections from'); j = s.index('</p>', i) + 4
s = s[:i] + ('<p class="src">Projections: <a href="https://fanscout.pro/projections" target="_blank" rel="noopener">FanScout</a> '
             '(updated <span id="asof"></span>), ESPN\'s and <a href="https://www.fantasypros.com/nba/projections/overall.php" target="_blank" rel="noopener">FantasyPros\'</a> '
             'consensus projections for 2026-27, averaged (FanScout\'s rookie and young-player projections tagged Rookie / Young; '
             'other veterans estimated from their 2025-26 stats, tagged Estimate). "Experts" is <a href="https://www.fantasypros.com/nba/rankings/overall.php" target="_blank" rel="noopener">FantasyPros\'</a> '
             'consensus of category-league experts (<span id="expAsof"></span>). ADP is where ESPN managers take him: ESPN\'s live ADP averaged with '
             'ESPN\'s category-league rank (ESPN data <span id="mktAsof"></span>); Yahoo ADP from FantasyPros. Teams and injury notes checked against '
             'ESPN\'s injury report (<span id="newsAsof"></span>). "Last season" shows 2025-26 actual stats. Value is his 9-cat worth this season: '
             'per-game projections times the games he\'s expected to play (a waiver player fills the rest), met halfway with the expert consensus, '
             'adjusted for age 31+. Hover it for his per-game value.</p>') + s[j:]
rep("""  $("#asof").textContent=DATA_ASOF;""", """  $("#asof").textContent=DATA_ASOF;$('#expAsof').textContent=EXPERTS_ASOF;$('#mktAsof').textContent=ESPN_MKT_ASOF;$('#newsAsof').textContent=NEWS_ASOF;""")

# plan box explanation
rep("""The other managers take players by where they usually go on ${esc(SITES[S.site]||SITES.avg)} (their ADP), with realistic randomness, and you draft for each plan from your real picks. Every finished team then plays the other nine week by week. The % is how many weekly matchups each plan won. It counts injuries (a waiver pickup fills missed games) and meets the market halfway when FanScout and ADP disagree about a player.""",
    """Each other manager drafts off the expert consensus or ${esc(SITES[S.site]||SITES.avg)}'s list (the mix is your "Your leaguemates" setting), with realistic randomness, and you draft for each plan from your real picks. Every finished team then plays the other nine week by week. The % is how many weekly matchups each plan won. It counts injuries (a waiver pickup fills missed games) and meets the expert consensus halfway when it disagrees with the projections.""")

# settings
rep("""<option value="adp">Typical: they follow the site's rankings</option>""", """<option value="adp">Typical: they draft off the rankings (experts and ESPN, per "Your leaguemates")</option>""")
rep("""<p>The built-in list is a 9-category ranking from summer 2026.""", """<p>The built-in list ranks players by this season's projected 9-category value (see the note above the board).""")

# first-timer guide
rep("""      <li><b>ADP</b> is where other managers usually draft him. If his ADP is well after your next pick, you can usually wait on him.</li>""",
    """      <li><b>ADP</b> is where ESPN managers usually draft him; <b>Experts</b> is where category-league experts rank him. Experienced leaguemates follow the experts, so a player the experts rank well ahead of his ADP goes sooner than his ADP suggests. The "% still there" odds account for both.</li>""")
rep("""title="FanScout and ESPN disagree about him by ${p.dis.toFixed(1)} value points. The app uses their average and treats him as riskier.">""",
    """title="FanScout and ESPN disagree about him by ${p.dis.toFixed(1)} value points. The app averages its projection sources and treats him as riskier.">""")

# code comments
rep("""// Projections are blended (Sept 25, 2026): FanScout 50% + ESPN's 2026-27 projections 50% (ESPN 60% for""",
    """// Projections were blended (Sept 25, 2026; FantasyPros' consensus added Sept 29, see the note below): FanScout 50% + ESPN's 2026-27 projections 50% (ESPN 60% for""")
rep("""// Sept 25, 2026, with Basketball Reference's 2025-26 per-game table for players ESPN doesn't list.""",
    """// by pipeline/refresh_espn.py, with Basketball Reference's 2025-26 per-game table for players ESPN doesn't list.""")
rep("""// FanScout and the market (ADP) disagree about some players. The simulator keeps FanScout's category
// shape but meets the market halfway on overall value, so a plan only wins if it holds up even when
// FanScout is partly wrong. Otherwise it would grade its own homework and call every plan a lock.""",
    """// The projections and the market (the expert consensus: marketRank) disagree about some players. Values keep the
// projections' category shape but meet the market halfway on overall value. Last season that blend predicted real
// value better than either alone (analysis/backtest_sources.py), and it keeps the app from grading its own homework.""")
rep("""    // typical: they draft off their site's rankings (ADP), with the same scatter the simulator uses""",
    """    // typical: they draft off the leaguemates' list (oppRank: experts and ESPN), with the same scatter the simulator uses""")
open(APP, 'w', encoding='utf-8', newline='\n').write(s)
print('texts updated')
