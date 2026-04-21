from pydantic import BaseModel, field_serializer
from datetime import time, datetime
from typing import List, Optional


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
# class WorkRequest(BaseModel):
#     employee_id: int

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
    # employee_id: int

# 체크리스트 조회 응답용 스키마
class TodoListResponse(BaseModel):
    id: int
    content: str
    is_achieved: bool

    class Config:
        from_attributes = True

# 체크리스트 상태변경 요청용 스키마
class TodoListModifyRequest(BaseModel):
    store_id: int
    id: int

class NoticeRequestSchemas(BaseModel):
    store_id: int

class NoticeResponse(BaseModel):
    id: int
    writer: str
    title: str
    created_at: datetime

    class Config:
        from_attributes = True

class WeeklyWorkRequest(BaseModel):
    store_id: int
    # employee_id: int

class WeeklyWorkResponse(BaseModel):
    day_of_week: int
    work_start: time
    work_end: time

    class Config:
        from_attributes = True

    
class MonthlyScheduleRequest(BaseModel):
    store_id: int
    # employee_id: int
    month: int


class ClosingReportRequest(BaseModel):
    store_id: int
    # employee_id: int
    card_sales: int
    cash_sales: int
    transfer_sales: int
    gift_sales: int
    discount_amount: int
    refund_amount: int
    cash_on_hand: int
    cash_shortage_type: Optional[str]
    cash_shortage_amount: int
    receipt_image_url: Optional[str]
    manager_note: str
    report_date: str


class MyInfoModifyRequest(BaseModel):
    name: str
    bank: str
    accountNumber: str
    resume: Optional[str] = None
    employment_contract: Optional[str] = None
    health_certificate: Optional[str] = None

# ===== 근태 관리 전용 스키마 ===== #
class WorkTimeRequest(BaseModel):
    store_id: int    

# ===== 출근 기록 조회 스키마 ===== #
class WorkMonthRequest(BaseModel):
    # employee_id: int
    store_id: int
    year: int
    month: int

# ===== 출근 기록 수정 요청 스키마 ===== #
class WorkChangeRequest(BaseModel):
    store_id: int
    # employee_id: int
    type: str
    date: str
    origin_start: Optional[str] = None
    origin_end: Optional[str] = None
    desired_start: Optional[str] = None
    desired_end: Optional[str] = None
    desired_break: Optional[str] = None
    reason: str

# ===== 출근 기록 수정내역 조회 스키마 ===== #
class WorkChangeRequestLogSchemas(BaseModel):
    store_id: int
    # employee_id: int