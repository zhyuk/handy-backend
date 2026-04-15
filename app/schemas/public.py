from pydantic import BaseModel, Field
from datetime import time, datetime
from typing import List, Optional

# === 매장코드 검증 스키마 === #
class add(BaseModel):
    code: str

# ========== 게시글 관련 스키마 ========== #
class BoardRequest(BaseModel):
    store_id: int

class BoardResponse(BaseModel):
    id: int
    category: str
    title: str
    content: str
    created_at: datetime
    writer: str
    role: str
    comments: int
    class Config:
        from_attributes = True

class BoardCreateResponse(BaseModel):
    store_id: int
    employee_id: int
    category: str
    title: str
    content: str
    images: Optional[List[str]] = []

class CommentResponse(BaseModel):
    id: int
    writer: str
    role: str
    content: str
    created_at: datetime
    parent_id: int | None = None
class BoardDetailResponse(BaseModel):
    id: int
    category: str
    title: str
    content: str
    created_at: datetime
    writer: str
    role: str
    comment_count: int
    comments: List[CommentResponse]
    photos: List[str] = Field(default=[], max_length=5)
    
    class Config:
        from_attributes = True

class CommentCreateRequest(BaseModel):
    employee_id: int
    content: str
    parent_id: int | None = None 


# === 비밀번호 변경 스키마 === #
class PasswordRequest(BaseModel):
    old_password: str
    new_password: str
    user_id: int

class StoreRequest(BaseModel):
    store_id: int