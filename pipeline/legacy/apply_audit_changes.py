"""One-time patch (Sept 25, 2026): the model changes from analysis/MODEL_AUDIT.md that passed the backtests.
Kept for the record; it asserts every edit matches exactly once, so it can't be re-run on a patched file."""
import os, json
APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'draft-room.html')
s = open(APP, encoding='utf-8').read()
CAL = json.load(open(os.path.join(os.path.dirname(APP), 'analysis', 'calibration.json')))
def rep(a, b):
    global s
    n = s.count(a)
    assert n == 1, (n, a[:90])
    s = s.replace(a, b)

# ---------- A1: ESPN's own market (live ADP + category-league rank) ----------
rep("""const SITES={avg:'Yahoo + ESPN average',yahoo:'Yahoo',espn:'ESPN'};
function siteAdp(a){
  if(!a)return null;const [ya,es]=a,s=S.site||'avg';
  if(s==='yahoo'&&ya!=null)return ya;if(s==='espn'&&es!=null)return es;
  return ya!=null&&es!=null?(ya+es)/2:(ya!=null?ya:es);
}""", """const SITES={avg:'Yahoo + ESPN average',yahoo:'Yahoo',espn:'ESPN'};
// Where ESPN managers take a player: ESPN's own live ADP (from ESPN's feed; FantasyPros' "ESPN" column was a
// median 13 picks off it) averaged with ESPN's category-league ranking, which is the list a 9-cat league's
// draft room shows. ESPN's ADP comes from 13-round leagues and bunches up past pick ~115, so beyond that
// only the category rank is used. TUNE.catRank = weight on the category rank (check it on your draft log).
function espnAnchor(p){
  const m=p.mkt;
  if(m){const [adp,cat]=m;if(adp!=null&&cat!=null)return TUNE.catRank*cat+(1-TUNE.catRank)*adp;if(cat!=null)return cat;if(adp!=null)return adp}
  return p.adp&&p.adp[1]!=null?p.adp[1]:null;
}
function siteAdp(p){
  if(!p)return null;const ya=p.adp?p.adp[0]:null,es=espnAnchor(p),s=S.site||'avg';
  if(s==='yahoo'&&ya!=null)return ya;if(s==='espn'&&es!=null)return es;
  return ya!=null&&es!=null?(ya+es)/2:(ya!=null?ya:es);
}
const hasAdp=p=>!!(p.adp||p.mkt);""")
rep("""const adpOf=p=>{if(p.importedRank!=null)return p.importedRank;const a=siteAdp(p.adp);return a!=null?a:p.stats?Math.max(150,p.rank+10):p.rank};
// players outside this list still use up other managers' picks
const PHANTOMS=ADP_OTHERS.map(([name,ya,es],i)=>({id:-(i+1),name,key:normName(name),adp:[ya,es],phantom:true,pos:[],rank:999}));""",
"""const adpOf=p=>{if(p.importedRank!=null)return p.importedRank;const a=siteAdp(p);return a!=null?a:p.stats?Math.max(150,(p.pgRank||p.rank)+10):p.rank};
// players outside this list still use up other managers' picks (FantasyPros' list plus ESPN's)
const PHANTOMS=(()=>{
  const m=new Map();ADP_OTHERS.forEach(([name,ya,es])=>m.set(normName(name),{name,adp:[ya,es],mkt:null}));
  ESPN_OTHERS.forEach(([name,adp,cat])=>{const k=normName(name),o=m.get(k)||{name,adp:null};o.mkt=[adp,cat];m.set(k,o)});
  return [...m.entries()].map(([key,o],i)=>({id:-(i+1),name:o.name,key,adp:o.adp,mkt:o.mkt,phantom:true,pos:[],rank:999}));
})();""")
rep("""      adp:ADP[name]||null,age:AGE[name]!=null?AGE[name]:null,est:EST[name]||'',dis:DISAGREE[name]||0};""",
    """      adp:ADP[name]||null,mkt:ESPN_MKT[name]||null,age:AGE[name]!=null?AGE[name]:null,est:EST[name]||'',dis:DISAGREE[name]||0};""")
rep("""  [...list].sort((a,b)=>total(b)-total(a)||a.id-b.id).forEach((p,i)=>{p.rank=i+1});
  return list;""", """  [...list].sort((a,b)=>total(b)-total(a)||a.id-b.id).forEach((p,i)=>{p.rank=i+1;p.pgRank=i+1});
  return list;""")
