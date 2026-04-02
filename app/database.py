import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DB_URL)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False,)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    import models
    Base.metadata.create_all(bind=engine)
    print("DB 연결 성공")
    insert_dummy_store()
    insert_test_member()

def insert_dummy_store():
    from models import Store
    db = SessionLocal()

    try:
        test_store = db.query(Store).filter(Store.name == "노량물산", Store.code == 12345).first()
        
        if not test_store:
            store = Store(
                code = 12345,
                name = "노량물산",
                address = "서울특별시 동작구 노량진로 151",
                industry = "test",
                owner = "김다흰",
                number = "027272112",
                image = "default.png",
                radius = 200
            )

            db.add(store)
            db.commit()
            print("테스트용 가게 생성 완료")
        else:
            print("테스트용 가게가 이미 존재합니다.")

    except Exception as e:
        print(f"가게 생성 중 에러 발생: {e}")
        db.rollback()
    finally:
        db.close()


def insert_test_member():
    from utils.auth_utils import password_encode
    from models import Member

    db = SessionLocal()

    try:
        test_member = db.query(Member).filter(Member.name == "테스트", Member.id == 1).first()

        if not test_member:
            member = Member(
                password = password_encode("1111"),
                phone = "01011111111",
                name = "테스트",
                gender = "male"
            )

            db.add(member)
            db.commit()
            print("테스트용 계정 생성 완료")
        else:
            print("테스트용 계정이 이미 존재합니다.")

    except Exception as e:
        print(f"계정 생성 중 에러 발생: {e}")
        db.rollback()
    finally:
        db.close()