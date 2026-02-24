from pydantic import BaseModel
from datetime import date
from typing import Optional

class ValidLogin(BaseModel):
    phone: str
    password: str
class Signup(BaseModel):
    phone: str
    password: str
    name: str
    birth: str
    gender: str
    imageUrl: Optional[str] = None

class PhoneReq(BaseModel):
    phone: str

class VerifyReq(BaseModel):
    phone: str
    code: str