rep("""    return {id:i+1,rank:i+1,importedRank:i+1,name,""", """    return {id:i+1,rank:i+1,pgRank:i+1,importedRank:i+1,mkt:k?k.mkt:null,dis:k?k.dis:0,name,""")

# ---------- one player value everywhere (season value: games, market, age) ----------
rep("""function valueOf(p){return p.z?CATS.reduce((s,c)=>s+(S.punt.includes(c)?0:p.z[c]),0):null}""",
"""// 9-cat value: THIS SEASON's expected value (effZ: per-game z-scores x expected games with a waiver player
// in the missed games, met halfway with the market, age 31+ adjusted), leaving out punted categories.
// The same number the simulator uses, so the board, the cards and the Recommended pick agree.
// null = no projections.
function valueOf(p){if(!p.z)return null;const e=effZ(p);return CATS.reduce((s,c,k)=>s+(S.punt.includes(c)?0:e[k]),0)}
// per-game value (no games, no market): shown as a secondary figure
const perGameValue=p=>p.z?CATS.reduce((s,c)=>s+(S.punt.includes(c)?0:p.z[c]),0):null;
// Rank the built-in list by season value (imported lists keep the order they were pasted in).
let SR='';
function seasonRank(){
  if(S.custom)return;const k=S.site+'|'+TUNE.market+'|'+TUNE.catRank;if(SR===k)return;SR=k;
  const tot=p=>effZ(p).reduce((s,v)=>s+v,0);
  [...DEFAULT].sort((a,b)=>tot(b)-tot(a)||a.id-b.id).forEach((p,i)=>{p.rank=i+1});
}""")
rep("""  const pool=players().filter(p=>p.z).sort((a,b)=>a.rank-b.rank).slice(120,150);""",
    """  const pool=players().filter(p=>p.z).sort((a,b)=>(a.pgRank||a.rank)-(b.pgRank||b.rank)).slice(120,150);""")
rep("""  const top=players().slice().sort((a,b)=>a.rank-b.rank).slice(0,150);
  BNORM=""", """  const top=players().slice().sort((a,b)=>(a.pgRank||a.rank)-(b.pgRank||b.rank)).slice(0,150);
  BNORM=""")
rep("""function effZ(p){
  // raw values, not capped: the weekly matchup model already gives diminishing returns for piling up one
  // category (a blowout in blocks is still one category), so capping here would penalize specialists twice
  const R=replProfile(),own=p.z&&!p.phantom?CATS.map(c=>p.z[c]):R;
  const shift=TUNE.market*(valueAtPick(adpOf(p))-own.reduce((s,v)=>s+v,0))/CATS.length;
  const g=p.phantom?1:gamesShare(p);
  return own.map((v,k)=>(v+shift)*g+R[k]*(1-g));
}""", """// cached per player; the cache resets when the list or the league site (ADP) changes
let EZ={key:'',m:new Map()};
function effZ(p){
  const ck=[S.site,players().length,S.custom?1:0,TUNE.market,TUNE.catRank,TUNE.ageNow].join('|');
  if(EZ.key!==ck)EZ={key:ck,m:new Map()};
  const hit=EZ.m.get(p);if(hit)return hit;
  // raw values, not capped: the weekly matchup model already gives diminishing returns for piling up one
  // category (a blowout in blocks is still one category), so capping here would penalize specialists twice
  const R=replProfile(),own=p.z&&!p.phantom?CATS.map(c=>p.z[c]):R;
  const shift=TUNE.market*(valueAtPick(adpOf(p))-own.reduce((s,v)=>s+v,0))/CATS.length;
  const g=p.phantom?1:gamesShare(p);
  // players 31+ fell short of their projections by about 0.4 more than prime-age players in each of the
  // last three seasons (analysis/audit_projection_seasons.py; tested out of sample in backtest_age.py)
  const age=!p.phantom&&p.age!=null&&p.age>=31?TUNE.ageNow/CATS.length:0;
  const out=own.map((v,k)=>(v+shift)*g+R[k]*(1-g)+age);
  EZ.m.set(p,out);return out;
}""")

