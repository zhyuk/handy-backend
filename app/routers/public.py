import os
import uuid
import json
from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from sqlalchemy import desc, func
from sqlalchemy.orm import Session
from database import get_db
from typing import Optional, List

from models import Store, StoreMap, StoreCommunity, StoreCommunityComment, StoreMembers, Member, Notice, Faq, Feedback, Notification, Withdrawal
from utils.auth_utils import password_encode, password_decode
from schemas.public import BoardRequest, BoardResponse, BoardDetailResponse, CommentCreateRequest, PasswordRequest, StoreRequest, WithdrawlRequestSchemas
from routers.auth import get_current_member_with_refresh

router = APIRouter(prefix="/api/common", tags=["공통 기능"])

for _dir in ["uploads/board/", "uploads/feedback/"]:
    os.makedirs(_dir, exist_ok=True)

BOARD_UPLOAD_DIR = "uploads/board/"
FEEDBACK_UPLOAD_DIR = "uploads/feedback/"


async def save_upload(file: UploadFile, upload_dir: str) -> str:
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join(upload_dir, filename)
    with open(filepath, "wb") as f:
        f.write(await file.read())
    return f"/{upload_dir}{filename}"


# ==================== 매장 위치 ==================== #
@router.post("/store/map")
async def get_store_map(req: StoreRequest, db: Session = Depends(get_db)):
    store_map = db.query(StoreMap).filter(StoreMap.store_id == req.store_id).first()
    if not store_map:
        raise HTTPException(status_code=404, detail="매장 위치 정보가 없습니다.")

    store = db.query(Store).filter(Store.id == req.store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="매장 정보가 없습니다.")

    return {"lat": store_map.lat, "lng": store_map.lng, "radius": store.radius}


# ==================== 게시글 ==================== #
@router.post("/board", response_model=list[BoardResponse])
async def get_board_list(req: BoardRequest, db: Session = Depends(get_db)):
    results = (
        db.query(
            StoreCommunity,
            Member.name,
            StoreMembers.role,
            func.count(StoreCommunityComment.id).label("comment_count")
        )
        .join(StoreMembers, StoreMembers.id == StoreCommunity.employee_id)
        .join(Member, Member.id == StoreMembers.member_id)
        .outerjoin(
            StoreCommunityComment,
            (StoreCommunityComment.community_id == StoreCommunity.id) &
            (StoreCommunityComment.is_deleted == False)
        )
        .filter(StoreCommunity.store_id == req.store_id, StoreCommunity.is_deleted == False)
        .group_by(StoreCommunity.id, Member.name, StoreMembers.role)
        .order_by(desc(StoreCommunity.created_at))
        .all()
    )

    return [{
        "id": b.id, "category": b.category, "title": b.title,
        "content": b.content, "created_at": b.created_at,
        "writer": name, "role": role, "comments": count
    } for b, name, role, count in results]


@router.get("/board/{id}", response_model=BoardDetailResponse)
async def get_board_detail(id: int, db: Session = Depends(get_db)):
    board_result = (
        db.query(StoreCommunity, Member.name, StoreMembers.role,
                 func.count(StoreCommunityComment.id).label("comment_count"))
        .join(StoreMembers, StoreMembers.id == StoreCommunity.employee_id)
        .join(Member, Member.id == StoreMembers.member_id)
        .outerjoin(StoreCommunityComment,
                   (StoreCommunityComment.community_id == StoreCommunity.id) &
                   (StoreCommunityComment.is_deleted == False))
        .filter(StoreCommunity.id == id, StoreCommunity.is_deleted == False)
        .group_by(StoreCommunity.id, Member.name, StoreMembers.role)
        .first()
    )
    if not board_result:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    board, author_name, role, comment_count = board_result

    comments = (
        db.query(StoreCommunityComment, Member.name.label("commenter_name"), StoreMembers.role.label("commenter_role"))
        .join(StoreMembers, StoreMembers.id == StoreCommunityComment.employee_id)
        .join(Member, Member.id == StoreMembers.member_id)
        .filter(StoreCommunityComment.community_id == id, StoreCommunityComment.is_deleted == False)
        .order_by(StoreCommunityComment.created_at.asc())
        .all()
    )

    return {
        "id": board.id, "category": board.category, "title": board.title,
        "content": board.content, "created_at": board.created_at,
        "writer": author_name, "role": role, "comment_count": comment_count,
        "comments": [{"id": c.id, "content": c.content, "created_at": c.created_at,
                      "parent_id": c.parent_id, "writer": name, "role": r}
                     for c, name, r in comments],
        "photos": board.image if board.image else []
    }


