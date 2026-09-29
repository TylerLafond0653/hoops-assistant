// League stress test: practice drafts against leaguemates with different builds and mistakes, then a season.
// Run (Sept 29, 2026 results in MODEL_AUDIT.md section 19):
//   1. Open draft-room.html in Chrome, press F12, open Console.
//   2. Paste this whole file, press Enter, then run:   await H.runAll()      (about 4 minutes)
//   3. Reload the page afterwards. Nothing is saved while the test runs, so your real draft is untouched.
//
// Your team (seat 5) is drafted four ways in the same league: the app's Recommended pick ('app'), best available
// by the expert consensus ('experts'), by ESPN's list ('espn'), and by the app's board order ('board').
// Leaguemate personas: list = which ranking they draft off (with realistic scatter); build = the plan they commit
// to from round `commit` (they give up `reach` value points per ranking spot to get a fit); mistake = chance per
// pick from round 2 of a blunder (reach 15-45 spots, injured player, old vet, rookie hype); homer/vet/rookie = biases.
// Each finished league plays 600 seasons: every player gets a projection miss of the size the app assumes, a
// 19-week schedule decided category by category with the measured weekly swings, top 6 make the playoffs.
// Three "truths": 'app' (the app's values), 'proj' (projections only) and 'exp' (the experts are right).
window.save = function(){};
window.H = {};
H.B = id => BUILDS.find(b=>b.id===id);
H.bv = (p,b) => {const e=effZ(p);return CATS.reduce((s,c,k)=>s+b.w[c]*e[k],0)};
H.reset = function(){
  S = freshState(); applyOfficialOrder(); S.savvy='sharp'; S.site='espn'; S.format='h2h'; S.future='bal'; delete S.planAnchor;
  UI.oppPlan = {}; UI.mockSeed = 'test'; KS = keeperSlots();
  SIMC = {key:'',res:null,myPicks:[]}; LA = {key:'',res:null};
  seasonRank();
};
H.oppPick = function(t, P, seedStr, pickNo){
  const av = available(), round = Math.floor(pickNo/10)+1;
  const list = P.list==='espn' ? rankSite : rankExp;
  const nz = (tag,id) => gauss(mulberry(hashStr(seedStr+'|'+tag+'|'+id)));
  // a league-wide view of each player plus this manager's own
  const noisy = av.map(p=>{const a=list(p);let r=a+(0.6*nz('all',p.id)+0.8*nz('t'+t,p.id))*adpSd(a);
    if(P.homer&&p.team===P.homer)r-=25; if(P.vet&&p.age>=31)r-=15; if(P.rookie&&p.est==='r')r-=20; return {p,r}}).sort((x,y)=>x.r-y.r);
  const rng = mulberry(hashStr(seedStr+'|m|'+pickNo));
  if(round>=2 && rng()<(P.mistake||0)){
    const kinds=['reach','reach','injured','old vet','rookie hype'], kind=kinds[Math.floor(rng()*kinds.length)];
    const pool = kind==='reach'?noisy.slice(15,45):kind==='injured'?noisy.slice(0,50).filter(x=>x.p.flag==='out'||gamesShare(x.p)<0.75)
      :kind==='old vet'?noisy.slice(0,50).filter(x=>x.p.age>=32):noisy.slice(0,50).filter(x=>x.p.est==='r');
    if(pool.length){const x=kind==='reach'?pool[Math.floor(rng()*pool.length)]:pool[0];return {p:x.p,mistake:kind}}
  }
  if(!P.build||P.build==='bal'||round<P.commit)return {p:noisy[0].p};
  const b=H.B(P.build), r0=noisy[0].r; let best=noisy[0], bs=-1e9;
  noisy.slice(0,12+round).forEach(x=>{const s=H.bv(x.p,b)-(P.reach||0.07)*(x.r-r0);if(s>bs){bs=s;best=x}});
  return {p:best.p};
};
H.tylerPick = function(strat){
  if(strat==='app'){
    renderAdvice();
    const plan=(document.querySelector('#recBody .bname')||{}).textContent, sure=(document.querySelector('#recBody .sure')||{}).textContent;
    return {p:byId.get(UI.recId), plan, sure};
  }
  const av=available();
  if(strat==='experts')return {p:av.slice().sort((a,b)=>rankExp(a)-rankExp(b))[0]};
  if(strat==='espn')return {p:av.slice().sort((a,b)=>rankSite(a)-rankSite(b))[0]};
  return {p:av[0]};
};
// forced(i) can override your i-th pick (a name, or a function returning a player) to test going off-script
H.runDraft = async function(personas, seed, strat, forced=()=>null){
  H.reset(); const seedStr='s'+seed, log=[], mistakes=[]; let mi=0;
  while(cur()<total()){
    const p=cur(), t=teamAt(p); let pick;
    if(t===me()){
      const r=H.tylerPick(strat), f=forced(mi);let tag='';
      const fp=f?(typeof f==='string'?available().find(x=>x.name===f):f()):null;
      pick=fp||r.p;if(fp&&fp.id!==r.p.id)tag='off-script, app said '+r.p.name;
      log.push({pick:pickLabel(p),name:pick.name,plan:r.plan,sure:r.sure,tag});mi++;await new Promise(r=>setTimeout(r,0));
    }else{const r=H.oppPick(t,personas[t],seedStr,p);pick=r.p;if(r.mistake)mistakes.push({team:nameOf(t),pick:pickLabel(p),name:pick.name,kind:r.mistake})}
    S.board[p]=pick.id;S.order.push(p);
  }
  return {rosters:Array.from({length:N()},(_,t)=>rosterOf(t).map(x=>x.p)),log,mistakes,lc:leagueCompare()};
};
H.season = function(rosters, truth='app', NS=600, seed=7){
  const old=TUNE.market; TUNE.market = truth==='proj'?0:truth==='exp'?1:old;
  const E=rosters.map(r=>r.map(p=>effZ(p).slice())); TUNE.market=old; effZ(rosters[0][0]);
  const SDp=rosters.map(r=>r.map(p=>projSd(p))), n=rosters.length, rng=mulberry(seed);
  const cr=Math.sqrt(MISS_R), ci=Math.sqrt(1-MISS_R);
  const rr=[];{const ids=[...Array(n).keys()];for(let w=0;w<n-1;w++){const pr=[];for(let i=0;i<n/2;i++)pr.push([ids[i],ids[n-1-i]]);rr.push(pr);ids.splice(1,0,ids.pop())}}
  const out=Array.from({length:n},()=>({wins:0,po:0,title:0,first:0,rank:0}));
  const week=(tot,a,b)=>{let ca=0;for(let q=0;q<9;q++)if(tot[a][q]-tot[b][q]+gauss(rng)*WEEK_SD_CAT[q]*TUNE.weekSd>0)ca++;return ca};
  for(let s=0;s<NS;s++){
    const tot=rosters.map((r,t)=>{
      const items=r.map((p,k)=>{const u=gauss(rng);const x=E[t][k].map((e,q)=>e+SDp[t][k]*MISS_W[q]*(cr*u+ci*gauss(rng)));return {x,v:x.reduce((a,b)=>a+b,0)}}).sort((a,b)=>b.v-a.v);
      const v=Array(9).fill(0);items.forEach((it,k)=>{const w=SLOT_W[Math.min(k,SLOT_W.length-1)];it.x.forEach((x,q)=>v[q]+=w*x)});return v});
    const W=Array(n).fill(0),C=Array(n).fill(0);
    for(let w=0;w<19;w++)rr[w%9].forEach(([a,b])=>{const ca=week(tot,a,b);C[a]+=ca;C[b]+=9-ca;if(ca>=5)W[a]++;else W[b]++});
    const st=[...Array(n).keys()].sort((a,b)=>W[b]-W[a]||C[b]-C[a]);
    st.forEach((t,i)=>{out[t].wins+=W[t];out[t].rank+=i+1;if(i<6)out[t].po++;if(i===0)out[t].first++});
    const g=(a,b)=>week(tot,a,b)>=5?a:b;
    const w36=g(st[2],st[5]),w45=g(st[3],st[4]);
    const lo=st.indexOf(w36)>st.indexOf(w45)?w36:w45, hi=lo===w36?w45:w36;
    out[g(g(st[0],lo),g(st[1],hi))].title++;
  }
  return out.map(o=>({wins:o.wins/NS,po:o.po/NS,title:o.title/NS,first:o.first/NS,rank:o.rank/NS}));
};
const P_=(list,build,commit,extra={})=>({list,build,commit,reach:0.07,...extra});
const bal_=(list='exp',extra={})=>P_(list,'bal',99,extra);
// seats in draft order: Saksham, Jattan, Cristian, Sameer, (you), Arjun, Surya, Satvik, Santosh, Pratham
H.SCN = {
  control: [bal_(),bal_(),bal_(),bal_('espn'),null,bal_(),bal_(),bal_('espn'),bal_(),bal_()],
  builds: [P_('exp','ft',1,{mistake:.05}),P_('exp','fg',3,{mistake:.05}),P_('exp','ast',3,{mistake:.05}),P_('espn','bigs',2,{mistake:.05}),null,
           P_('exp','to',1,{mistake:.05}),bal_('exp',{mistake:.05}),P_('espn','guards',3,{mistake:.05}),P_('exp','ft3',2,{mistake:.05}),bal_('espn',{mistake:.05})],
  messy: [P_('exp','ft',1,{mistake:.2}),P_('exp','fg',3,{mistake:.2,homer:'TOR'}),P_('exp','ast',3,{mistake:.2}),P_('espn','bigs',2,{mistake:.2,vet:true}),null,
          P_('exp','to',1,{mistake:.2}),bal_('exp',{mistake:.2,rookie:true}),P_('espn','guards',3,{mistake:.2}),P_('exp','ft3',2,{mistake:.2}),bal_('espn',{mistake:.2})],
  bigsRush: [P_('exp','ft',1,{mistake:.05}),P_('exp','bigs',1,{mistake:.05}),bal_('exp',{mistake:.05}),P_('espn','ft3',2,{mistake:.05}),null,
             P_('exp','ast',1,{mistake:.05}),bal_('exp',{mistake:.05}),P_('exp','3pm',2,{mistake:.05}),bal_('espn',{mistake:.05}),bal_('exp',{mistake:.05})],
  guardsRush: [P_('exp','fg',1,{mistake:.05}),bal_('exp',{mistake:.05}),P_('exp','guards',1,{mistake:.05}),bal_('espn',{mistake:.05}),null,
               P_('exp','blk',2,{mistake:.05}),P_('exp','to',1,{mistake:.05}),bal_('exp',{mistake:.05}),P_('espn','count',2,{mistake:.05}),bal_('exp',{mistake:.05})],
};
H.runAll = async function(seeds=[1,2,3,4], strats=['app','experts','espn','board']){
  const res=[];
  for(const scn of Object.keys(H.SCN))for(const seed of seeds)for(const strat of strats){
    const d=await H.runDraft(H.SCN[scn],seed,strat),row={scn,seed,strat,log:d.log,cr:d.lc.find(r=>r.t===me()).cr};
    for(const tr of ['app','proj','exp'])row[tr]=H.season(d.rosters,tr,600,seed*31+7)[me()];
    res.push(row);console.log(res.length,scn,seed,strat,row.app.wins.toFixed(1));
  }
  const rows=[];
  for(const scn of Object.keys(H.SCN))for(const strat of strats){
    const r=res.filter(x=>x.scn===scn&&x.strat===strat),a=(tr,m)=>r.reduce((s,x)=>s+x[tr][m],0)/r.length;
    rows.push({league:scn,you:strat,wins:+a('app','wins').toFixed(1),playoffs:Math.round(100*a('app','po'))+'%',title:Math.round(100*a('app','title'))+'%',
      wins_if_projections_right:+a('proj','wins').toFixed(1),wins_if_experts_right:+a('exp','wins').toFixed(1)});
  }
  console.table(rows);H.last=res;return rows;
};
'loaded: run  await H.runAll()'