# keeper value in the same units: per-game value with a future games share halfway to full health
rep("""// best run of keeper seasons (you can stop keeping any year, but can't skip one and come back)
function keeperPlan(p,round){
  if(!p||!p.z||p.age==null||p.phantom)return {kv:0,years:0,path:[]};
  let v=CATS.reduce((s,c)=>s+p.z[c],0),alive=1,run=0,best=0,years=0;const path=[];
  for(let y=1;y<=3;y++){
    v+=ageStep(p.age+y-1)+expStep(p,y);alive*=1-breakRisk(p.age+y);""",
"""// Keeper seasons count games too: this season's missed time mostly doesn't carry over, chronic missed time
// partly does, so future seasons use a games share halfway between this season's and full health. Next
// year's pick values (keeperPickValue) are measured the same way, so both sides are in the same units.
const futureShare=p=>0.5+0.5*gamesShare(p);
function futureValue(p){const R=replProfile(),g=futureShare(p);return CATS.reduce((s,c,k)=>s+p.z[c]*g+R[k]*(1-g),0)}
let VTF={list:null,v:[]};
function futureAtPick(a){
  if(VTF.list!==players())VTF={list:players(),v:players().filter(p=>p.z).map(futureValue).sort((x,y)=>y-x)};
  const v=VTF.v;return v.length?v[Math.max(0,Math.min(v.length-1,Math.round(a)-1))]:0;
}
// best run of keeper seasons (you can stop keeping any year, but can't skip one and come back)
function keeperPlan(p,round){
  if(!p||!p.z||p.age==null||p.phantom)return {kv:0,years:0,path:[]};
  let v=futureValue(p),alive=1,run=0,best=0,years=0;const path=[],g=futureShare(p);
  for(let y=1;y<=3;y++){
    v+=(ageStep(p.age+y-1)+expStep(p,y))*g;alive*=1-breakRisk(p.age+y);""")
rep("""const keeperPickValue=r=>valueAtPick(pickOfRound(r)+keepDeplete());""", """const keeperPickValue=r=>futureAtPick(pickOfRound(r)+keepDeplete());""")

# ---------- B1/B3: uncertainty and weekly spread from three seasons of data ----------
rep("""const TUNE={
  weekSd:5,        // week-to-week swing in a category total; 3-7 give the same plan ranking
  market:0.5,      // how far to meet ADP when it disagrees with FanScout (0 = trust FanScout fully)
  deplete:0.25,    // share of the league's keepers counted as gone before a pick next year
  rookie:0.5,      // share of the measured rookie/sophomore extra growth that's counted
  projSd:1.5,      // typical projection miss in 9-cat value per season (larger for rookies, estimates, injuries)
};""", """const TUNE={
  weekSd:1,        // multiplier on the measured weekly spread of each category (WEEK_SD_CAT)
  market:0.5,      // how far to meet ADP when it disagrees with the projections (backtest: +3.7 pts of weekly
                   // wins on average over 3 seasons; 0.25 and 0 did worse)
  catRank:0.5,     // ESPN anchor: weight on ESPN's category-league rank vs ESPN's live ADP
  deplete:0.25,    // share of the league's keepers counted as gone before a pick next year
  rookie:0.5,      // share of the measured rookie/sophomore extra growth that's counted
  projSd:2.2,      // typical projection miss in season value (ESPN alone missed by 2.3-2.5 in each of the last
                   // 3 seasons; averaging with FanScout should cut that a little). Larger for rookies, estimates, injuries.
  ageNow:-0.4,     // this-season adjustment for players 31+ (they missed their projections by ~0.4 more)
};""")
rep("""const WEEK_SD=TUNE.weekSd;""", """const WEEK_SD=TUNE.weekSd;
// Week-to-week spread of each category's team total, measured on three seasons of real box scores with
// injured players' games filled by a waiver player (analysis/calibrate_constants.py -> calibration.json).
// Steals, FG%%, FT%% and threes swing far more week to week than points, rebounds and assists.
const WEEK_SD_CAT=%s;
// How projections miss, by category (per game, ESPN preseason vs actual, 3 seasons). Misses in different
// categories are nearly independent (average correlation %s), so each player gets a shock per category plus a
// small shared one, scaled so the total miss is projSd(p).
const MISS_CAT=%s,MISS_R=%s;
const MISS_W=(()=>{const s2=MISS_CAT.reduce((a,x)=>a+x*x,0),s1=MISS_CAT.reduce((a,x)=>a+x,0),tot=Math.sqrt(s2+MISS_R*(s1*s1-s2));return MISS_CAT.map(x=>x/tot)})();""" % (
    json.dumps([CAL['weekly_sd'][c] for c in ['PTS', 'REB', 'AST', 'STL', 'BLK', '3PM', 'FG', 'FT', 'TO']]), CAL['proj_r'],
    json.dumps([CAL['proj_sd'][c] for c in ['PTS', 'REB', 'AST', 'STL', 'BLK', '3PM', 'FG', 'FT', 'TO']]), CAL['proj_r']))