@router.post("/board/add")
async def add_board(
    store_id: int = Form(...),
    category: str = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    images: Optional[List[UploadFile]] = File(default=None),
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    employee = db.query(StoreMembers).filter(
        StoreMembers.store_id == store_id,
        StoreMembers.member_id == current_member.id
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="직원 정보를 찾을 수 없습니다.")

    image_urls = [await save_upload(img, BOARD_UPLOAD_DIR) for img in images] if images else []

    board = StoreCommunity(
        store_id=store_id,
        employee_id=employee.id,
        category=category,
        title=title,
        content=content,
        image=image_urls if image_urls else None,
    )
    db.add(board)
    db.commit()


@router.post("/board/modify")
async def modify_board(
    board_id: int = Form(...),
    category: str = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    clear_images: bool = Form(default=False),
    images: Optional[List[UploadFile]] = File(default=None),
    existing_images: Optional[str] = Form(default=None),
    db: Session = Depends(get_db)
):
    board = db.query(StoreCommunity).filter(StoreCommunity.id == board_id).first()
    if not board:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    image_urls = [await save_upload(img, BOARD_UPLOAD_DIR) for img in images] if images else []
    existing_urls = json.loads(existing_images) if existing_images else []

    board.category = category
    board.title = title
    board.content = content

    if clear_images:
        board.image = None
    elif image_urls or existing_urls:
        board.image = existing_urls + image_urls

    db.commit()
    return {"message": "게시글이 수정되었습니다."}


@router.delete("/board/{id}")
async def delete_post(id: int, db: Session = Depends(get_db)):
    board = db.query(StoreCommunity).filter(StoreCommunity.id == id).first()
    if not board:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    board.is_deleted = True
    db.commit()
    return {"message": "게시글이 삭제되었습니다."}


# ==================== 댓글 ==================== #
@router.post("/board/{id}/comment")
async def add_comment(
    id: int,
    body: CommentCreateRequest,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    # community로 store_id 조회 후 employee 찾기
    board = db.query(StoreCommunity).filter(StoreCommunity.id == id).first()
    if not board:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    employee = db.query(StoreMembers).filter(
        StoreMembers.store_id == board.store_id,
        StoreMembers.member_id == current_member.id
    ).first()
    if not employee:
        raise HTTPException(status_code=404, detail="직원 정보를 찾을 수 없습니다.")

    comment = StoreCommunityComment(
        community_id=id,
        employee_id=employee.id,
        parent_id=body.parent_id,
        content=body.content,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return {"message": "댓글이 등록되었습니다."}


@router.delete("/board/comment/{comment_id}")
async def delete_comment(comment_id: int, db: Session = Depends(get_db)):
    comment = db.query(StoreCommunityComment).filter(StoreCommunityComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")

    comment.is_deleted = True
    if comment.parent_id is None:
        for recomment in db.query(StoreCommunityComment).filter(
            StoreCommunityComment.parent_id == comment.id
        ).all():
            recomment.is_deleted = True

    db.commit()
    return {"message": "댓글이 삭제되었습니다."}


# ==================== 비밀번호 변경 ==================== #
@router.post("/password/change")
async def change_password(
    req: PasswordRequest,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    if not password_decode(req.old_password, current_member.password):
        raise HTTPException(status_code=401, detail="기존 비밀번호가 일치하지 않습니다.")

    current_member.password = password_encode(req.new_password)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="서버 오류로 인해 비밀번호를 변경하지 못했습니다.")


# ==================== 공지사항 / FAQ ==================== #
@router.get("/notice")
async def get_notice(db: Session = Depends(get_db)):
    return db.query(Notice).filter(Notice.is_deleted == False).order_by(desc(Notice.created_at)).all()


@router.get("/notice/{id}")
async def get_notice_detail(id: int, db: Session = Depends(get_db)):
    return db.query(Notice).filter(Notice.is_deleted == False, Notice.id == id).first()


@router.get("/faq")
async def get_faq(db: Session = Depends(get_db)):
    return db.query(Faq).filter(Faq.is_deleted == False).order_by(Faq.id).all()


# ==================== 건의함 ==================== #
@router.post("/feedback")
async def post_feedback(
    title: str = Form(...),
    content: str = Form(...),
    images: Optional[List[UploadFile]] = File(None),
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    image_urls = [await save_upload(img, FEEDBACK_UPLOAD_DIR) for img in images] if images else []

    feedback = Feedback(
        member_id=current_member.id,
        title=title,
        content=content,
        image=image_urls if image_urls else None,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


@router.get("/feedback")
async def get_personal_feedback(
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    return db.query(Feedback).filter(
        Feedback.member_id == current_member.id
    ).order_by(Feedback.created_at.desc()).all()


# ==================== 알림 ==================== #
@router.get("/notification")
async def get_personal_notification(
    unread_only: bool = False,
    current_member: Member = Depends(get_current_member_with_refresh),
    db: Session = Depends(get_db)
):
    # store_members.id 목록 먼저 조회
    employee_ids = [
        sm.id for sm in db.query(StoreMembers)
        .filter(StoreMembers.member_id == current_member.id).all()
    ]

    query = db.query(Notification).filter(Notification.employee_id.in_(employee_ids))
    if unread_only:
        query = query.filter(Notification.is_read == False)
    return query.order_by(desc(Notification.created_at)).all()


@router.patch("/notification/{id}/read")
async def mark_notification_read(id: int, db: Session = Depends(get_db)):
    notification = db.query(Notification).filter(Notification.id == id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")
    notification.is_read = True
    db.commit()
    return {"success": True}

@router.post("/withdrawal")
async def user_delete_reason(req: WithdrawlRequestSchemas, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    회원탈퇴 사유 API

    * 추후 스케줄링 구현으로 30일 지나면 해당 Member.id의 개인정보 모두 null로 업데이트
    ----------------------------------------
    """

    new_withdrawal = Withdrawal(
        member_id = req.member_id,
        reason = req.reason
    )

    db.add(new_withdrawal)
    db.commit()