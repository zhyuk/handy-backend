from pydantic import BaseModel

# === 매장코드 검증 스키마 === #
class VerifyCode(BaseModel):
    code: str

# === 직원 가입신청 스키마 === #
class MemberRequestSchemas(BaseModel):
    store_id: int
    bank: str
    accountName: str
    accountNumber: str