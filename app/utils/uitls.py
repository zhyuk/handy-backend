import re
import os
import httpx
import secrets
from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import Store

def format_phone_number(number: str) -> str:
    """ 전화번호 포맷팅 함수 """
    # 숫자만 남기기 (혹시 모를 공백이나 기호 제거)
    clean_number = re.sub(r'\D', '', number)
    
    # 1. 서울 지역번호 (02)인 경우
    if clean_number.startswith('02'):
        return re.sub(r'(\d{2})(\d{3,4})(\d{4})', r'\1-\2-\3', clean_number)
    
    # 2. 그 외 (010, 031, 070, 050 등 3자리 시작)
    else:
        return re.sub(r'(\d{3})(\d{3,4})(\d{4})', r'\1-\2-\3', clean_number)

async def create_store_code(db: Session):
    """ 매장코드 발급 함수 """
    while True:
        # 1. 5자리 코드 생성 (00000 ~ 99999)
        store_code = str(secrets.randbelow(100000)).zfill(5)
        
        # 2. DB에서 중복 확인
        exists = db.query(Store).filter(Store.code == store_code).first()
        
        # 3. 중복이 없으면 코드 반환, 있으면 다시 위로 올라가서 생성
        if not exists:
            return store_code

async def get_coords_from_address(address: str):
    """ 주소 → 위/경도 변환 함수 """
    KAKAO_REST_API_KEY = os.getenv("KAKAO_CLIENT_ID")
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    params = {"query": address}

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        
    # if response.status_code != 200:
    #     raise HTTPException(status_code=500, detail="카카오 주소 변환 서비스 오류")

    data = response.json()
    if not data["documents"]:
        raise HTTPException(status_code=400, detail="유효하지 않은 주소입니다. 좌표를 찾을 수 없습니다.")

    # 카카오 API 결과: x는 경도(lng), y는 위도(lat)
    lng = data["documents"][0]["x"]
    lat = data["documents"][0]["y"]
    
    return float(lat), float(lng)