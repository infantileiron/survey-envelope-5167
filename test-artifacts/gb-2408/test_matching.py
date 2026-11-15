"""对拍验证：matching.reconcile_points vs 暴力枚举全部匹配（小规模）。

用法：PYTHONPATH=/workspace/backend python3 -I test_matching.py
覆盖：随机小图（含重合坐标/零距离阈值/并列代价）、字典序目标、
必然配对/归属歧义/始终未配点分类、报告方案最优性、确定性、超时拒绝、密集性能。
"""
import math,random,time
from src.services.matching import reconcile_points,ReconcileTimeout,_GRID

def quantize(left,right,threshold):
 t2=threshold*threshold;q=t2/_GRID if t2>0 else 1.0
 c={}
 for i,a in enumerate(left):
  for j,b in enumerate(right):
   d2=(a['x']-b['x'])**2+(a['y']-b['y'])**2
   if d2<=t2:c[(i,j)]=int(round(d2/q))
 return c

def brute(left,right,threshold):
 """枚举全部合法匹配，返回 (最优对数k, 最优量化总代价, 可配集合, 必然集合, 左点状态, 右点状态)"""
 n,m=len(left),len(right);cost=quantize(left,right,threshold)
 best=None;opts=[]
 def rec(i,used,pairs,total):
  nonlocal best,opts
  if i==n:
   key=(len(pairs),-total)   # 字典序：先对数最多，再总量化代价最小
   if best is None or key>best[0]:best=(key,total);opts=[set(pairs)]
   elif key==best[0]:opts.append(set(pairs))
   return
  rec(i+1,used,pairs,total)
  for j in range(m):
   if j not in used and (i,j) in cost:
    used.add(j);pairs.append((i,j))
    rec(i+1,used,pairs,total+cost[(i,j)])
    pairs.pop();used.discard(j)
 rec(0,set(),[],0)
 allowed=set().union(*opts);essential=set.intersection(*opts)
 def statuses(count,is_left):
  out=[]
  for v in range(count):
   if is_left:hit=[any((v,j) in o for j in range(m)) for o in opts]
   else:hit=[any((i,v) in o for i in range(n)) for o in opts]
   out.append('always_matched' if all(hit) else 'sometimes_matched' if any(hit) else 'never_matched')
  return out
 return best[0][0],best[1],allowed,essential,statuses(n,True),statuses(m,False)

def one(seed):
 rng=random.Random(seed)
 n=rng.randint(1,6);m=rng.randint(1,6)
 grid=[0.0,1.0,2.0,3.0]
 def pts(k):
  out=[]
  for t in range(k):
   if rng.random()<0.45:x,y=rng.choice(grid),rng.choice(grid)   # 重合坐标高发
   else:x,y=round(rng.uniform(0,3),rng.choice([0,1,3])),round(rng.uniform(0,3),rng.choice([0,1,3]))
   out.append({'point_id':f'P{t}','x':x,'y':y})
  return out
 left,right=pts(n),pts(m)
 threshold=rng.choice([0.0,0.5,1.0,1.5,2.5,10.0])
 result,_=reconcile_points(left,right,threshold,time.monotonic()+30)
 k,total,allowed,essential,ls,rs=brute(left,right,threshold)
 assert result['pair_count']==k,(seed,'pair_count',result['pair_count'],k)
 pair_map={(p['left_id'],p['right_id']):p for p in result['pairs']}
 want_allowed={(left[i]['point_id'],right[j]['point_id']) for i,j in allowed}
 want_essential={(left[i]['point_id'],right[j]['point_id']) for i,j in essential}
 assert set(pair_map)==want_allowed,(seed,'allowed',set(pair_map)^want_allowed)
 for key,p in pair_map.items():
  want='essential' if key in want_essential else 'ambiguous'
  assert p['status']==want,(seed,'pair status',key,p['status'],want)
 for side,points,want in (('left',left,ls),('right',right,rs)):
  got={p['point_id']:p['status'] for p in result['points'][side]}
  exp={p['point_id']:s for p,s in zip(points,want)}
  assert got==exp,(seed,side,'point status',got,exp)
 # 报告方案自身必为最优：对数与量化总代价一致
 cost=quantize(left,right,threshold)
 lid={p['point_id']:i for i,p in enumerate(left)};rid={p['point_id']:j for j,p in enumerate(right)}
 rep=[(lid[a],rid[b]) for (a,b),p in pair_map.items() if p['in_reported']]
 assert len(rep)==k and len(set(i for i,_ in rep))==len(rep) and len(set(j for _,j in rep))==len(rep)
 assert sum(cost[e] for e in rep)==total,(seed,'reported not optimal')

def determinism(seed):
 rng=random.Random(seed)
 left=[{'point_id':f'A{t}','x':round(rng.uniform(0,5),2),'y':round(rng.uniform(0,5),2)} for t in range(8)]
 right=[{'point_id':f'B{t}','x':round(rng.uniform(0,5),2),'y':round(rng.uniform(0,5),2)} for t in range(8)]
 d=time.monotonic()+30
 r1,_=reconcile_points(left,right,2.0,d);r2,_=reconcile_points(left,right,2.0,d)
 assert r1==r2,'non-deterministic result'

def coincident():
 """重合坐标：3左2右同坐标，各占名额；另1左孤立。"""
 left=[{'point_id':'L1','x':5.0,'y':5.0},{'point_id':'L2','x':5.0,'y':5.0},{'point_id':'L3','x':5.0,'y':5.0},{'point_id':'L4','x':99.0,'y':99.0}]
 right=[{'point_id':'R1','x':5.0,'y':5.0},{'point_id':'R2','x':5.0,'y':5.0}]
 r,_=reconcile_points(left,right,1.0,time.monotonic()+30)
 assert r['pair_count']==2
 assert len(r['pairs'])==6 and all(p['status']=='ambiguous' for p in r['pairs'])
 st={p['point_id']:p['status'] for p in r['points']['left']}
 assert st['L4']=='never_matched' and st['L1']=='sometimes_matched'
 st={p['point_id']:p['status'] for p in r['points']['right']}
 assert st['R1']=='always_matched' and st['R2']=='always_matched'

def timeout():
 left=[{'point_id':f'A{i}','x':float(i%17),'y':float(i%29)} for i in range(60)]
 right=[{'point_id':f'B{i}','x':float(i%17),'y':float(i%29)} for i in range(60)]
 try:
  reconcile_points(left,right,100.0,time.monotonic()-1)
  raise SystemExit('timeout not raised')
 except ReconcileTimeout:pass

def performance():
 rng=random.Random(7)
 left=[{'point_id':f'A{i}','x':rng.uniform(0,80),'y':rng.uniform(0,80)} for i in range(300)]
 right=[{'point_id':f'B{i}','x':rng.uniform(0,80),'y':rng.uniform(0,80)} for i in range(300)]
 t0=time.monotonic();r,_=reconcile_points(left,right,500.0,t0+10.0);dt=time.monotonic()-t0
 print(f'dense 300x300: {dt:.2f}s pairs={r["pair_count"]} allowed={len(r["pairs"])}')
 assert dt<10.0,'dense case exceeds 10s'

if __name__=='__main__':
 random.seed(20261114)
 seeds=[random.randint(0,10**9) for _ in range(400)]
 for s in seeds:one(s)
 print('brute-force x',len(seeds),'OK')
 determinism(3);determinism(4);print('determinism OK')
 coincident();print('coincident OK')
 timeout();print('timeout OK')
 performance();print('performance OK')
