import os
import httpx
import json
from fastapi import APIRouter, Depends, Query, Cookie, HTTPException, Response, UploadFile, File, Form
from sqlalchemy.orm import Session
from pathlib import Path
from dotenv import load_dotenv
import uuid

from models import Store, StoreMap, MemberRequest
from database import get_db
from schemas.employee import VerifyCode, MemberRequestSchemas
from utils.uitls import format_phone_number, get_coords_from_address


router = APIRouter(prefix="/api/employee", tags=["직원유형"])

# ======= 매장코드 조회 ======= #
@router.post("/verify-code")
async def verify_store_code(req: VerifyCode, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    매장코드 조회 API
    ----------------------------------------
    """
    # print(req)

    storeInfo = db.query(Store).filter(Store.code == req.code).first()

    # 일치하는 매장이 존재하지 않을 경우
    if not storeInfo:
        raise HTTPException(status_code=404, detail="조회되지 않는 매장 코드에요")
    
    storeMap = db.query(StoreMap).filter(storeInfo.id == StoreMap.store_id).first()
    
    # 세부주소가 존재할 경우 병합
    address_parts = [storeInfo.address, storeInfo.addressDetail]
    full_address = " ".join([part for part in address_parts if part])

    if not storeMap:
        lat, lng = await get_coords_from_address(storeInfo.address)

        storeMap = StoreMap(
            store_id = storeInfo.id,
            lat = lat,
            lng = lng
        )

        db.add(storeMap)
        db.commit()
        db.refresh(storeMap)

    return_info = {
        "id": storeInfo.id,
        "name": storeInfo.name,
        "address": full_address,
        "phone": format_phone_number(storeInfo.number),
        "lat": float(storeMap.lat),
        "lng": float(storeMap.lng)
    }

    return return_info
# ======= 매장코드 조회 ======= #

# ======= 가입신청 하기 ======= #
@router.post("/member/request")
async def add_member_request(req: MemberRequestSchemas, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    직원 가입신청 API
    ----------------------------------------
    """
    # print(req)

    try:
        request = MemberRequest(
            store_id = req.store_id,
            member_id = 1,
            bank = req.bank,
            accountName = req.accountName,
            accountNumber = req.accountNumber
        )

        db.add(request)
        db.commit()
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="데이터 저장 중 오류가 발생했습니다.")
# ======= 가입신청 하기 ======= #