rep("""  for(let q=0;q<CATS.length;q++){const pw=ncdf((a[q]-b[q])/TUNE.weekSd);cat.push(pw);mu+=pw;v+=pw*(1-pw)}""",
    """  for(let q=0;q<CATS.length;q++){const pw=ncdf((a[q]-b[q])/(WEEK_SD_CAT[q]*TUNE.weekSd));cat.push(pw);mu+=pw;v+=pw*(1-pw)}""")
rep("""  const shockGen=id=>{const r=mulberry(hashStr((seed||key)+'|sh|'+id));return Array.from({length:NS},()=>gauss(r))};""",
    """  const shockGen=id=>{const r=mulberry(hashStr((seed||key)+'|sh|'+id)),a=new Float64Array(NS*9),cr=Math.sqrt(MISS_R),ci=Math.sqrt(1-MISS_R);
    for(let s=0;s<NS;s++){const u=gauss(r);for(let q=0;q<9;q++)a[s*9+q]=MISS_W[q]*(cr*u+ci*gauss(r))}return a};""")
rep("""        const items=baseTeams[t].map((b,k)=>({e:b.e,x:BSH[t][k][s]*b.sd})).concat(picked[t].map(i=>({e:E[i],x:SH[i][s]*PS[i]})));
        items.forEach(it=>it.v=it.e.reduce((a,b)=>a+b,0)+it.x);items.sort((a,b)=>b.v-a.v);
        const v=CATS.map(()=>0);items.forEach((it,k)=>{const wt=SLOT_W[k]!=null?SLOT_W[k]:SLOT_W[SLOT_W.length-1];for(let q=0;q<CATS.length;q++)v[q]+=wt*(it.e[q]+it.x/CATS.length)});""",
    """        const o=s*9;
        const items=baseTeams[t].map((b,k)=>({e:b.e,x:BSH[t][k],sd:b.sd})).concat(picked[t].map(i=>({e:E[i],x:SH[i],sd:PS[i]})));
        items.forEach(it=>{let t2=0;for(let q=0;q<9;q++)t2+=it.e[q]+it.x[o+q]*it.sd;it.v=t2});items.sort((a,b)=>b.v-a.v);
        const v=CATS.map(()=>0);items.forEach((it,k)=>{const wt=SLOT_W[k]!=null?SLOT_W[k]:SLOT_W[SLOT_W.length-1];for(let q=0;q<CATS.length;q++)v[q]+=wt*(it.e[q]+it.x[o+q]*it.sd)});""")

# ---------- win-unit thresholds keep their meaning in value points ----------
rep("""const WIN_PER_Z=0.021;""", """const WIN_PER_Z=__WINPERZ__;
// The plan and pick thresholds below were set when a value point was worth 2.1%% of weekly matchups; WU keeps
// each one worth the same number of value points under the recalibrated matchup model.
const WU=WIN_PER_Z/0.021;""".replace('%%', '%'))
rep("""const sureCls=(g,se=0)=>g>=.03&&g>=2.5*se?'hi':g>=.01&&g>=1.5*se?'mid':'lo';""",
    """const sureCls=(g,se=0)=>g>=.03*WU&&g>=2.5*se?'hi':g>=.01*WU&&g>=1.5*se?'mid':'lo';""")
rep("""  const bonus=j=>(BUILDS[j].level==='Hard'?-0.03:0)+(BUILDS[j].id==='bal'?0.005:0)+(chosen(BUILDS[j])?0.01:0);""",
    """  const bonus=j=>((BUILDS[j].level==='Hard'?-0.03:0)+(BUILDS[j].id==='bal'?0.005:0)+(chosen(BUILDS[j])?0.01:0))*WU;""")
