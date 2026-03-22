from pydantic import BaseModel
from fastapi import APIRouter, UploadFile, File, Form
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
# ===== 애플 콜백 스키마 ===== #
class AppleCallbackRequest(BaseModel):
    code: str
    id_token: str = None
# ===== 애플 콜백 스키마 ===== #

# ===== 사장 유형 ===== #
class StoreInfo(BaseModel):
    """ 매장정보 추가하는 스키마 """
    storeName: str = Form(...)
    address: str = Form(...)
    addressDetail: str | None = Form(None)
    businessType: str = Form(...)
    ownerName: str = Form(...)
    ownerPhone: str = Form(...)
    file: UploadFile = File(...)
# ===== 사장 유형 ===== #

# ===== 직원 유형 ===== #
# ===== 직원 유형 ===== #