from sqlalchemy import Column, Integer, BigInteger, String, Text, Boolean, DateTime, ForeignKey, func, Date, UniqueConstraint, Numeric, Time, JSON, Enum
from sqlalchemy.orm import relationship
from database import Base
import enum


# ==========================================
# 1. 사용자 및 계정 관련
# ==========================================
class Member(Base):
    __tablename__ = "members"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    password = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True, unique=True)
    name = Column(String(100), nullable=True)
    birth = Column(Date, nullable=True)
    gender = Column(String(10), nullable=True)
    image_url = Column(String(255), default="default.png")
    is_deleted = Column(Boolean, default=False)

    # Relationships
    social_accounts = relationship("SocialAccount", back_populates="member", cascade="all, delete-orphan")
    tokens = relationship("JwtTokens", back_populates="member", cascade="all, delete-orphan")
    members_for_storeMembers = relationship("StoreMembers", back_populates="member", cascade="all, delete-orphan")
    member_requests = relationship("MemberRequest", back_populates="member", cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="member", cascade="all, delete-orphan")

class SocialAccount(Base):
    __tablename__ = "social_accounts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    member_id = Column(BigInteger, ForeignKey("members.id"))
    provider = Column(String(20), nullable=False)   # google/kakao/apple
    provider_id = Column(String(255), nullable=False)

    __table_args__ = (UniqueConstraint("provider", "provider_id"),)
    member = relationship("Member", back_populates="social_accounts")

class JwtTokens(Base):
    __tablename__ = "jwt_tokens"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    member_id = Column(BigInteger, ForeignKey("members.id"))
    refresh_token = Column(String(512))
    expires_at = Column(DateTime, nullable=True)
    is_revoked = Column(Boolean, server_default="false")
    created_at = Column(DateTime, server_default=func.now())

    member = relationship("Member", back_populates="tokens")

# ==========================================
# 2. 매장 및 지도 관련
# ==========================================
class Store(Base):
    __tablename__ = "stores"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(BigInteger, unique=True)
    name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=False)
    addressDetail = Column(String(255), nullable=True)
    industry = Column(String(100), nullable=False)
    owner = Column(String(100), nullable=False)
    number = Column(String(20), nullable=False)
    image = Column(Text, nullable=False)
    radius = Column(Integer, nullable=True)

    # Relationships
    map_info = relationship("StoreMap", back_populates="store", cascade="all, delete-orphan")
    stores_for_storeMembers = relationship("StoreMembers", back_populates="store", cascade="all, delete-orphan")
    member_requests = relationship("MemberRequest", back_populates="store", cascade="all, delete-orphan")
    community_posts = relationship("StoreCommunity", back_populates="store", cascade="all, delete-orphan")
    all_todos = relationship("StoreMembersTodo", back_populates="store", cascade="all, delete-orphan")
    closing_reports = relationship("DailyClosingReport", back_populates="store", cascade="all, delete-orphan")
    change_requests = relationship("WorkLogChangeRequest", back_populates="store", cascade="all, delete-orphan")

class StoreMap(Base):
    __tablename__ = "store_maps"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    store_id = Column(BigInteger, ForeignKey("stores.id"), nullable=False)
    lat = Column(Numeric(precision=10, scale=7), nullable=False)
    lng = Column(Numeric(precision=11, scale=7), nullable=False)

    store = relationship("Store", back_populates="map_info")

class StorePart(Base):
    __tablename__ = "store_parts"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    store_id = Column(BigInteger, ForeignKey("stores.id"), nullable=False)
    name = Column(String(20), nullable=False)   # "오픈", "미들", "마감"
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
# ==========================================
# 3. 가입 및 승인 프로세스
# ==========================================
class BusinessRequest(Base):
    __tablename__ = "business_requests"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=False)
    addressDetail = Column(String(255), nullable=True)
    industry = Column(String(100), nullable=False)
    owner = Column(String(100), nullable=False)
    number = Column(String(20), nullable=False)
    image = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    is_checked = Column(Boolean, default=False)
    checked_time = Column(DateTime, onupdate=func.now())
    reject_reason = Column(Text)

