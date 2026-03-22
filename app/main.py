import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import create_tables
import os

from routers import community, auth, owner

import firebase_init
from firebase_admin import messaging

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("서버 시작 중...")
    try:
        create_tables()
    except Exception as e:
        print(f"DB 연결 에러: {e}")
    yield
    print("서버 종료 중...")

app = FastAPI(title="handy", lifespan=lifespan, redirect_slashes=False)

# ===== ROUTER ===== #
app.include_router(auth.router)
app.include_router(owner.router)
app.include_router(community.router)

# ===== CORS ===== #
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "http://10.0.2.2",
    "http://10.0.2.2:8000",
    "http://localhost",
    "https://local.handy.com",
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,    # 배포할 때 허용한 URL만 접속하도록 처리
    # allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(__file__)

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        # ssl_certfile=os.path.join(BASE_DIR, "../cert.pem"),  # 한 단계 위
        # ssl_keyfile=os.path.join(BASE_DIR, "../key.pem"),    # 한 단계 위
    )