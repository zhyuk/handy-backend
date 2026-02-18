from pydantic import BaseModel

class PushReq(BaseModel):
    token: str
    value: int