class MemberRequest(Base):
    __tablename__ = "member_requests"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    store_id = Column(BigInteger, ForeignKey("stores.id"), nullable=False)
    member_id = Column(BigInteger, ForeignKey("members.id"), nullable=False)
    bank = Column(String(50))
    accountName = Column(String(100))
    accountNumber = Column(String(100))
    status = Column(String(10), server_default="pending")
    created_at = Column(DateTime, server_default=func.now())

    store = relationship("Store", back_populates="member_requests")
    member = relationship("Member", back_populates="member_requests")

# ==========================================
# 4. 소속 직원 및 상세 관리
# ==========================================
class StoreMembers(Base):
    __tablename__ = "store_members"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    store_id = Column(BigInteger, ForeignKey("stores.id"), nullable=False)
    member_id = Column(BigInteger, ForeignKey("members.id"), nullable=False)
    role = Column(String(10), server_default="employee")
    bank = Column(String(50), nullable=True)
    accountNumber = Column(String(100), nullable=True)
    image_url = Column(String(500), nullable=True)
    joined_at = Column(DateTime, server_default=func.now())

    # 기본 관계
    member = relationship("Member", back_populates="members_for_storeMembers")
    store = relationship("Store", back_populates="stores_for_storeMembers")
    
    # 직원 상세 및 업무 데이터
    detail = relationship("StoreMembersDetail", back_populates="store_member", uselist=False, cascade="all, delete-orphan")
    todos = relationship("StoreMembersTodo", back_populates="employee", cascade="all, delete-orphan")
    work_schedules = relationship("StoreMembersWork", back_populates="employee", cascade="all, delete-orphan")
    work_logs = relationship("StoreMembersWorkLog", back_populates="employee", cascade="all, delete-orphan")
    schedule_requests = relationship("ScheduleChangeRequest", back_populates="employee", cascade="all, delete-orphan")
    
    # 커뮤니티 활동 (작성한 글/댓글)
    community_posts = relationship("StoreCommunity", back_populates="author")
    comments = relationship("StoreCommunityComment", back_populates="author")

    closing_reports = relationship("DailyClosingReport", back_populates="employee", cascade="all, delete-orphan")
    work_log_requests = relationship("WorkLogChangeRequest", back_populates="employee", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="employee", cascade="all, delete-orphan")

class StoreMembersDetail(Base):
    __tablename__ = "store_members_detail"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    store_member_id = Column(BigInteger, ForeignKey("store_members.id"), nullable=False)
    employee_type = Column(String(20))
    salary_cycle = Column(String(10))
    salary_day = Column(String(20))
    hourly_rate = Column(Integer)
    is_probation = Column(Boolean, server_default="false")
    income_tax = Column(Numeric(8, 4))
    local_income_tax = Column(Numeric(8, 4))
    national_pension_tax = Column(Numeric(8, 4))
    health_insurance_tax = Column(Numeric(8, 4))
    long_term_care_tax = Column(Numeric(8, 4))
    employment_insurance_tax = Column(Numeric(8, 4))
    industrial_accident_tax = Column(Numeric(8, 4))
    memo = Column(Text)
    resume = Column(String(255))
    employment_contract = Column(String(255))
    health_certificate = Column(String(255))
    working_status = Column(String(10), server_default="재직")

    store_member = relationship("StoreMembers", back_populates="detail")

# ==========================================
# 5. 근태 및 업무 관련
# ==========================================
class StoreMembersTodo(Base):
    __tablename__ = "store_members_todo"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    store_id = Column(BigInteger, ForeignKey("stores.id"), nullable=False)
    employee_id = Column(BigInteger, ForeignKey("store_members.id"), nullable=True)
    type = Column(String(30), nullable=False, comment="공통 / 개인")
    content = Column(String(100), nullable=False)
    created_at = Column(Date, server_default=func.now())
    is_achieved = Column(Boolean, server_default="false")

    store = relationship("Store", back_populates="all_todos")
    employee = relationship("StoreMembers", back_populates="todos")

