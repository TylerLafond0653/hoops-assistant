"""One-time patch (Sept 29, 2026): the expert consensus becomes the market for player value and the main input for
predicting experienced leaguemates. Evidence: analysis/backtest_sources.py and analysis/backtest_experts_league.py.
Every edit must match exactly once, so this can't be re-run on a patched file."""
import os
APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'draft-room.html')
s = open(APP, encoding='utf-8').read()
def rep(a, b):
    global s
    n = s.count(a); assert n == 1, (n, a[:90]); s = s.replace(a, b)

# players carry their expert-consensus rank [rank, best, worst]
rep("""      adp:ADP[name]||null,mkt:ESPN_MKT[name]||null,""", """      adp:ADP[name]||null,mkt:ESPN_MKT[name]||null,exp:EXPERTS[name]||null,""")
rep("""    return {id:i+1,rank:i+1,pgRank:i+1,importedRank:i+1,mkt:k?k.mkt:null,""", """    return {id:i+1,rank:i+1,pgRank:i+1,importedRank:i+1,mkt:k?k.mkt:null,exp:k?k.exp:null,""")

# market and opponent ranks
rep("""const hasAdp=p=>!!(p.adp||p.mkt);""", """const hasAdp=p=>!!(p.adp||p.mkt);
// FantasyPros' expert consensus for roto/category leagues (Yahoo's analysts, Razzball, FantasyPros and others;
// refreshed by pipeline/refresh_fantasypros.py). Last season it predicted real 9-cat value about as well as ESPN's
// projections, and blending it with the projections beat both (analysis/backtest_sources.py).
const expertRank=p=>p.exp?p.exp[0]:null;
const noRank=p=>p.stats?Math.max(150,(p.pgRank||p.rank)+10):p.rank;
// The market view of a player's worth, which the projections are met halfway with (TUNE.market): the expert
// consensus first, then Yahoo ADP (category leagues), then ESPN. In a league drafting off the experts, this
// won 4-7 points more of weekly matchups than projections alone (analysis/backtest_experts_league.py).
function marketRank(p){
  if(p.importedRank!=null)return p.importedRank;
  const e=expertRank(p);if(e!=null)return e;
  const ya=p.adp?p.adp[0]:null;if(ya!=null)return ya;
  const es=espnAnchor(p);return es!=null?es:noRank(p);
}
// Who your leaguemates take: experienced category drafters read the expert consensus, and ESPN's draft room shows
// ESPN's list, so it's a mix. Weight on the experts by the "Your leaguemates" setting. In a test league drafting
// off the experts, an ESPN-only model said Chet Holmgren, Austin Reaves and Trae Young were 99-100% sure to last
// from 2.06 to 3.06; all three were gone. Check the mix after the draft with analysis/fit_opponent_model.py.
const OPP_EXPERT={casual:0,mixed:0.5,sharp:0.75};
function oppRank(p){
  if(p.importedRank!=null)return p.importedRank;
  const w=OPP_EXPERT[S.savvy]!=null?OPP_EXPERT[S.savvy]:OPP_EXPERT.sharp;
  const e=expertRank(p),es=siteAdp(p);
  if(e!=null&&es!=null)return w*e+(1-w)*es;
  if(es!=null)return es;
  return e!=null?e:noRank(p);
}""")
rep("""  ESPN_OTHERS.forEach(([name,adp,cat])=>{const k=normName(name),o=m.get(k)||{name,adp:null};o.mkt=[adp,cat];m.set(k,o)});
  return [...m.entries()].map(([key,o],i)=>({id:-(i+1),name:o.name,key,adp:o.adp,mkt:o.mkt,phantom:true,pos:[],rank:999}));""",
"""  ESPN_OTHERS.forEach(([name,adp,cat])=>{const k=normName(name),o=m.get(k)||{name,adp:null};o.mkt=[adp,cat];m.set(k,o)});
  EXPERTS_OTHERS.forEach(([name,r])=>{const k=normName(name),o=m.get(k)||{name,adp:null,mkt:null};o.exp=[r,r,r];m.set(k,o)});
  return [...m.entries()].map(([key,o],i)=>({id:-(i+1),name:o.name,key,adp:o.adp,mkt:o.mkt,exp:o.exp||null,phantom:true,pos:[],rank:999}));""")
rep("""  const all=[...av,...phantomsLeft()].map(p=>({p,a:adpOf(p)})).sort((x,y)=>x.a-y.a);""",
    """  const all=[...av,...phantomsLeft()].map(p=>({p,a:oppRank(p)})).sort((x,y)=>x.a-y.a);""")
