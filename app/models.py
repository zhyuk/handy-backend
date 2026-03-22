from sqlalchemy import  Column, Integer, BigInteger, String, Text, Boolean, DateTime, ForeignKey, func, Date, UniqueConstraint
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
