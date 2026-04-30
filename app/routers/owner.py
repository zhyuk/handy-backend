import os
import httpx
import json
from fastapi import APIRouter, Depends, Query, Cookie, HTTPException, Response, UploadFile, File, Form
from sqlalchemy import text, func
from sqlalchemy.orm import Session, joinedload
from pathlib import Path
from dotenv import load_dotenv
import uuid

from models import BusinessRequest, Store, StoreSetting, StorePart
from database import get_db, SessionLocal
from schemas.login import StoreInfo
from schemas.owner import setStoreInfoSchemas

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(ENV_PATH)

BUSINESS_KEY = os.getenv("VITE_BUSINESS_API_KEY")

router = APIRouter(prefix="/api/owner", tags=["소셜 로그인 관리"])

# === 사업자등록증 파일 저장 로직 === #
UPLOAD_DIR = "uploads/business_registractions/"
async def prepare_business_image(image: UploadFile):
    ext = os.path.splitext(image.filename)[1]
    new_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, new_filename)
    
    # 파일 내용을 메모리에 읽어둡니다.
    content = await image.read()
    return new_filename, file_path, content

 # ===================================================== 사업자번호 조회 ===================================================== #
@router.get("/business/{bno}")
async def verify_business(bno: str):
    """
    ----------------------------------------
    사업자등록번호 조회 API
    ----------------------------------------
    """
    
    url = "https://api.odcloud.kr/api/nts-businessman/v1/status"

    params = {
        "serviceKey": BUSINESS_KEY
    }

    data = {
        "b_no": [bno]
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(
            url,
            params=params,
            json=data
        )

    return res.json()

@router.post("/stores")
async def add_store_request(
    rawDigits: str = Form(...),
    storeName: str = Form(...),
    address: str = Form(...),
    addressDetail: str | None = Form(None),
    businessType: str = Form(...),
    ownerName: str = Form(...),
    ownerPhone: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
    ):
    """
    ----------------------------------------
    매장정보 추가 API
    ----------------------------------------
    """
    file_name, file_path, content = await prepare_business_image(image)
    try:
        request = BusinessRequest(
            rawDigits = rawDigits,
            name = storeName,
            address = address,
            addressDetail = addressDetail,
            industry = businessType,
            owner = ownerName,
            number = ownerPhone,
            image = file_name,
        )
        db.add(request)

        db.commit()
        db.refresh(request)
    
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(content)
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="데이터 저장 중 오류가 발생했습니다.")
    
@router.put("/store/update")
async def update_store_info(req: setStoreInfoSchemas, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    매장정보 수정 API
    ----------------------------------------
    """
    storeInfo = db.query(Store).filter(Store.id == req.id).first()

    if not storeInfo:
        raise HTTPException(status_code=404, detail="해당 매장을 찾을 수 없습니다.")
    
    storeInfo.name = req.name
    storeInfo.address = req.address
    storeInfo.addressDetail = req.addressDetail
    storeInfo.industry = req.industry
    storeInfo.owner = req.owner
    storeInfo.number = req.number

    db.commit()

@router.get("/store/{id}")
async def get_store_info(id: int, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    매장정보 조회 API
    ----------------------------------------
    """
    store = (
        db.query(Store)
        .options(
            joinedload(Store.setting),
            joinedload(Store.parts)
        )
        .filter(Store.id == id)
        .first()
    )
    return store

@router.put("/store/{store_id}/setting")
async def update_store_setting(store_id: int, data: dict, db: Session = Depends(get_db)):
    setting = db.query(StoreSetting).filter(StoreSetting.store_id == store_id).first()
    if not setting:
        setting = StoreSetting(store_id=store_id)
        db.add(setting)
    for key, val in data.items():
        setattr(setting, key, val)
    db.commit()
    return {"ok": True}

@router.put("/store/{store_id}/parts")
async def update_store_parts(
    store_id: int,
    data: dict,
    db: Session = Depends(get_db)
):
    # 기존 파트 삭제 후 재삽입
    db.query(StorePart).filter(StorePart.store_id == store_id).delete()
    for p in data["parts"]:
        db.add(StorePart(
            store_id=store_id,
            name=p["name"],
            start_time=p["start_time"],
            end_time=p["end_time"],
        ))
    db.commit()
    return {"ok": True}

@router.put("/store/{store_id}/attendance-standard")
async def update_attendance_standard(
    store_id: int,
    data: dict,
    db: Session = Depends(get_db)
):
    
    print(data.get("radius"))
    # stores 테이블 radius 업데이트
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404)
    store.radius = data.get("radius")

    # store_settings 테이블 업데이트
    setting = db.query(StoreSetting).filter(StoreSetting.store_id == store_id).first()
    if setting:
        setting.late_minutes = data.get("late_minutes")
        setting.has_overtime_pay = data.get("has_overtime_pay")
        setting.overtime_after_8h = data.get("overtime_after_8h")
        setting.overtime_after_40h = data.get("overtime_after_40h")
        setting.overtime_multiplier = data.get("overtime_multiplier")
        setting.overtime_minutes = data.get("overtime_minutes")
        setting.has_night_pay = data.get("has_night_pay")
        setting.night_multiplier = data.get("night_multiplier")
        setting.night_minutes = data.get("night_minutes")
        setting.has_holiday_pay = data.get("has_holiday_pay")
        setting.holiday_multiplier_under_8h = data.get("holiday_multiplier_under_8h")
        setting.holiday_multiplier_over_8h = data.get("holiday_multiplier_over_8h")
        setting.holiday_minutes = data.get("holiday_minutes")

    db.commit()
    return {"ok": True}

# TODO: 직원 스케줄(근무표) 변경요청 수락 시, StoreMemberWork 업데이트 진행.
# TODO: 매장 공지사항 작성 시, Notification에 데이터 추가. employee_id는 해당 매장에 재직 중인 모두
# TODO: 사장이 급여 명세서 발행하면 직원의 급여 명세서 관련 부분 구현해야함.