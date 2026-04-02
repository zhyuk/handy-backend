from sqlalchemy import  Column, Integer, BigInteger, String, Text, Boolean, DateTime, ForeignKey, func, Date, UniqueConstraint, Numeric
from sqlalchemy.orm import relationship
from database import Base
from database import SessionLocal

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

    social_accounts = relationship("SocialAccount", back_populates="member", cascade="all, delete-orphan")
    tokens = relationship("JwtTokens", back_populates="member", cascade="all, delete-orphan")
    members_for_storeMembers = relationship("StoreMembers", back_populates="members_to_storeMember", cascade="all, delete-orphan")
    member_requests = relationship("MemberRequest", back_populates="member", cascade="all, delete-orphan")

class SocialAccount(Base):
    __tablename__ = "social_accounts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    member_id = Column(BigInteger, ForeignKey("members.id"))
    provider = Column(String(20), nullable=False)   # google/kakao/apple
    provider_id = Column(String(255), nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "provider_id"),
    )

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

class Store(Base):
    __tablename__ = "stores"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(BigInteger, unique=True)
    name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=False)
    addressDetail = Column(String(255), nullable=True)
    industry = Column(String(100), nullable=False)  # 업종
    owner = Column(String(100), nullable=False)
    number = Column(String(20), nullable=False)
    image = Column(Text, nullable=False)
    radius = Column(Integer, nullable=True)

    # 관계 설정
    map_info = relationship("StoreMap", back_populates="store", cascade="all, delete-orphan")
    stores_for_storeMembers = relationship("StoreMembers", back_populates="stores_to_storeMember", cascade="all, delete-orphan")
    member_requests = relationship("MemberRequest", back_populates="store", cascade="all, delete-orphan")

class StoreMap(Base):
    __tablename__ = "store_maps"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    store_id = Column(BigInteger, ForeignKey("stores.id"), nullable=False)
    # 위도 (Latitude): 전체 10자리, 소수점 이하 7자리
    lat = Column(Numeric(precision=10, scale=7), nullable=False)
    # 경도 (Longitude): 전체 11자리(180도 때문), 소수점 이하 7자리
    lng = Column(Numeric(precision=11, scale=7), nullable=False)

    store = relationship("Store", back_populates="map_info")
class BusinessRequest(Base):
    __tablename__ = "business_requests"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=False)
    addressDetail = Column(String(255), nullable=True)
    industry = Column(String(100), nullable=False)  # 업종
    owner = Column(String(100), nullable=False)
    number = Column(String(20), nullable=False)
    image = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    is_checked = Column(Boolean, default=False) # 승인 여부
    checked_time = Column(DateTime, onupdate=func.now())  # 승인 시간
    reject_reason = Column(Text)

class StoreMembers(Base):
    __tablename__ = "store_members"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    store_id = Column(BigInteger, ForeignKey("stores.id"), nullable=False)
    member_id = Column(BigInteger, ForeignKey("members.id"), nullable=False)
    bank = Column(String(50), nullable=False)
    accountNumber = Column(String(100), nullable=False)
    joined_at = Column(Date, server_default=func.now())

    # "members" -> "Member", "stores" -> "Store"로 수정
    members_to_storeMember = relationship("Member", back_populates="members_for_storeMembers")
    stores_to_storeMember = relationship("Store", back_populates="stores_for_storeMembers")
    
    # 상세 정보와 1:1 관계
    detail = relationship("StoreMembersDetail", back_populates="store_member", uselist=False, cascade="all, delete-orphan")


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

class MemberRequest(Base):
    __tablename__ = "member_requests"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    store_id = Column(BigInteger, ForeignKey("stores.id"), nullable=False)
    member_id = Column(BigInteger, ForeignKey("members.id"), nullable=False)
    
    bank = Column(String(50))
    accountName = Column(String(100))
    accountNumber = Column(String(100))
    
    status = Column(String(10), server_default="pending")   # 결과(pending / approved / rejected)
    created_at = Column(DateTime, server_default=func.now())

    # 관계 설정 (N:1)
    store = relationship("Store", back_populates="member_requests")
    member = relationship("Member", back_populates="member_requests")