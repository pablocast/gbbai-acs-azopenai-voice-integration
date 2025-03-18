from pydantic import BaseModel
from typing import Union

class OutboundCallPayloadModel(BaseModel):
    """Payload model for outbound call route"""
    phone_number: str
    candidate_name: str
    candidate_data: Union[dict, str]
    job_data: Union[dict, str]
