"""服务端集成冒烟：SQLite 内存库 + 假 Redis，验证对账服务层与快照冻结。

用法：PYTHONPATH=/workspace/backend python3 test_service.py
"""
import os,sys,types
os.environ['DATABASE_URL']='sqlite:///:memory:'
os.environ['SEED_DEMO']='false'

# 假 Redis：记录入队，不真正连接
class FakeRedis:
 def __init__(self):self.queues={}
 def lpush(self,k,v):self.queues.setdefault(k,[]).append(v);return 1
 def brpop(self,keys,timeout=1):return None
 @classmethod
 def from_url(cls,url):return cls()
import redis
redis.Redis=FakeRedis

from src.config.database import Base,engine,Session
from src.models import PointSurvey,Reconciliation
from src.schemas.reconciliation import ReconciliationInput
from src.services import reconciliations as svc
from src.services.matching import run_reconciliation
from src.utils.time import now

# SQLite 不编译 LONGTEXT；按模型列名手工建表（运行期 PreciseJSON 即 TEXT 读写）
with engine.begin() as c:
 c.exec_driver_sql('CREATE TABLE point_surveys (id VARCHAR(80) PRIMARY KEY,name VARCHAR(160),source VARCHAR(180),coordinate_system VARCHAR(32),groups TEXT,created_at VARCHAR(64))')
 c.exec_driver_sql('CREATE TABLE reconciliations (id VARCHAR(80) PRIMARY KEY,name VARCHAR(160),left_survey_id VARCHAR(80),left_group_id VARCHAR(32),right_survey_id VARCHAR(80),right_group_id VARCHAR(32),threshold_m DOUBLE,snapshot TEXT,status VARCHAR(32),summary TEXT,result TEXT,error TEXT,created_at VARCHAR(64))')
db=Session()
def mk_survey(id,groups):
 s=PointSurvey(id=id,name=id+'-name',source=id+'.json',coordinate_system='local_m',groups=groups,created_at=now())
 db.add(s);db.commit();return s
g1={'group_id':'G1','name':'左组','points':[{'point_id':f'L{i}','x':float(i%5),'y':float(i%3)} for i in range(20)]}
g2={'group_id':'G2','name':'右组','points':[{'point_id':f'R{i}','x':float(i%5)+0.1,'y':float(i%3)} for i in range(22)]}
mk_survey('sv-a',[g1]);mk_survey('sv-b',[g2])

# 正常创建：双方来源与阈值冻结，原测组不被修改
payload=ReconciliationInput(name='冒烟对账',left={'survey_id':'sv-a','group_id':'G1'},right={'survey_id':'sv-b','group_id':'G2'},threshold_m=0.4)
created=svc.create(db,payload)
assert created['status']=='queued' and created['threshold_m']==0.4
snap=created['snapshot']
assert snap['left']['survey_name']=='sv-a-name' and snap['right']['group_id']=='G2'
assert len(snap['left']['group']['points'])==20 and len(snap['right']['group']['points'])==22
assert db.get(PointSurvey,'sv-a').groups[0]['group_id']=='G1'  # 原测组未改

# 重名 409、缺测组 404、缺点组 422
from fastapi import HTTPException
for bad,code in [(ReconciliationInput(name='冒烟对账',left={'survey_id':'sv-a','group_id':'G1'},right={'survey_id':'sv-b','group_id':'G2'},threshold_m=0.4),409),(ReconciliationInput(name='新对账甲',left={'survey_id':'none','group_id':'G1'},right={'survey_id':'sv-b','group_id':'G2'},threshold_m=0.4),404),(ReconciliationInput(name='新对账乙',left={'survey_id':'sv-a','group_id':'GX'},right={'survey_id':'sv-b','group_id':'G2'},threshold_m=0.4),422)]:
 try:svc.create(db,bad);raise SystemExit(f'should raise {code}')
 except HTTPException as e:assert e.status_code==code,(e.status_code,code)

# 阈值校验：0/负数/inf 被 schema 拒绝
from pydantic import ValidationError
for t in (0.0,-1.0,float('inf'),float('nan')):
 try:ReconciliationInput(name='坏阈值',left={'survey_id':'a','group_id':'g'},right={'survey_id':'b','group_id':'g'},threshold_m=t);raise SystemExit(f'threshold {t} accepted')
 except ValidationError:pass

# 工作进程路径：queued -> completed，结果与摘要落库
item=db.get(Reconciliation,created['id'])
item.status='running'
result,summary=run_reconciliation(item.snapshot)
item.result=result;item.summary=summary;item.status='completed';db.commit()
assert item.result['pair_count']>0 and item.summary['pair_count']==item.result['pair_count']
assert item.result['left']['survey_id']=='sv-a' and item.result['right']['survey_id']=='sv-b'
assert item.result['checksum'] and len(item.result['pairs'])>=item.result['essential_pair_count']
# 列表摘要不含完整结果
listed=svc.listed(item)
assert 'result' not in listed and listed['summary']['pair_count']==item.result['pair_count']
print('service integration OK: pairs',item.result['pair_count'],'essential',item.result['essential_pair_count'],'ambiguous',item.result['ambiguous_pair_count'])
