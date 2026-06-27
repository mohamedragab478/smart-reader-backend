from pydantic import BaseModel
from typing import List, Optional

# --- User Schemas ---
class UserBase(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

# --- Comment Schemas ---
class CommentCreate(BaseModel):
    text: str
    user: Optional[UserBase] = None
    article: Optional[BaseModel] = None  # We will handle nested article ID parsing in main

    class Config:
        from_attributes = True

class CommentResponse(BaseModel):
    id: int
    text: str
    sentiment: str
    user: Optional[UserBase] = None

    class Config:
        from_attributes = True

# --- Article Schemas ---
class ArticleBase(BaseModel):
    id: int
    title: str
    content: str
    category: Optional[str] = None
    author: Optional[str] = None
    image: Optional[str] = None
    summary: Optional[str] = None

    class Config:
        from_attributes = True

class ArticleResponse(ArticleBase):
    comments: List[CommentResponse] = []

    class Config:
        from_attributes = True

# --- Chat & Scraping Upgrades ---
class ScrapeRequest(BaseModel):
    url: str

class ChatMessage(BaseModel):
    role: str  # "user" or "model"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = None

# --- Web Search Schema ---
class SearchResult(BaseModel):
    title: str
    url: str
    snippet: Optional[str] = None
    image: Optional[str] = None
    source: Optional[str] = None
