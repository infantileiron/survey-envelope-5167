from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from src.config.database import db_session
from src.controllers.auth import current_user,writer
from src.models import Reconciliation
from src.schemas.reconciliation import ReconciliationInput
from src.services import reconciliations as service
from src.utils.serialization import serialize
router=APIRouter(prefix='/reconciliations')
@router.get('')
def listing(db=Depends(db_session),user=Depends(current_user)):return [service.listed(r) for r in db.scalars(select(Reconciliation).order_by(Reconciliation.created_at.desc()))]
@router.post('')
def create(payload:ReconciliationInput,db=Depends(db_session),user=Depends(writer)):return service.create(db,payload)
@router.get('/{id}')
def detail(id:str,db=Depends(db_session),user=Depends(current_user)):
 item=db.get(Reconciliation,id)
 if not item:raise HTTPException(404,'对账不存在')
 return serialize(item)
