from sqlalchemy import  Column, Integer, BigInteger, String, Text, Boolean, DateTime, ForeignKey, func, Date, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base
from database import SessionLocal

class Member(Base):
    __tablename__ = "members"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    password = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    name = Column(String(100), nullable=True)
    birth = Column(Date, nullable=True)
    gender = Column(String(10), nullable=True)
    is_deleted = Column(Boolean, default=False)

    social = relationship("SocialAccount", back_populates="member", cascade="all, delete-orphan")

class SocialAccount(Base):
    __tablename__ = "social_accounts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    member_id = Column(BigInteger, ForeignKey("members.id"))
    provider = Column(String(20), nullable=False)   # google/kakao/apple
    provider_id = Column(String(255), nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "provider_id"),
    )

    member = relationship("Member", back_populates="social", cascade="all, delete-orphan")

class Store(Base):
    __tablename__ = "stores"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(BigInteger, unique=True)
    name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=False)
    industry = Column(String(100), nullable=False)
    owner = Column(String(100), nullable=False)
    number = Column(String(20), nullable=False)
    image = Column(Text, nullable=False)
    radius = Column(Integer, nullable=False)