from pydantic import BaseModel, field_serializer
from datetime import time, datetime


# === 매장코드 검증 스키마 === #
class VerifyCode(BaseModel):
    code: str

# === 직원 가입신청 스키마 === #
class MemberRequestSchemas(BaseModel):
    store_id: int
    bank: str
    accountName: str
    accountNumber: str

# 근무일정 조회 스키마
class WorkRequest(BaseModel):
    employee_id: int

class WrokResponse(BaseModel):
    # day_of_week: int
    work_start: time
    work_end: time

    @field_serializer('work_start', 'work_end')
    def serialize_time(self, v: time):
        return v.strftime("%H:%M") # "10:30:00" -> "10:30"

    class Config:
        from_attributes = True
    

# 체크리스트 조회 요청용 스키마
class TodoListRequest(BaseModel):
    store_id: int

# 체크리스트 조회 응답용 스키마
class TodoListResponse(BaseModel):
    id: int
    content: str
    is_achieved: bool

    class Config:
        from_attributes = True

# 체크리스트 상태변경 요청용 스키마
class TodoListModifyRequest(TodoListRequest):
    id: int

class NoticeResponse(BaseModel):
    writer: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True