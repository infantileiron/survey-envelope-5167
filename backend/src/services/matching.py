"""两点组记录对账：字典序最优配对与全最优方案配对分类。

目标：给定距离上限，每点最多配一次，先使配对数最多，再使总平方距离最小。
方法：平方距离量化为 int64 后，用平衡匈牙利（左点+虚行 × 右点+虚列，虚边代价
D 满足 2D 大于任何匹配的真实量化总代价，从而编码字典序）求一个最优方案与最优
对偶；再在等边子图上做 Dulmage-Mendelsohn 分解，给出能出现在任一最优方案中的
全部配对，并区分必然配对、归属歧义与始终未配点。代价非负，全部算术为 int64
精确运算，不使用浮点容差。
"""
import math,time,hashlib,json
import numpy as np

TIME_LIMIT_S=10.0      # 计算硬上限，超时整份拒绝
_INF=1<<60             # 禁止配对的代价，远大于任何有限总代价（<=600*2*D≈2e17）
_GRID=1<<40            # 平方距离量化：阈值² 对应 2^40 个整数单位

class ReconcileTimeout(Exception):pass

def _check(deadline):
 if time.monotonic()>deadline:raise ReconcileTimeout('对账计算超过10秒上限，整份结果已拒绝')

def _hungarian(cost,deadline):
 """方阵最小代价完美分配。cost (N,N) int64 非负，返回 (row_to_col (N,), u (N,), v (N,))。
 u[i]+v[j]<=cost[i,j] 对所有边成立，匹配边取等号（最优对偶）。"""
 N=cost.shape[0]
 u=np.zeros(N+1,np.int64);v=np.zeros(N+1,np.int64)
 match=np.zeros(N+1,np.int64);way=np.zeros(N+1,np.int64)
 for i in range(1,N+1):
  _check(deadline)
  match[0]=i;j0=0
  minv=np.full(N+1,_INF,np.int64);used=np.zeros(N+1,bool)
  while True:
   used[j0]=True;i0=match[j0]
   cur=cost[i0-1]-u[i0]-v[1:]
   tail=minv[1:];free=~used[1:]
   upd=free&(cur<tail)
   tail[upd]=cur[upd]
   w=way[1:];w[upd]=j0
   j0=int(np.argmin(np.where(used[1:],_INF,minv[1:])))+1
   delta=int(minv[j0])
   idx=np.nonzero(used)[0]
   u[match[idx]]+=delta
   v[idx]-=delta
   minv-=delta
   if match[j0]==0:break
  while j0:
   j1=way[j0];match[j0]=match[j1];j0=j1
 row_to_col=np.full(N,-1,np.int64)
 for j in range(1,N+1):
  if match[j]:row_to_col[match[j]-1]=j-1
 return row_to_col,u[1:],v[1:]

def _scc(adj,deadline):
 """Kosaraju 强连通分量，返回每个节点的分量编号。adj 为前向邻接表。"""
 N=len(adj);rev=[[] for _ in range(N)]
 for a in range(N):
  for b in adj[a]:rev[b].append(a)
 seen=[False]*N;order=[]
 for s in range(N):
  if seen[s]:continue
  seen[s]=True;stack=[(s,0)]
  while stack:
   node,ci=stack[-1]
   if ci<len(adj[node]):
    stack[-1]=(node,ci+1);nxt=adj[node][ci]
    if not seen[nxt]:seen[nxt]=True;stack.append((nxt,0))
   else:order.append(node);stack.pop()
 _check(deadline)
 comp=[-1]*N;label=0
 for s in reversed(order):
  if comp[s]>=0:continue
  comp[s]=label;stack=[s]
  while stack:
   node=stack.pop()
   for nxt in rev[node]:
    if comp[nxt]<0:comp[nxt]=label;stack.append(nxt)
  label+=1
 return comp

