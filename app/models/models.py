from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)

    comments = relationship("Comment", back_populates="user")

class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(100))
    author = Column(String(100))
    image = Column(String(500))
    summary = Column(Text, nullable=True)

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
