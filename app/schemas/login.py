from pydantic import BaseModel
from datetime import date
from typing import Optional

class ValidLogin(BaseModel):
    phone: str
    password: str
class Signup(BaseModel):
    phone: str
    password: Optional[str] = None
    name: str
    birth: str
    gender: str
    imageUrl: Optional[str] = None
    type: str

class PhoneReq(BaseModel):
    phone: str

class VerifyReq(BaseModel):
    phone: str
    code: str