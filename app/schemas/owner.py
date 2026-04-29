from pydantic import BaseModel, field_serializer
from datetime import time, datetime
from typing import Optional

class setStoreInfoSchemas(BaseModel):
    id: int
    name: str
    address: str
    addressDetail: Optional[str] = None
    industry: str
    owner: str
    number: str