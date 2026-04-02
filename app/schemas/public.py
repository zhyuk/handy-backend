from pydantic import BaseModel

# === 매장코드 검증 스키마 === #
class add(BaseModel):
    code: str

# ===  === #