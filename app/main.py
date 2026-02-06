import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import create_tables

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("서버 시작 중...")
    try:
        create_tables()
    except Exception as e:
        print(f"DB 연결 에러: {e}")
    yield
    print("서버 종료 중...")

app = FastAPI(title="handy", lifespan=lifespan)

origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)