class StoreMembersWork(Base):
    __tablename__ = "store_members_work"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    store_id = Column(BigInteger, ForeignKey("stores.id"), nullable=False)
    employee_id = Column(BigInteger, ForeignKey("store_members.id"), nullable=False)
    part_id = Column(BigInteger, ForeignKey("store_parts.id"), nullable=True)
    work_date = Column(Date, nullable=False)
    work_start = Column(Time, nullable=True)
    work_end = Column(Time, nullable=True)
    is_holiday = Column(Boolean, server_default="false")

    employee = relationship("StoreMembers", back_populates="work_schedules")
    part = relationship("StorePart")

class StoreMembersWorkLog(Base):
    __tablename__ = "store_members_work_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    store_id = Column(BigInteger, ForeignKey("stores.id"), nullable=False)
    employee_id = Column(BigInteger, ForeignKey("store_members.id"), nullable=False)
    work_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=True)
    break_start_time = Column(Time, nullable=True)
    break_end_time = Column(Time, nullable=True)
    status = Column(String(20), server_default="active")

    employee = relationship("StoreMembers", back_populates="work_logs")

class ScheduleChangeRequest(Base):
    __tablename__ = "schedule_change_requests"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    store_id = Column(BigInteger, ForeignKey("stores.id"), nullable=False)
    employee_id = Column(BigInteger, ForeignKey("store_members.id"), nullable=False)
    type = Column(String(20), nullable=False)  # "schedule_change" | "vacation"
    origin_date = Column(Date, nullable=True)
    origin_start = Column(Time, nullable=True)
    origin_end = Column(Time, nullable=True)
    desired_date = Column(Date, nullable=False)
    desired_start = Column(Time, nullable=True)
    desired_end = Column(Time, nullable=True)
    reason = Column(Text, nullable=False)
    status = Column(String(10), server_default="pending")  # pending | approved | rejected
    created_at = Column(DateTime, server_default=func.now())
    is_deleted = Column(Boolean, server_default="false")

    store = relationship("Store")
    employee = relationship("StoreMembers", back_populates="schedule_requests")

# ==========================================
# 6. 매장 커뮤니티 (게시판)
# ==========================================
class StoreCommunity(Base):
    __tablename__ = "store_community"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    store_id = Column(BigInteger, ForeignKey("stores.id"), nullable=False)
    employee_id = Column(BigInteger, ForeignKey("store_members.id", ondelete="SET NULL"), nullable=True)
    category = Column(String(20), nullable=False, index=True)
    title = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    image = Column(JSON)
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    is_deleted = Column(Boolean, server_default="false")

    store = relationship("Store", back_populates="community_posts")
    author = relationship("StoreMembers", back_populates="community_posts")
    comments = relationship("StoreCommunityComment", back_populates="community", cascade="all, delete-orphan")