rep("""    const pd=pairDiff(res,fw,order[0],anc),need=Math.max(0.02+0.002*drafted,2.5*pd.se);""",
    """    const pd=pairDiff(res,fw,order[0],anc),need=Math.max((0.02+0.002*drafted)*WU,2.5*pd.se);""")
rep("""    out.push({p,pl,alt,gap,adp,grade:gap<=1?'good':gap<=3?'close':'miss'});""",
    """    out.push({p,pl,alt,gap,adp,grade:gap<=1*WU?'good':gap<=3*WU?'close':'miss'});""")

# ---------- A3 + adaptive simulation count: look-ahead ----------
rep("""function lookahead(cands,anchor){
  const c=cur(),fw=futureW();
  const key=[S.order.map(p=>p+':'+S.board[p]).join(','),S.site,fw,S.punt.join(),anchor,cands.map(p=>p.id).join(',')].join('|');
  if(LA.key===key)return LA.res;
  const seed='la:'+S.order.length+':'+S.site;
  const res=cands.map(p=>{
    S.board[c]=p.id;S.order.push(c);
    const R=simBuilds(me(),fw,'la',60,seed),""", """function lookahead(cands,anchor,NS=60,tag=''){
  const c=cur(),fw=futureW();
  // everything that changes the answer is in the key (leaguemates, format, keepers and settings too)
  const key=[S.order.map(p=>p+':'+S.board[p]).join(','),S.site,S.savvy,S.format,[...KS.map].join(','),JSON.stringify(TUNE),fw,S.punt.join(),anchor,NS,tag,cands.map(p=>p.id).join(',')].join('|');
  if(LA.key===key)return LA.res;
  const seed='la'+tag+':'+S.order.length+':'+S.site;
  const res=cands.map(p=>{
    S.board[c]=p.id;S.order.push(c);
    const R=simBuilds(me(),fw,'la'+tag,NS,seed),""")
rep("""// paired lead of look-ahead result a over b, and its noise
function laLead(a,b){""", """// a candidate's own simulation noise (how uncertain his finished team is)
const laSe=r=>{const m=r.v,n=r.vals.length;return Math.sqrt(r.vals.reduce((t,x)=>t+(x-m)**2,0)/Math.max(1,n-1))/Math.sqrt(n)};
// paired lead of look-ahead result a over b, and its noise
function laLead(a,b){""")

# ---------- A5: practice opponents value players the same way ----------
rep("""    const xs=av.map(x=>({x,t:(x.z?CATS.reduce((s,c)=>s+zOf(x,c),0):-5)+fw*keeperPlan(x,round).kv,q:after<0?0:chance(AI.get(x.id),mA)}));""",
    """    const xs=av.map(x=>({x,t:(x.z?effZ(x).reduce((s,v)=>s+v,0):-5)+fw*keeperPlan(x,round).kv,q:after<0?0:chance(AI.get(x.id),mA)}));""")

# ---------- A2: tie-break, and a closer look at near-ties ----------
rep("""  let laBest=null,la=null,tied=()=>false;
  if(m===0&&rec){
    const pool=[rec,planX,...bpa,fit,...likely.slice(0,4)].filter(Boolean);
    const cands=[...new Map(pool.map(x=>[x.p.id,x])).values()].slice(0,6).map(x=>x.p);
    la=lookahead(cands,TB.id);const best=la[0];
    tied=r=>{if(!r||!best)return false;if(r===best)return true;const l=laLead(best,r);return l.m<Math.max(0.004,1.5*l.se)};
    const pick=(planX&&la.find(r=>r.p.id===planX.p.id&&tied(r)))||la.find(r=>r.p.id===rec.p.id&&tied(r))||best;
    if(pick)rec=likely.find(x=>x.p.id===pick.p.id)||rec;""", """  let laBest=null,la=null,tied=()=>false;
  if(m===0&&rec){
    const pool=[rec,planX,...bpa,fit,...likely.slice(0,4)].filter(Boolean);
    const cands=[...new Map(pool.map(x=>[x.p.id,x])).values()].slice(0,6).map(x=>x.p);
    la=lookahead(cands,TB.id);
    // near-tie at the top: replay the leading three three times as often before deciding
    if(la.length>1){const l=laLead(la[0],la[1]);if(l.m<2*l.se){
      const top=lookahead(la.slice(0,3).map(r=>r.p),TB.id,180,'x'),ids=new Set(top.map(r=>r.p.id));
      la=[...top,...la.filter(r=>!ids.has(r.p.id)).map(r=>({...r,far:true}))];
    }}
    const best=la[0],bse=laSe(best);
    // tied = within the noise of the best (and 0.4 value points' worth), and not just because his own
    // result is much noisier than the best one's
    tied=r=>{if(!r||!best||r.far)return false;if(r===best)return true;const l=laLead(best,r);return l.m<Math.max(0.004*WU,1.5*l.se)&&laSe(r)<=1.5*bse};
    // among ties: the plan's pick only when the plan itself is at least "leaning" (so a close-call plan
    // can't pull a weaker player ahead), then the quick pick, otherwise the best
    const planOk=planX&&sure!=='lo';
    const pick=(planOk&&la.find(r=>r.p.id===planX.p.id&&tied(r)))||la.find(r=>r.p.id===rec.p.id&&tied(r))||best;
    if(pick)rec=likely.find(x=>x.p.id===pick.p.id)||rec;""")

