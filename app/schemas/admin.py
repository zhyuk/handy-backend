from pydantic import BaseModel
from datetime import time, datetime
from typing import List, Optional, Text

# 피드백 답변 스키마
class FeedbackAnswerSchemas(BaseModel):
    id: int
    answer: str

class FaqAddSchemas(BaseModel):
    type: str
    question: str
    answer: str