rep("""const adpRound=p=>roundAt(Math.round(adpOf(p)));""", """const adpRound=p=>roundAt(Math.round(oppRank(p)));""")
rep("""  const shift=TUNE.market*(valueAtPick(adpOf(p))-own.reduce((s,v)=>s+v,0))/CATS.length;""",
    """  const shift=TUNE.market*(valueAtPick(marketRank(p))-own.reduce((s,v)=>s+v,0))/CATS.length;""")
rep("""  const ck=[S.site,players().length,S.custom?1:0,TUNE.market,TUNE.catRank,TUNE.ageNow].join('|');""",
    """  const ck=[S.site,players().length,S.custom?1:0,TUNE.market,TUNE.catRank,TUNE.ageNow,EXPERTS_ASOF].join('|');""")

# simulator: other managers draft by the opponent rank (the old blend toward the app's own rank is gone)
rep("""// How sharp your leaguemates are, for the plan simulations: 0 = they draft straight off ESPN's rankings,
// higher = their picks lean toward the projections too.
const SAVVY={casual:0,mixed:0.3,sharp:0.6};""", """// How sharp your leaguemates are: the share of their ranking that comes from the expert consensus (oppRank).
const SAVVY=OPP_EXPERT;""")
rep("""  const keepIds=new Set([...[...avAll].sort((a,b)=>adpOf(a)-adpOf(b)).slice(0,room),""",
    """  const keepIds=new Set([...[...avAll].sort((a,b)=>oppRank(a)-oppRank(b)).slice(0,room),""")
rep("""  const E=pool.map(effZ),A=pool.map(adpOf);""", """  const E=pool.map(effZ),A=pool.map(oppRank);""")
rep("""  // how the other managers rank players: ESPN's list, pulled toward projections the sharper they are
  const kap=SAVVY[S.savvy]!=null?SAVVY[S.savvy]:SAVVY.mixed;
  const A2=pool.map((x,i)=>x.phantom?A[i]:(1-kap)*A[i]+kap*x.rank);""",
    """  // how the other managers rank players: the expert consensus and ESPN's list, mixed by the leaguemates setting
  const A2=A;""")
rep("""    else{let bs=Infinity;av.forEach(x=>{const a=adpOf(x),s=a+gauss(Math.random)*adpSd(a);if(s<bs){bs=s;best=x}})}""",
    """    else{let bs=Infinity;av.forEach(x=>{const a=oppRank(x),s=a+gauss(Math.random)*adpSd(a);if(s<bs){bs=s;best=x}})}""")
rep("""    const a=hasAdp(pl)||pl.importedRank!=null?adpOf(pl):null,no=p+1;""", """    const a=hasAdp(pl)||pl.exp||pl.importedRank!=null?oppRank(pl):null,no=p+1;""")

# settings: leaguemates, default Sharp for this league (switched over once)
rep("""        <p>How sharp the other managers are. The app's plan simulations assume they draft this way. Casual managers take players straight off ESPN's rankings; sharper ones also follow projections, so undervalued players go sooner.</p>
        <select class="inp" id="savvy" aria-label="How sharp your leaguemates are"><option value="mixed">Mixed: mostly ESPN's rankings, some research (default)</option><option value="casual">Casual: straight off ESPN's rankings</option><option value="sharp">Sharp: they follow projections too</option></select>""",
    """        <p>How the other managers pick. It decides who's likely still there at your picks ("% still there" and the simulations). Casual managers take players straight off ESPN's list; experienced category-league drafters follow the expert consensus (FantasyPros, Yahoo's analysts), so players ESPN underrates go much sooner.</p>
        <select class="inp" id="savvy" aria-label="How sharp your leaguemates are"><option value="sharp">Sharp: mostly the expert consensus, some ESPN (your league)</option><option value="mixed">Mixed: half the expert consensus, half ESPN</option><option value="casual">Casual: straight off ESPN's list</option></select>""")
rep("""$('#savvy').addEventListener('change',e=>{S.savvy=SAVVY[e.target.value]!=null?e.target.value:'mixed';save();render()});""",
    """$('#savvy').addEventListener('change',e=>{S.savvy=SAVVY[e.target.value]!=null?e.target.value:'sharp';S.savvyChosen=true;save();render()});""")
rep("""if(!S.siteChosen){S.site='espn';S.siteChosen=true;save()}""", """if(!S.siteChosen){S.site='espn';S.siteChosen=true;save()}
// your leaguemates are experienced category drafters: switch a saved setting over to Sharp once
if(!S.savvyChosen){S.savvy='sharp';S.savvyChosen=true;save()}""")
rep("""$('#format').value=S.format;$('#site').value=S.site||'avg';$('#future').value=S.future||'bal';$('#oppMode').value=S.oppMode||'smart';$('#savvy').value=S.savvy||'mixed';""",
    """$('#format').value=S.format;$('#site').value=S.site||'avg';$('#future').value=S.future||'bal';$('#oppMode').value=S.oppMode||'smart';$('#savvy').value=S.savvy||'sharp';""")
