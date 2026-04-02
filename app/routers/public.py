import uuid
import secrets
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db

from models import Store, StoreMap
from utils.uitls import create_store_code


router = APIRouter(prefix="/api/common", tags=["공통 기능"])

@router.get("")
async def add_stores(db: Session = Depends(get_db)):
    """
    ----------------------------------------
    승인된 매장 정보 추가 API

    * 관리자가 사업자등록증 사진을 보고 승인을 누른 경우 동작하는 API
    ----------------------------------------
    """
    store_code = create_store_code(db)

    

    