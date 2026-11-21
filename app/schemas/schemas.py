from pydantic import BaseModel
from typing import List, Optional

# --- User Schemas ---
class UserBase(BaseModel):
    id: int
    name: str
    email: Optional[str] = None

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    code: str

class EmailVerificationRequest(BaseModel):
    email: str

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserBase

class TokenData(BaseModel):
    email: Optional[str] = None

# --- Comment Schemas ---
class CommentCreate(BaseModel):
    text: str
    article_id: int

    class Config:
        from_attributes = True

class CommentResponse(BaseModel):
    id: int
    text: str
    sentiment: str
    user: Optional[UserBase] = None
    upvotes: int = 0
    downvotes: int = 0
    score: int = 0

    class Config:
        from_attributes = True

class CommentRatingCreate(BaseModel):
    vote: int  # 1 or -1

# --- Article Schemas ---
class ArticleBase(BaseModel):
    id: int
    title: str
    content: str
    category: Optional[str] = None
    author: Optional[str] = None
    image: Optional[str] = None
    summary: Optional[str] = None
    is_sensitive: Optional[bool] = False
    user_id: Optional[int] = None

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

# --- Text-to-Speech Schema ---
class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "salma"
