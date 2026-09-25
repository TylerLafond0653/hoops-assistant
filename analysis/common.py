"""Shared loaders for the model audit and backtests.

Everything is read from the app itself (draft-room.html is the source of truth) or from the cached source
files in analysis/data. Pure Python: no numpy/pandas needed.

Stat vectors throughout are [PTS, REB, AST, STL, BLK, 3PM, FGM, FGA, FTM, FTA, TO] per game (or totals).
"""
import json, os, re, html, math, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, '..', 'draft-room.html')
DATA = os.path.join(HERE, 'data')
CATS = ['PTS', 'REB', 'AST', 'STL', 'BLK', '3PM', 'FG', 'FT', 'TO']
ESPN_TEAM = {0: 'FA', 1: 'ATL', 2: 'BOS', 3: 'NOP', 4: 'CHI', 5: 'CLE', 6: 'DAL', 7: 'DEN', 8: 'DET', 9: 'GSW', 10: 'HOU',
             11: 'IND', 12: 'LAC', 13: 'LAL', 14: 'MIA', 15: 'MIL', 16: 'MIN', 17: 'BKN', 18: 'NYK', 19: 'ORL', 20: 'PHI',
             21: 'PHX', 22: 'POR', 23: 'SAC', 24: 'SAS', 25: 'OKC', 26: 'UTA', 27: 'WAS', 28: 'TOR', 29: 'MEM', 30: 'CHA'}
SLOT_POS = {0: 'PG', 1: 'SG', 2: 'SF', 3: 'PF', 4: 'C'}


def key(s):
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = re.sub(r'\b(jr|sr|ii|iii|iv)\b\.?', '', s)
    return re.sub(r'[^a-z]', '', s)


# ---------- the app ----------
def load_app():
    app = open(APP, encoding='utf-8').read()
    i0 = app.index('const DATA=['); i1 = app.index('\n];', i0)
    rows = [json.loads(l.strip().rstrip(',')) for l in app[i0:i1].split('\n') if l.strip().startswith('["')]
    js = lambda n: json.loads(re.search(r'const %s=(\{.*?\});' % n, app).group(1))
    out = dict(rows=rows, ADP=js('ADP'), AGE=js('AGE'), EST=js('EST'), DIS=js('DISAGREE'), EXP=js('EXP'), LAST=js('LAST'),
               MKT=js('ESPN_MKT') if 'const ESPN_MKT=' in app else {})
    out['NEWS'] = {m.group(1).replace("\\'", "'"): m.group(2) for m in re.finditer(r"\['((?:[^'\\]|\\.)+)','(out|watch|ok)'", app)}
    return out


def app_players(A=None):
    A = A or load_app()
    P = []
    for i, (name, team, pos, g, mn, st, z) in enumerate(A['rows']):
        P.append(dict(id=i + 1, name=name, team=team, pos=pos.split('/'), G=g, MIN=mn, st=st, z=z, v=sum(z),
                      adp=A['ADP'].get(name), age=A['AGE'].get(name), est=A['EST'].get(name, ''),
                      dis=A['DIS'].get(name, 0), flag=A['NEWS'].get(name, '')))
    P.sort(key=lambda p: -p['v'])
    for r, p in enumerate(P): p['rank'] = r + 1
    return P


# ---------- stat line -> the app's z scale ----------
def _lstsq(X, y):
    n = len(X[0])
    A = [[sum(r[i] * r[j] for r in X) for j in range(n)] for i in range(n)]
    b = [sum(r[i] * t for r, t in zip(X, y)) for i in range(n)]
    for i in range(n):
        p = max(range(i, n), key=lambda k: abs(A[k][i])); A[i], A[p] = A[p], A[i]; b[i], b[p] = b[p], b[i]
        for k in range(i + 1, n):
            f = A[k][i] / A[i][i]; A[k] = [a - f * c for a, c in zip(A[k], A[i])]; b[k] -= f * b[i]
    x = [0] * n
    for i in reversed(range(n)): x[i] = (b[i] - sum(A[i][j] * x[j] for j in range(i + 1, n))) / A[i][i]
    return x


class ZMap:
    """Linear map from a per-game stat line to the app's 9-cat z-scores, fitted on the app's top 150
    (the same method the app used to put ESPN projections on FanScout's scale)."""
    def __init__(self, P):
        top = [p for p in P if p['rank'] <= 150]
        # app stat rows: [PTS,REB,AST,STL,BLK,3PM,FG%,FT%,TO,FGA,FTA]
        def vec(st): return [st[0], st[1], st[2], st[3], st[4], st[5], st[6] * st[9], st[9], st[7] * st[10], st[10], st[8]]
        X = [vec(p['st']) for p in top]
        self.coef = []
        for c in range(9):
            f = self.feat(c)
            self.coef.append(_lstsq([f(x) for x in X], [p['z'][c] for p in top]))
        self.fit_err = [max(abs(sum(a * b for a, b in zip(self.coef[c], self.feat(c)(vec(p['st'])))) - p['z'][c]) for p in top) for c in range(9)]

    @staticmethod
    def feat(c):
        # counting stats: z = a + b*stat. FG/FT: z = a + b*makes + c*attempts (volume-weighted impact).
        idx = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 8: 10}
        if c in idx: return lambda x, i=idx[c]: [1, x[i]]
        if c == 6: return lambda x: [1, x[6], x[7]]
        return lambda x: [1, x[8], x[9]]

    def z(self, x):
        """x = per-game [PTS,REB,AST,STL,BLK,3PM,FGM,FGA,FTM,FTA,TO]"""
        return [sum(a * b for a, b in zip(self.coef[c], self.feat(c)(x))) for c in range(9)]

    def slope(self, c):
        """z per unit of the stat (for FG/FT: per make, holding attempts; and per attempt)."""
        return self.coef[c][1:]


