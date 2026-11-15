import uuid,redis
from fastapi import HTTPException
from sqlalchemy import select
from src.models import PointSurvey,Reconciliation
from src.config.settings import REDIS_URL
from src.utils.serialization import serialize
from src.utils.time import now

def _side(db,ref):
 survey=db.get(PointSurvey,ref.survey_id)
 if not survey:raise HTTPException(404,'足迹测组不存在：'+ref.survey_id)
 group=next((g for g in survey.groups if g['group_id']==ref.group_id),None)
 if not group:raise HTTPException(422,'点组不存在于测组：'+ref.group_id)
 return {'survey_id':survey.id,'survey_name':survey.name,'source':survey.source,'coordinate_system':survey.coordinate_system,'group_id':group['group_id'],'group_name':group['name'],'group':group}

def create(db,payload):
 left=_side(db,payload.left);right=_side(db,payload.right)
 if db.scalar(select(Reconciliation).where(Reconciliation.name==payload.name)):raise HTTPException(409,'对账名称已存在')
 snapshot={'left':left,'right':right,'threshold_m':payload.threshold_m}
 item=Reconciliation(id=str(uuid.uuid4()),name=payload.name,left_survey_id=left['survey_id'],left_group_id=left['group_id'],right_survey_id=right['survey_id'],right_group_id=right['group_id'],threshold_m=payload.threshold_m,snapshot=snapshot,status='queued',summary={},result={},error='',created_at=now())
 db.add(item);db.commit()
 try:redis.Redis.from_url(REDIS_URL).lpush('survey-envelope:reconciliations',item.id)
 except redis.RedisError:
  item.status='failed';item.error='队列不可用，请重试';db.commit();raise HTTPException(503,item.error)
 return serialize(item)

def listed(row):
 data=serialize(row);data.pop('result');return data
