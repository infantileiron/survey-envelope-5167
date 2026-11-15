from pathlib import Path
import redis,traceback
from sqlalchemy import select
from src.config.settings import REDIS_URL
from src.config.database import Session
from src.models import EnvelopeRun,EnvelopeStudy,Reconciliation
from src.services.analysis import analyze
from src.services.matching import run_reconciliation,ReconcileTimeout
client=redis.Redis.from_url(REDIS_URL);heartbeat=Path('/artifacts/worker-heartbeat')
def execute(id):
 with Session() as db:
  run=db.get(EnvelopeRun,id)
  if not run or run.status not in ('queued','running'):return
  run.status='running';db.commit()
  try:
   study=db.get(EnvelopeStudy,run.study_id);run.result=analyze(study.snapshot,study.group_ids);run.status='completed'
  except Exception as e:run.error=str(e);run.status='failed';traceback.print_exc()
  db.commit()
def execute_reconciliation(id):
 with Session() as db:
  item=db.get(Reconciliation,id)
  if not item or item.status not in ('queued','running'):return
  item.status='running';db.commit()
  try:
   item.result,item.summary=run_reconciliation(item.snapshot);item.status='completed'
  except ReconcileTimeout as e:item.error=str(e);item.status='failed'
  except Exception as e:item.error=str(e);item.status='failed';traceback.print_exc()
  db.commit()
with Session() as db:
 for id in db.scalars(select(EnvelopeRun.id).where(EnvelopeRun.status.in_(['queued','running']))):client.lpush('survey-envelope:jobs',id)
 for id in db.scalars(select(Reconciliation.id).where(Reconciliation.status.in_(['queued','running']))):client.lpush('survey-envelope:reconciliations',id)
while True:
 heartbeat.touch();job=client.brpop(['survey-envelope:jobs','survey-envelope:reconciliations'],timeout=1)
 if job:
  queue,id=job[0].decode(),job[1].decode()
  if queue=='survey-envelope:reconciliations':execute_reconciliation(id)
  else:execute(id)
