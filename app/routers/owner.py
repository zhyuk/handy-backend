import os
import httpx
import json
from fastapi import APIRouter, Depends, Query, Cookie, HTTPException, Response, UploadFile, File, Form
from sqlalchemy import text, func
from sqlalchemy.orm import Session
from pathlib import Path
from dotenv import load_dotenv
import uuid

from models import BusinessRequest
from database import get_db, SessionLocal
from schemas.login import StoreInfo

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
    # print(storeName, address, addressDetail, businessType, ownerName, ownerPhone, image)
    file_name, file_path, content = await prepare_business_image(image)
    try:
        request = BusinessRequest(
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