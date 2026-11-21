from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.db.database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=True)

    articles = relationship("Article", back_populates="user")
    comments = relationship("Comment", back_populates="user")
    ratings = relationship("CommentRating", back_populates="user")
    searches = relationship("SearchHistory", back_populates="user", cascade="all, delete-orphan")
    saved_articles = relationship("SavedArticle", back_populates="user", cascade="all, delete-orphan")


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(100))
    author = Column(String(100))
    image = Column(String(500))
    summary = Column(Text, nullable=True)
    is_sensitive = Column(Boolean, default=False, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    user = relationship("User", back_populates="articles")
    comments = relationship("Comment", back_populates="article", cascade="all, delete-orphan")

class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    sentiment = Column(String(20), default="NEUTRAL")  # POSITIVE, NEGATIVE, NEUTRAL
    user_id = Column(Integer, ForeignKey("users.id"))
    article_id = Column(Integer, ForeignKey("articles.id"))

    user = relationship("User", back_populates="comments")
    article = relationship("Article", back_populates="comments")
    ratings = relationship("CommentRating", back_populates="comment", cascade="all, delete-orphan")

    @property
    def upvotes(self):
        return sum(1 for r in self.ratings if r.vote == 1)
        
    @property
    def downvotes(self):
        return sum(1 for r in self.ratings if r.vote == -1)
        
    @property
    def score(self):
        return self.upvotes - self.downvotes

class CommentRating(Base):
    __tablename__ = "comment_ratings"

    id = Column(Integer, primary_key=True, index=True)
    vote = Column(Integer, nullable=False) # 1 for upvote, -1 for downvote
    user_id = Column(Integer, ForeignKey("users.id"))
    comment_id = Column(Integer, ForeignKey("comments.id"))

    user = relationship("User", back_populates="ratings")
    comment = relationship("Comment", back_populates="ratings")

class EmailVerificationCode(Base):
    __tablename__ = "email_verification_codes"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), index=True, nullable=False)
    code = Column(String(10), nullable=False)
    expires_at = Column(DateTime, nullable=False)

class SearchHistory(Base):
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="searches")

class SavedArticle(Base):
    __tablename__ = "saved_articles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    article_id = Column(Integer, ForeignKey("articles.id"))
    saved_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="saved_articles")
    article = relationship("Article")
