from pydantic import BaseModel, Field
from typing import Any

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    session_id: str = Field(min_length=1, max_length=100)

class ChatResponse(BaseModel):
    session_id: str
    answer: str

class Document(BaseModel):
    id: str
    text: str
    metadata: dict[str, Any] = {}

class KnowledgeRequest(BaseModel):
    documents: list[Document]
