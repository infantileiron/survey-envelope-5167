from sqlalchemy import String,Double,Text
from sqlalchemy.orm import Mapped,mapped_column
from src.config.database import Base
from src.config.json_type import PreciseJSON as JSON
class Reconciliation(Base):
 __tablename__='reconciliations'
 id:Mapped[str]=mapped_column(String(80),primary_key=True)
 name:Mapped[str]=mapped_column(String(160),unique=True)
 left_survey_id:Mapped[str]=mapped_column(String(80))
 left_group_id:Mapped[str]=mapped_column(String(32))
 right_survey_id:Mapped[str]=mapped_column(String(80))
 right_group_id:Mapped[str]=mapped_column(String(32))
 threshold_m:Mapped[float]=mapped_column(Double)
 snapshot:Mapped[dict]=mapped_column(JSON)
 status:Mapped[str]=mapped_column(String(32))
 summary:Mapped[dict]=mapped_column(JSON,default=dict)
 result:Mapped[dict]=mapped_column(JSON,default=dict)
 error:Mapped[str]=mapped_column(Text,default='')
 created_at:Mapped[str]=mapped_column(String(64))