# ---------- ESPN feed: projections, actuals, box scores, ranks ----------
ESPN_KEYS = ['0', '6', '3', '2', '1', '17', '13', '14', '15', '16', '11']   # PTS REB AST STL BLK 3PM FGM FGA FTM FTA TO


SEASON_FILES = {2026: 'espn_feed_2026-09-25.json', 2025: 'espn_feed_season2025.json', 2024: 'espn_feed_season2024.json'}
PRIOR_BBREF = {2026: 'bbref_2024-25_per_game.html', 2025: 'bbref_2023-24_per_game.html', 2024: 'bbref_2022-23_per_game.html'}


def load_espn(path=None, season=2026):
    """season = the ESPN season id (2026 = 2025-26). 'proj'/'act' = that season's preseason projection and
    actual averages; 'games' = that season's box scores by day."""
    path = path or os.path.join(DATA, SEASON_FILES[season])
    d = json.load(open(path, encoding='utf-8'))
    out = {}
    # note: 'proTeamId' on a player is his team now; each box score carries the team he played for then
    for x in d['players']:
        pl = x['player']
        rec = dict(name=pl['fullName'], team=ESPN_TEAM.get(pl.get('proTeamId')), inj=pl.get('injuryStatus'),
                   pos=[SLOT_POS[s] for s in pl.get('eligibleSlots', []) if s in SLOT_POS],
                   roto_rank=((pl.get('draftRanksByRankType') or {}).get('ROTO') or {}).get('rank'),
                   std_rank=((pl.get('draftRanksByRankType') or {}).get('STANDARD') or {}).get('rank'),
                   espn_adp=(pl.get('ownership') or {}).get('averageDraftPosition'), games={})
        for s in pl.get('stats', []):
            sid, src, spl = s.get('seasonId'), s.get('statSourceId'), s.get('statSplitTypeId')
            if spl == 0 and s.get('averageStats'):
                a = s['averageStats']
                line = [float(a.get(k, 0) or 0) for k in ESPN_KEYS]
                g = float(a.get('42', 0) or 0)
                tag = {(2026, 1): 'proj25', (2026, 0): 'act25', (2027, 1): 'proj26'}.get((sid, src))
                if tag: rec[tag] = dict(line=line, G=g, MIN=float(a.get('40', 0) or 0))
                gen = {(season, 1): 'proj', (season, 0): 'act'}.get((sid, src))
                if gen: rec[gen] = dict(line=line, G=g, MIN=float(a.get('40', 0) or 0))
            elif spl == 5 and sid == season and src == 0 and s.get('stats'):
                t = s['stats']
                if float(t.get('40', 0) or 0) <= 0: continue          # DNP
                rec['games'][s['scoringPeriodId']] = [float(t.get(k, 0) or 0) for k in ESPN_KEYS]
                rec.setdefault('game_team', {})[s['scoringPeriodId']] = s.get('proTeamId')
        out[key(pl['fullName'])] = rec
    return out


# ---------- Basketball Reference per-game table ----------
def load_bbref(path):
    s = open(path, encoding='utf-8', errors='replace').read()
    t = s[s.find('id="per_game_stats"'):]; t = t[:t.find('</table>')]
    rows = {}
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', t, re.S):
        cells = dict(re.findall(r'data-stat="([^"]+)"[^>]*>(.*?)</t[dh]>', tr, re.S))
        name = html.unescape(re.sub(r'<[^>]+>', '', cells.get('name_display', cells.get('player', ''))).strip())
        if not name or name == 'Player' or key(name) in rows: continue
        def g(f):
            v = re.sub(r'<[^>]+>', '', cells.get(f, '')).strip()
            try: return float(v)
            except ValueError: return 0.0
        rows[key(name)] = dict(name=name, age=g('age'), G=g('games'), MP=g('mp_per_g'),
                               line=[g('pts_per_g'), g('trb_per_g'), g('ast_per_g'), g('stl_per_g'), g('blk_per_g'), g('fg3_per_g'),
                                     g('fg_per_g'), g('fga_per_g'), g('ft_per_g'), g('fta_per_g'), g('tov_per_g')])
    return rows


# ---------- the app's matchup model ----------
def ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def matchup(a, b, sd=5.0):
    """The app's matchup(): each category an independent normal with the same weekly sd."""
    sds = sd if isinstance(sd, (list, tuple)) else [sd] * 9
    mu = v = 0.0
    for q in range(9):
        pw = ncdf((a[q] - b[q]) / sds[q]); mu += pw; v += pw * (1 - pw)
    return (1 - ncdf((4.5 - mu) / math.sqrt(v))) if v > 0 else (1.0 if mu > 4.5 else 0.0), mu


SLOT_W = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.9, 0.9, 0.9, 0.7, 0.7, 0.6]
