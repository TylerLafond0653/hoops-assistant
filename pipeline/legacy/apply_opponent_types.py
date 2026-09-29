"""One-time patch (Sept 29, 2026): leaguemates are modelled as TYPES instead of an averaged list.
Averaging the expert and ESPN rankings made an in-between list nobody drafts from (Chet Holmgren ~28th, when expert
followers take him ~18th and ESPN followers ~58th), so availability odds missed in both kinds of league. Now, in
each simulated draft, each other manager drafts off the expert consensus (with the share set by "Your leaguemates")
or off ESPN's list, and the "% still there" odds mix the two cases."""
import os
APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'draft-room.html')
s = open(APP, encoding='utf-8').read()
def rep(a, b):
    global s
    n = s.count(a); assert n == 1, (n, a[:90]); s = s.replace(a, b)

rep("""function chance(i,m){if(m<=0)return 1;const s=Math.max(1.3,m*0.2);return 1/(1+Math.exp((m-i-0.5)/s))}""",
    """// i can be a plain count, or {e,s}: his place on the expert list and on ESPN's list (adpIndex). Then the odds
// mix the two kinds of leaguemate by the "Your leaguemates" setting.
function chance(i,m){
  if(i&&typeof i==='object'){const w=expertShare();return w*chance(i.e,m)+(1-w)*chance(i.s,m)}
  if(m<=0)return 1;const s=Math.max(1.3,m*0.2);return 1/(1+Math.exp((m-i-0.5)/s));
}""")
rep("""const OPP_EXPERT={casual:0,mixed:0.5,sharp:0.75};
function oppRank(p){
  if(p.importedRank!=null)return p.importedRank;
  const w=OPP_EXPERT[S.savvy]!=null?OPP_EXPERT[S.savvy]:OPP_EXPERT.sharp;
  const e=expertRank(p),es=siteAdp(p);
  if(e!=null&&es!=null)return w*e+(1-w)*es;
  if(es!=null)return es;
  return e!=null?e:noRank(p);
}""", """const OPP_EXPERT={casual:0,mixed:0.5,sharp:0.75};
const expertShare=()=>OPP_EXPERT[S.savvy]!=null?OPP_EXPERT[S.savvy]:OPP_EXPERT.sharp;
// The two lists leaguemates draft from. Each is complete: a player missing from one falls back to the other.
const rankExp=p=>{if(p.importedRank!=null)return p.importedRank;const e=expertRank(p);if(e!=null)return e;const s=siteAdp(p);return s!=null?s:noRank(p)};
const rankSite=p=>{if(p.importedRank!=null)return p.importedRank;const s=siteAdp(p);if(s!=null)return s;const e=expertRank(p);return e!=null?e:noRank(p)};
// one number for "where he usually goes" (keeper badge, bargain/early tags, which players the simulator keeps
// in its pool); the simulator and the odds use the two lists separately
const oppRank=p=>{const w=expertShare();return w*rankExp(p)+(1-w)*rankSite(p)};""")
rep("""function adpIndex(av){
  const all=[...av,...phantomsLeft()].map(p=>({p,a:oppRank(p)})).sort((x,y)=>x.a-y.a);
  const idx=new Map();all.forEach((x,i)=>{if(!x.p.phantom)idx.set(x.p.id,i)});return idx;
}""", """function adpIndex(av){
  const all=[...av,...phantomsLeft()];
  const place=f=>{const m=new Map();all.map(p=>({p,a:f(p)})).sort((x,y)=>x.a-y.a).forEach((x,i)=>{if(!x.p.phantom)m.set(x.p.id,i)});return m};
  const e=place(rankExp),s=place(rankSite),idx=new Map();
  av.forEach(p=>idx.set(p.id,{e:e.get(p.id),s:s.get(p.id)}));return idx;
}""")
rep("""  const E=pool.map(effZ),A=pool.map(oppRank);
  const byAdp=pool.map((_,i)=>i).sort((a,b)=>A[a]-A[b]);
  // how the other managers rank players: the expert consensus and ESPN's list, mixed by the leaguemates setting
  const A2=A;""", """  const E=pool.map(effZ),A=pool.map(oppRank),AE=pool.map(rankExp),AS=pool.map(rankSite);
  const byAdp=pool.map((_,i)=>i).sort((a,b)=>A[a]-A[b]);""")
rep("""  const rnd=mulberry(hashStr(seed||key)),SHOW=8;""", """  const rnd=mulberry(hashStr(seed||key)),SHOW=8;
  // each simulated draft, each other manager drafts off the expert consensus (chance = the leaguemates setting)
  // or off ESPN's list; drawn from the seed so look-ahead candidates face the same leaguemates
  const typR=mulberry(hashStr((seed||key)+'|type')),wExp=expertShare();
  const TYP=Array.from({length:NS},()=>Array.from({length:N()},()=>typR()<wExp));""")
rep("""  const score=new Float64Array(P),ct=new Float64Array(P),cq=new Float64Array(P),ci=new Int32Array(P);
  for(let s=0;s<NS;s++){
    for(let i=0;i<P;i++)score[i]=A2[i]+(PN?PN[i][s]:gauss(rnd))*adpSd(A2[i]);
    // every build faces the same draft by the other managers, so builds are compared fairly
    const ord=pool.map((_,i)=>i).sort((a,b)=>score[a]-score[b]);""",
    """  const scE=new Float64Array(P),scS=new Float64Array(P),ct=new Float64Array(P),cq=new Float64Array(P),ci=new Int32Array(P);
  for(let s=0;s<NS;s++){
    // the same draft-day scatter for a player on both lists
    for(let i=0;i<P;i++){const eps=PN?PN[i][s]:gauss(rnd);scE[i]=AE[i]+eps*adpSd(AE[i]);scS[i]=AS[i]+eps*adpSd(AS[i])}
    // every build faces the same draft by the other managers, so builds are compared fairly
    const ordE=pool.map((_,i)=>i).sort((a,b)=>scE[a]-scE[b]),ordS=pool.map((_,i)=>i).sort((a,b)=>scS[a]-scS[b]),typ=TYP[s];""")
rep("""      let ptr=0,mi=0,myC=myC0,have=have0;const kvs=baseKV.slice();""", """      let pE=0,pS=0,mi=0,myC=myC0,have=have0;const kvs=baseKV.slice();""")
rep("""        }else{
          while(ptr<P&&taken[ord[ptr]])ptr++;
          if(ptr<P)pick=ord[ptr];
        }""", """        }else if(typ[t]){
          while(pE<P&&taken[ordE[pE]])pE++;
          if(pE<P)pick=ordE[pE];
        }else{
          while(pS<P&&taken[ordS[pS]])pS++;
          if(pS<P)pick=ordS[pS];
        }""")
open(APP, 'w', encoding='utf-8', newline='\n').write(s)
print('patched')