def reconcile_points(left,right,threshold_m,deadline):
 """left/right 为 [{point_id,x,y}...] 原始记录（不去重，重合坐标各占名额）。
 返回 (result, summary)；超时抛 ReconcileTimeout，不返回任何部分结果。"""
 n,m=len(left),len(right);N=n+m
 t2=threshold_m*threshold_m
 # 共同局部原点平移，避免大绝对坐标相减抵消（与面积口径一致）
 ox=min([p['x'] for p in left]+[p['x'] for p in right])
 oy=min([p['y'] for p in left]+[p['y'] for p in right])
 ax=np.array([p['x']-ox for p in left]);ay=np.array([p['y']-oy for p in left])
 bx=np.array([p['x']-ox for p in right]);by=np.array([p['y']-oy for p in right])
 d2=(ax[:,None]-bx[None,:])**2+(ay[:,None]-by[None,:])**2
 within=d2<=t2
 _check(deadline)
 # 量化：阈值² 映射到 2^40 整数单位，int64 精确比较
 q=t2/_GRID if t2>0 else 1.0
 cint=np.where(within,np.rint(d2/q),0.0).astype(np.int64)
 D=(min(n,m)<<39)+1     # 虚边代价：2D 大于任何匹配的真实量化总代价，编码字典序
 cost=np.zeros((N,N),np.int64)
 cost[:n,:m]=np.where(within,cint,_INF)  # 真实候选边
 cost[:n,m:]=D                            # 左点 × 虚列：左点不配
 cost[n:,:m]=D                            # 虚行 × 右点：右点不配
 cost[n:,m:]=0                            # 虚行 × 虚列
 row_to_col,u,v=_hungarian(cost,deadline)
 _check(deadline)
 # 等边子图：u[i]+v[j]==cost[i,j] 的边；最优方案恰好是等边子图的完美匹配
 tight=(cost==(u[:,None]+v[None,:]))&(cost<_INF)
 # Dulmage-Mendelsohn：匹配边列->行，未匹配紧边行->列，求强连通分量
 matched=np.zeros((N,N),bool)
 matched[np.arange(N),row_to_col]=True
 adj=[[] for _ in range(2*N)]
 ti,tj=np.nonzero(tight)
 for a,b in zip(ti.tolist(),tj.tolist()):
  if matched[a,b]:adj[N+b].append(a)
  else:adj[a].append(N+b)
 comp=np.array(_scc(adj,deadline))
 _check(deadline)
 # 可出现在某一最优方案的边：匹配边，或两端同分量的紧边
 same=comp[:N,None]==comp[N:][None,:]
 allowed_edge=matched|(tight&same)
 # 必然配对：匹配边且两端不同分量（不在任何交错环上）
 essential=matched&~same
 # 真实配对分类
 real_allowed=allowed_edge[:n,:m]&within
 real_essential=essential[:n,:m]&within
 reported_real=[(i,int(row_to_col[i])) for i in range(n) if row_to_col[i]<m]
 reported_set=set(reported_real)
 k=len(reported_real)
 total_d2=math.fsum(float(d2[i,j]) for i,j in reported_real)
 _check(deadline)
 # 点状态：左侧行可到虚列、右侧列可到虚行，即“可在某最优方案中不配”
 left_dummy_allowed=(allowed_edge[:n,m:]).any(axis=1)
 right_dummy_allowed=(allowed_edge[n:,:m]).any(axis=0)
 left_real_allowed=real_allowed.any(axis=1)
 right_real_allowed=real_allowed.any(axis=0)
 def point_status(real_in_reported,essential_in_reported,real_allowed_any,dummy_allowed_any):
  if real_in_reported:
   if essential_in_reported:return 'always_matched'
   return 'sometimes_matched' if dummy_allowed_any else 'always_matched'
  return 'sometimes_matched' if real_allowed_any else 'never_matched'
 right_in_reported={j:i for i,j in reported_real}
 left_points=[];right_points=[]
 for i,p in enumerate(left):
  real_in=int(row_to_col[i])<m
  ess=real_in and bool(real_essential[i,row_to_col[i]])
  partners=[right[j]['point_id'] for j in np.nonzero(real_allowed[i])[0]]
  left_points.append({'point_id':p['point_id'],'x':p['x'],'y':p['y'],'status':point_status(real_in,ess,bool(left_real_allowed[i]),bool(left_dummy_allowed[i])),'partners':partners})
 for j,p in enumerate(right):
  real_in=j in right_in_reported
  ess=real_in and bool(real_essential[right_in_reported[j],j])
  partners=[left[i]['point_id'] for i in np.nonzero(real_allowed[:,j])[0]]
  right_points.append({'point_id':p['point_id'],'x':p['x'],'y':p['y'],'status':point_status(real_in,ess,bool(right_real_allowed[j]),bool(right_dummy_allowed[j])),'partners':partners})
 _check(deadline)
 pairs=[]
 for i,j in zip(*np.nonzero(real_allowed)):
  i,j=int(i),int(j)
  pairs.append({'left_id':left[i]['point_id'],'right_id':right[j]['point_id'],'distance_m':math.sqrt(float(d2[i,j])),'squared_distance':float(d2[i,j]),'status':'essential' if real_essential[i,j] else 'ambiguous','in_reported':(i,j) in reported_set})
 pairs.sort(key=lambda r:(0 if r['status']=='essential' else 1,r['left_id'],r['right_id']))
 def tally(points):
  return {s:sum(1 for p in points if p['status']==s) for s in ('always_matched','sometimes_matched','never_matched')}
 lc,rc=tally(left_points),tally(right_points)
 result={'threshold_m':threshold_m,'coordinate_system':'local_m','candidate_pair_count':int(within.sum()),'pair_count':k,'total_squared_distance':total_d2,'essential_pair_count':int(real_essential.sum()),'ambiguous_pair_count':int(real_allowed.sum()-real_essential.sum()),'left_counts':lc,'right_counts':rc,'pairs':pairs,'points':{'left':left_points,'right':right_points}}
 summary={'pair_count':k,'candidate_pair_count':int(within.sum()),'essential_pair_count':result['essential_pair_count'],'ambiguous_pair_count':result['ambiguous_pair_count'],'left_counts':lc,'right_counts':rc}
 return result,summary

