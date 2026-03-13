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


# ===== 사장 유형 ===== #
class StoreInfo(BaseModel):
    """ 매장정보 추가하는 스키마 """
    storeName: str
    address: str
    addressDetail: Optional[str] = None
    businessType: str
    ownerName: str
    ownerPhone: str
# ===== 사장 유형 ===== #

# ===== 직원 유형 ===== #
# ===== 직원 유형 ===== #