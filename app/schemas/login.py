from pydantic import BaseModel
from datetime import date

class ValidLogin(BaseModel):
    phone: str
    password: str

class Signup(ValidLogin):
    name: str
    birth: date
    gender: str

class PhoneReq(BaseModel):
    phone: str

class VerifyReq(BaseModel):
    phone: str
    code: str