ASSUMPTIONS=['候选配对按原始float64平方距离≤阈值²判定；计算前双方坐标平移到共同局部原点，避免大绝对坐标抵消，与面积口径一致。','字典序目标：先配对数最多，再总平方距离最小；虚边代价D满足2D大于任何匹配的真实量化总代价，因此不会因代价牺牲配对数。','平方距离按阈值²·2^-40网格量化为int64后精确比较，网格内视为同距并列；并列不人为就近抢占，全部进入归属歧义。','每个点最多配一次；重合坐标不去重，按原始编号各占一个名额，同坐标点之间为并列歧义。','必然配对=出现在全部最优方案；归属歧义=出现在部分而非全部最优方案；始终未配=任何最优方案都不配对；分类来自等边子图的Dulmage-Mendelsohn分解。','计算超过10秒整份拒绝，不保存部分结果；对账只读原始测组，快照冻结双方来源、阈值与算法口径，不回写测组。']

def run_reconciliation(snapshot):
 """对冻结快照执行对账，返回带校验和的完整结果与列表摘要。
 校验和只覆盖快照与确定性输出；计时信息在校验和之外。"""
 started=time.monotonic();deadline=started+TIME_LIMIT_S
 left=snapshot['left']['group']['points'];right=snapshot['right']['group']['points']
 result,summary=reconcile_points(left,right,snapshot['threshold_m'],deadline)
 elapsed=round((time.monotonic()-started)*1000,3)
 result['left']={k:snapshot['left'][k] for k in ('survey_id','survey_name','source','group_id','group_name')}
 result['right']={k:snapshot['right'][k] for k in ('survey_id','survey_name','source','group_id','group_name')}
 result['assumptions']=ASSUMPTIONS
 payload={'snapshot':snapshot,'result':result}
 result['checksum']=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
 result['timing_ms']=elapsed;result['deadline_ms']=int(TIME_LIMIT_S*1000)
 summary['timing_ms']=elapsed;summary['checksum']=result['checksum']
 return result,summary