# ---------- displays ----------
rep("""const valHtml=p=>{const v=valueOf(p);return `<span class="pval num ${v!=null&&v<0?'low':''}" title="Projected 9-cat value: total z-score${S.punt.length?' without punted categories':''}">${v==null?'—':(v>0?'+':'')+v.toFixed(1)}</span>`};""",
    """const valHtml=p=>{const v=valueOf(p),pg=perGameValue(p);return `<span class="pval num ${v!=null&&v<0?'low':''}" title="This season's 9-cat value${S.punt.length?' without punted categories':''}: per-game value ${pg==null?'—':(pg>0?'+':'')+pg.toFixed(1)}, adjusted for expected games, where managers draft him${p.age>=31?' and age':''}">${v==null?'—':(v>0?'+':'')+v.toFixed(1)}</span>`};""")
rep("""${p.adp?`<span title="Where other managers usually draft him (${esc(SITES[S.site]||SITES.avg)})">ADP ${Math.round(adpOf(p))}</span>`:''}${estHtml(p)}${noteHtml(p)}</div>
        <div class="tags">""", """${hasAdp(p)?`<span title="${esc(adpTip(p))}">ADP ${Math.round(adpOf(p))}</span>`:''}${estHtml(p)}${noteHtml(p)}</div>
        <div class="tags">""")
rep("""// Board stats view: this season's projection (default) or last season's actual per-game stats.""",
    """// what the ADP figure is made of
function adpTip(p){
  const m=p.mkt||[],b=[];
  if(S.site!=='yahoo'){if(m[0]!=null)b.push(`ESPN ADP ${Math.round(m[0])}`);if(m[1]!=null)b.push(`ESPN category rank ${m[1]}`)}
  if(S.site!=='espn'&&p.adp&&p.adp[0]!=null)b.push(`Yahoo ADP ${p.adp[0]}`);
  return `Where managers in your league are expected to take him (${SITES[S.site]||SITES.avg})${b.length?': '+b.join(', '):''}`;
}
// Board stats view: this season's projection (default) or last season's actual per-game stats.""")
rep("""<span title="Projected 9-cat value">Value</span>""", """<span title="This season's 9-cat value: per-game value adjusted for expected games, where managers draft him, and age">Value</span>""")
open(APP, 'w', encoding='utf-8', newline='\n').write(s)
print('patched')

# ---- second pass (applied right after the first) ----
if __name__ == '__main__' and 'hasAdp(x.p)' not in open(APP, encoding='utf-8').read():
    s = open(APP, encoding='utf-8').read()
    rep("""${x.p.adp?`<span title="Where other managers usually draft him (${esc(SITES[S.site]||SITES.avg)})">ADP ${Math.round(adpOf(x.p))}</span>`:''}""",
        """${hasAdp(x.p)?`<span title="${esc(adpTip(x.p))}">ADP ${Math.round(adpOf(x.p))}</span>`:''}""")
    rep("""    const a=pl.adp||pl.importedRank!=null?adpOf(pl):null,no=p+1;""", """    const a=hasAdp(pl)||pl.importedRank!=null?adpOf(pl):null,no=p+1;""")
    rep("""function render(){
""", """function render(){
  seasonRank();
""")
    rep("""const WIN_PER_Z=__WINPERZ__;""", """const WIN_PER_Z=0.021;""")
    open(APP, 'w', encoding='utf-8', newline='\n').write(s)
    print('second pass applied')