class StoreCommunityComment(Base):
    __tablename__ = "store_community_comment"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    community_id = Column(BigInteger, ForeignKey("store_community.id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(BigInteger, ForeignKey("store_members.id", ondelete="SET NULL"), nullable=True)
    parent_id = Column(BigInteger, ForeignKey("store_community_comment.id"), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    is_deleted = Column(Boolean, server_default="false")

    community = relationship("StoreCommunity", back_populates="comments")
    author = relationship("StoreMembers", back_populates="comments")
    
    # 대댓글 셀프 참조 관계
    parent = relationship("StoreCommunityComment", remote_side=[id], back_populates="replies")
    replies = relationship("StoreCommunityComment", back_populates="parent", cascade="all, delete-orphan")

class CashShortageStatus(enum.Enum):
    plus = "plus"
    minus = "minus"

class DailyClosingReport(Base):
    __tablename__ = "daily_closing_reports"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(BigInteger, ForeignKey("stores.id"), nullable=False)
    employee_id = Column(BigInteger, ForeignKey("store_members.id"), nullable=False)
    
    # 보고 날짜
    report_date = Column(Date, nullable=False)
    
    # 1단계: 매출 정보
    card_sales = Column(BigInteger, default=0)
    cash_sales = Column(BigInteger, default=0)
    transfer_sales = Column(BigInteger, default=0)
    gift_sales = Column(BigInteger, default=0)
    
    # 2단계: 할인/환불/시제
    discount_amount = Column(BigInteger, default=0)
    refund_amount = Column(BigInteger, default=0)
    cash_on_hand = Column(BigInteger, default=0)
    
    # 현금 과부족
    cash_shortage_type = Column(Enum(CashShortageStatus), nullable=True)
    cash_shortage_amount = Column(BigInteger, default=0)
    
    # 3단계: 영수증 이미지
    receipt_image_url = Column(String(500), nullable=True)
    
    # 4단계: 추가 전달 내용
    manager_note = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # --- 외래키 관계 설정 (Relationship) ---
    store = relationship("Store", back_populates="closing_reports")
    employee = relationship("StoreMembers", back_populates="closing_reports")

# 근무 기록 수정 요청 모델
class WorkLogChangeRequest(Base):
    __tablename__ = "workLog_change_request"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="요청 고유번호")
    store_id = Column(BigInteger, ForeignKey("stores.id"), nullable=False, comment="매장 고유번호 (FK)")
    employee_id = Column(BigInteger, ForeignKey("store_members.id"), nullable=False, comment="직원 고유번호 (FK) (작성자)")
    
    type = Column(String(100), nullable=False, comment="타입")
    date = Column(Date, nullable=False, comment="변경 일자")
    
    origin_start = Column(Time, nullable=True, comment="기존 출근 시간")
    origin_end = Column(Time, nullable=True, comment="기존 퇴근 시간")
    
    desired_start = Column(Time, nullable=True, comment="변경 출근 시간")
    desired_end = Column(Time, nullable=True, comment="변경 퇴근 시간")
    desired_break = Column(Integer, nullable=True, comment="변경 휴게 시간")
    
    reason = Column(Text, nullable=False, comment="사유")
    status = Column(String(10), nullable=False, server_default="pending", comment="상태")
    
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="생성일")

    # 관계 설정 (필요 시 주석 해제하여 사용)
    store = relationship("Store", back_populates="change_requests")
    employee = relationship("StoreMembers", back_populates="work_log_requests")

class Notice(Base):
    __tablename__ = "notice"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="공지사항 고유번호")
    title = Column(String(200), comment="제목")
    content = Column(Text, nullable=False, comment="내용")
    image = Column(JSON, comment="이미지 URL")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), comment="생성일")
    is_deleted = Column(Boolean, server_default="false", comment="노출 여부(삭제 여부)")

class Faq(Base):
    __tablename__ = "faq"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="요청 고유번호")
    type = Column(String(20), nullable=False, comment="질문 유형")
    question = Column(String(500), nullable=False, comment="질문")
    answer = Column(Text, nullable=False, comment="답변")
    is_deleted = Column(Boolean, server_default="false", comment="노출 여부(삭제 여부)")
class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="건의 고유번호")
    member_id = Column(BigInteger, ForeignKey("members.id"))
    title = Column(String(200), comment="제목")
    content = Column(Text, comment="내용")
    image = Column(JSON, comment="이미지 URL")
    status = Column(String(30), server_default="pending", comment="상태")
    answer = Column(Text, nullable=True, comment="답변")
    created_at = Column(DateTime, server_default=func.now(), comment="생성 일시(건의 일시)")
    answered_at = Column(DateTime, onupdate=func.now(), comment="답변 일시")

    member = relationship("Member", back_populates="feedbacks")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="알림 고유번호")
    employee_id = Column(BigInteger, ForeignKey("store_members.id"), nullable=False, comment="직원 고유번호")
    type = Column(String(20), nullable=False, comment="알림 유형")
    message = Column(String(200), nullable=False, comment="알림 내용")
    reference_id = Column(BigInteger, nullable=True, comment="연관 데이터 ID")
    is_read = Column(Boolean, server_default="false", comment="읽음 여부")
    created_at = Column(DateTime, server_default=func.now(), comment="알림 발생 시간")

    employee = relationship("StoreMembers", back_populates="notifications")