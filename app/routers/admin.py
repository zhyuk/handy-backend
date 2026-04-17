from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text, func
from sqlalchemy.orm import Session
from database import get_db, SessionLocal

from models import Feedback, Faq
from schemas.admin import FeedbackAnswerSchemas, FaqAddSchemas

router = APIRouter(prefix="/api/admin", tags=["관리자 기능"])


# ====== 고객 건의함 관련 ====== #
@router.get("/feedback")
async def get_feedback(db: Session = Depends(get_db)):
    """
    ----------------------------------------
    [관리자용] 건의내역 조회 API
    ----------------------------------------
    """

    feedbackList = db.query(Feedback).filter(Feedback.status == "pending").order_by(Feedback.created_at).all()

    return feedbackList


@router.post("/feedback")
async def post_answer_for_feedback(req: FeedbackAnswerSchemas, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    [관리자용] 건의내역에 답변해주는 API
    ----------------------------------------
    """

    feedback = db.query(Feedback).filter(Feedback.id == req.id).first()

    if not feedback:
        raise HTTPException(status_code=404, detail="해당하는 건의내역을 찾을 수 없습니다.")
    
    feedback.answer = req.answer
    feedback.status = "completed"
    
    db.commit()
# ====== 고객 건의함 관련 끝 ====== #

# ====== 자주 묻는 질문 ====== #
@router.post("/faq")
async def add_faq(req: FaqAddSchemas, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    [관리자용] 자주 묻는 질문 추가 API
    ----------------------------------------
    """
    new_faq = Faq(
        type = req.type,
        question = req.question,
        answer = req.answer
    )

    db.add(new_faq)
    db.commit()

@router.delete("/faq/{id}")
async def delete_faq(id: int, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    [관리자용] 자주 묻는 질문 삭제 API

    * 소프트 삭제
    ----------------------------------------
    """

    faq = db.query(Faq).filter(Faq.id == id).first()
    faq.is_deleted = True

    db.commit()
# ====== 자주 묻는 질문 끝 ====== #

# ====== 서비스 공지사항 ====== #