import os
import uuid
import secrets
import json
from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from sqlalchemy import desc, func
from sqlalchemy.orm import Session
from database import get_db
from typing import Optional, List

from models import Store, StoreMap, StoreCommunity, StoreCommunityComment, StoreMembers, Member
from utils.uitls import create_store_code
from schemas.public import BoardCreateResponse, BoardRequest, BoardResponse, BoardDetailResponse, CommentCreateRequest


router = APIRouter(prefix="/api/common", tags=["공통 기능"])

BOARD_UPLOAD_DIR = "uploads/board/"
os.makedirs(BOARD_UPLOAD_DIR, exist_ok=True)

@router.get("")
async def add_stores(db: Session = Depends(get_db)):
    """
    ----------------------------------------
    승인된 매장 정보 추가 API

    * 관리자가 사업자등록증 사진을 보고 승인을 누른 경우 동작하는 API
    ----------------------------------------
    """
    store_code = create_store_code(db)

    
# ==================== 게시글 관련 ==================== #
@router.post("/board", response_model=list[BoardResponse])
async def get_boardList(req: BoardRequest, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    매장별 게시판 글 목록 조회 API
    ----------------------------------------
    """

    # print("board_list req : ", req)


    results = (
            db.query(
                StoreCommunity, 
                Member.name, 
                StoreMembers.role,
                func.count(StoreCommunityComment.id).label("comment_count") # 댓글 수 집계
            )
            .join(StoreMembers, StoreMembers.id == StoreCommunity.employee_id)
            .join(Member, Member.id == StoreMembers.member_id)
            .outerjoin(
                StoreCommunityComment, 
                (StoreCommunityComment.community_id == StoreCommunity.id) & 
                (StoreCommunityComment.is_deleted == False)
            )
            .filter(
                StoreCommunity.store_id == req.store_id,
                StoreCommunity.is_deleted == False,
            )
            .group_by(StoreCommunity.id, Member.name, StoreMembers.role) # 집계 함수 사용 시 필수
            .order_by(desc(StoreCommunity.created_at))
            .all()
        )

    result = []
    for board, author_name, role, comment_count in results:
        result.append({
            "id": board.id,
            "category": board.category,
            "title": board.title,
            "content": board.content,
            "created_at": board.created_at,
            "writer": author_name,
            "role": role,
            "comments": comment_count  # 댓글이 없으면 0으로 들어갑니다.
        })

    return result

@router.get("/board/{id}", response_model=BoardDetailResponse)
async def get_boardList(id:int, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    매장별 게시판 글 상세 조회 API
    ----------------------------------------
    """
    # print(id)

    board_result = (
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
        .filter(
            StoreCommunity.id == id,
            StoreCommunity.is_deleted == False
        )
        .group_by(StoreCommunity.id, Member.name, StoreMembers.role)
        .first()
    )

    if not board_result:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    board, author_name, role, comment_count = board_result

    # 댓글 조회 (community_id 기준, is_deleted 컬럼 없으면 제거)
    comments = (
        db.query(
            StoreCommunityComment,
            Member.name.label("commenter_name"),
            StoreMembers.role.label("commenter_role")
        )
        .join(StoreMembers, StoreMembers.id == StoreCommunityComment.employee_id)
        .join(Member, Member.id == StoreMembers.member_id)
        .filter(StoreCommunityComment.community_id == id, StoreCommunityComment.is_deleted == False)
        .order_by(StoreCommunityComment.created_at.asc())
        .all()
    )

    comment_list = []
    for comment, commenter_name, commenter_role in comments:
        comment_list.append({
            "id": comment.id,
            "content": comment.content,
            "created_at": comment.created_at,
            "parent_id": comment.parent_id,
            "writer": commenter_name,
            "role": commenter_role,
        })

    return {
        "id": board.id,
        "category": board.category,
        "title": board.title,
        "content": board.content,
        "created_at": board.created_at,
        "writer": author_name,
        "role": role,
        "comment_count": comment_count,
        "comments": comment_list,
        "photos": board.image if board.image else []
    }

@router.post("/board/add")
async def add_board(    
    store_id: int = Form(...),
    employee_id: int = Form(...),
    category: str = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    images: Optional[List[UploadFile]] = File(default=None),
    db: Session = Depends(get_db)):
    """
    ----------------------------------------
    게시판 글 추가 API
    ----------------------------------------
    """

    image_urls = []

    if images:
        for image in images:
            ext = os.path.splitext(image.filename)[1]
            new_filename = f"{uuid.uuid4()}{ext}"
            file_path = os.path.join(BOARD_UPLOAD_DIR, new_filename)
            content_data = await image.read()
            with open(file_path, "wb") as f:
                f.write(content_data)
            image_urls.append(f"/uploads/board/{new_filename}")

    board = StoreCommunity(
        store_id=store_id,
        employee_id=employee_id,
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
    db: Session = Depends(get_db)):

    """
    ----------------------------------------
    게시글 수정 API
    ----------------------------------------
    """


    board = db.query(StoreCommunity).filter(StoreCommunity.id == board_id).first()

    if not board:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    image_urls = []
    if images:
        for image in images:
            ext = os.path.splitext(image.filename)[1]
            new_filename = f"{uuid.uuid4()}{ext}"
            file_path = os.path.join(BOARD_UPLOAD_DIR, new_filename)
            content_data = await image.read()
            with open(file_path, "wb") as f:
                f.write(content_data)
            image_urls.append(f"/uploads/board/{new_filename}")

    board.category = category
    board.title = title
    board.content = content
    
    existing_urls = json.loads(existing_images) if existing_images else []

    if clear_images:
        board.image = None
    elif image_urls or existing_urls:
        board.image = existing_urls + image_urls

    db.commit()
    return {"message": "게시글이 수정되었습니다."}

@router.delete("/board/{id}")
async def delete_post(id: int, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    게시글 삭제 API
    ----------------------------------------
    """

    board = db.query(StoreCommunity).filter(StoreCommunity.id == id).first()

    if not board:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    
    board.is_deleted = True

    db.commit()
    return {"message": "게시글이 삭제되었습니다."}

# ==================== 게시글 관련 종료 ==================== #


# ==================== 댓글 관련 ==================== #
@router.post("/board/{id}/comment")
async def add_comment(id: int, body: CommentCreateRequest, db: Session = Depends(get_db)):
    """
    ----------------------------------------
    게시판 댓글 추가 API
    ----------------------------------------
    """

    print(id)
    print(body)
    comment = StoreCommunityComment(
        community_id=id,
        employee_id=body.employee_id,
        parent_id=body.parent_id,
        content=body.content,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return {"message": "댓글이 등록되었습니다."}

@router.delete("/board/comment/{comment_id}")
async def delete_comment(comment_id: int,  db: Session = Depends(get_db)):
    """
    ----------------------------------------
    게시판 댓글 삭제 API
    ----------------------------------------
    """
    # print(comment_id)

    comment = db.query(StoreCommunityComment).filter(StoreCommunityComment.id == comment_id).first()

    if not comment:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")
    
    comment.is_deleted = True

    if comment.parent_id is None:
        recomments = db.query(StoreCommunityComment).filter(
            StoreCommunityComment.parent_id == comment.id
        ).all()
        for recomment in recomments:
            recomment.is_deleted = True

    db.commit()
    return {"message": "댓글이 삭제되었습니다."}
# ==================== 댓글 관련 종료 ==================== #