rep("""savvy:'mixed',board:{}""", """savvy:'sharp',board:{}""")

# displays: experts on the board and cards, in the ADP tooltip, the value explanation and the draft log
rep("""  return `Where managers in your league are expected to take him (${SITES[S.site]||SITES.avg})${b.length?': '+b.join(', '):''}`;""",
    """  const e=p.exp?` · expert consensus #${p.exp[0]} (range ${p.exp[1]}-${p.exp[2]})`:'';
  return `Where ${SITES[S.site]||SITES.avg} managers take him${b.length?': '+b.join(', '):''}${e}`;""")
rep("""${hasAdp(p)?`<span title="${esc(adpTip(p))}">ADP ${Math.round(adpOf(p))}</span>`:''}${estHtml(p)}${noteHtml(p)}</div>
        <div class="tags">""", """${hasAdp(p)?`<span title="${esc(adpTip(p))}">ADP ${Math.round(adpOf(p))}</span>`:''}${p.exp?`<span title="${esc(adpTip(p))}">Experts #${p.exp[0]}</span>`:''}${estHtml(p)}${noteHtml(p)}</div>
        <div class="tags">""")
rep("""${hasAdp(x.p)?`<span title="${esc(adpTip(x.p))}">ADP ${Math.round(adpOf(x.p))}</span>`:''}""",
    """${hasAdp(x.p)?`<span title="${esc(adpTip(x.p))}">ADP ${Math.round(adpOf(x.p))}</span>`:''}${x.p.exp?`<span title="${esc(adpTip(x.p))}">Experts #${x.p.exp[0]}</span>`:''}""")
rep("""adjusted for expected games, where managers draft him${p.age>=31?' and age':''}""", """adjusted for expected games, the expert consensus${p.age>=31?' and age':''}""")
rep("""Value is his 9-cat worth this season: per-game z-scores times the games he's expected to play (a waiver player fills the rest), met halfway with where managers draft him, adjusted for age 31+. Hover it for his per-game value.""",
    """"Experts" is FantasyPros' consensus of category-league experts (refreshed with the ESPN data). Value is his 9-cat worth this season: per-game projections (FanScout, ESPN and FantasyPros' consensus, averaged) times the games he's expected to play (a waiver player fills the rest), met halfway with the expert consensus, adjusted for age 31+. Hover it for his per-game value.""")
rep("""<span title="This season's 9-cat value: per-game value adjusted for expected games, where managers draft him, and age">Value</span>""",
    """<span title="This season's 9-cat value: per-game projections adjusted for expected games, the expert consensus and age">Value</span>""")
rep("""  const head=['pick','round','pick_label','manager','player','kept','espn_adp','espn_category_rank','yahoo_adp','fantasypros_espn_adp','app_adp_estimate','season_value','per_game_value'];""",
    """  const head=['pick','round','pick_label','manager','player','kept','espn_adp','espn_category_rank','yahoo_adp','fantasypros_espn_adp','experts_rank','app_adp_estimate','season_value','per_game_value'];""")
rep("""    rows.push([p+1,Math.floor(p/N())+1,pickLabel(p),nameOf(teamAt(p)),pl.name,KS.map.has(p)?1:0,m[0],m[1],pl.adp?pl.adp[0]:null,pl.adp?pl.adp[1]:null,
      Math.round(adpOf(pl)*10)/10,""", """    rows.push([p+1,Math.floor(p/N())+1,pickLabel(p),nameOf(teamAt(p)),pl.name,KS.map.has(p)?1:0,m[0],m[1],pl.adp?pl.adp[0]:null,pl.adp?pl.adp[1]:null,
      pl.exp?pl.exp[0]:null,Math.round(oppRank(pl)*10)/10,""")

# self-test
rep("""    window.__draftSelfTest='ran';""", """    const tp={exp:[20,15,25],adp:[30,null],mkt:[40,60],stats:{},rank:50,pgRank:50};
    console.assert(marketRank(tp)===20&&marketRank({...tp,exp:null})===30,'Market: expert consensus first, then Yahoo ADP');
    const sv=S.savvy;S.savvy='casual';const c0=oppRank(tp);S.savvy='sharp';const c1=oppRank(tp);S.savvy=sv;
    console.assert(c0===siteAdp(tp)&&Math.abs(c1-(0.75*20+0.25*siteAdp(tp)))<1e-9,'Opponents: casual = ESPN only, sharp = mostly experts');
    window.__draftSelfTest='ran';""")
open(APP, 'w', encoding='utf-8', newline='\n').write(s)
print('patched')
