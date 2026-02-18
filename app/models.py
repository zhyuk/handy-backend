from sqlalchemy import  Column, BigInteger, String, Text, Boolean, DateTime, ForeignKey, func, Date
from sqlalchemy.orm import relationship
from database import Base
from database import SessionLocal

class Member(Base):
    __tablename__ = "members"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    password = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    birth = Column(Date, nullable=False)
    gender = Column(String(10), nullable=True)