from pydantic import BaseModel,Field,ConfigDict
class SideInput(BaseModel):
 model_config=ConfigDict(extra='forbid')
 survey_id:str=Field(min_length=1,max_length=80)
 group_id:str=Field(min_length=1,max_length=32)
class ReconciliationInput(BaseModel):
 model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
 name:str=Field(min_length=2,max_length=160)
 left:SideInput
 right:SideInput
 threshold_m:float=Field(gt=0,le=1e10)
