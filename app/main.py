import os
import sys
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from dotenv import load_dotenv

# Force UTF-8 encoding for standard output to prevent Uvicorn from crashing when logging Arabic URLs on Windows
if sys.platform == 'win32' and sys.stdout:
    sys.stdout.reconfigure(encoding='utf-8')

from app.db.database import engine, get_db
from app.models import models
from app.schemas import schemas
from app.services.scraper import scrape_article_url
from app.security import get_password_hash, verify_password, create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
from datetime import timedelta, datetime
import random
import requests
import traceback
from fastapi.security import OAuth2PasswordRequestForm

# Load environment variables from .env file
load_dotenv()

# Initialize database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Reader API", version="1.0.0")

# --- CORS Middleware Configuration ---
cors_origins_str = os.environ.get("CORS_ORIGINS", "")
if cors_origins_str:
    allow_origins = [origin.strip() for origin in cors_origins_str.split(",")]
else:
    allow_origins = ["*"]  # Fallback for local development if not set

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Sentiment Analysis Helper ---
def analyze_sentiment(text: str) -> str:
    """
    Analyzes the sentiment of a comment text.
    Works for both Arabic and English using a keyword-based lexicon approach.
    """
    t = text.lower()
    positive_keywords = [
        "جميل", "رائع", "ممتاز", "مفيد", "شكرا", "تحفة", "حب", "جيد", "حلو", 
        "عظيم", "أعجبني", "قوي", "سهل", "واضح",
        "nice", "good", "great", "awesome", "love", "useful", "thanks", "like", "easy"
    ]
    negative_keywords = [
        "سيء", "صعب", "ملل", "خطأ", "فشل", "ضعيف", "لا يعجبني", "حزين", "أسف", 
        "وحش", "ركيك", "ممل", "معقد", "ناقص",
        "bad", "worst", "boring", "error", "fail", "sad", "dislike", "hate", "hard", "difficult"
    ]
    
    pos_count = sum(1 for word in positive_keywords if word in t)
    neg_count = sum(1 for word in negative_keywords if word in t)
    
    if pos_count > neg_count:
        return "POSITIVE"
    elif neg_count > pos_count:
        return "NEGATIVE"
    return "NEUTRAL"

# --- AI Summarization Helper ---
def generate_ai_summary(content: str) -> str:
    """
    Generates a summary of the article using Groq API.
    Falls back to a clean local extraction summary if no Groq API Key is set.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if api_key and api_key.strip():
        try:
            from groq import Groq
            client = Groq(api_key=api_key)
            groq_model = os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b")
            response = client.chat.completions.create(
                model=groq_model,
                messages=[
                    {"role": "system", "content": "You are a professional summarizer. You MUST output ONLY the raw summary text. No intro, no outro, no conversational filler. Summarize the text in the exact same language as the input text."},
                    {"role": "user", "content": f"Summarize this text in 2-3 sentences. Start immediately with the first word of the summary:\n\n{content[:4000]}"}
                ],
                max_tokens=300,
            )
            summary = response.choices[0].message.content.strip()
            
            # Programmatically strip common conversational fillers
            fillers = [
                "Here is a summary of the text",
                "Here is a summary",
                "Here is the summary",
                "Sure, here is a summary",
                "The text can be summarized as follows:",
                "This text is about",
                "إليك ملخص",
                "فيما يلي ملخص"
            ]
            for filler in fillers:
                if summary.lower().startswith(filler.lower()):
                    # Find the end of the first line or colon and slice it
                    idx = summary.find("\n\n")
                    if idx != -1:
                        summary = summary[idx+2:].strip()
                    else:
                        idx = summary.find(":")
                        if idx != -1 and idx < 100:
                            summary = summary[idx+1:].strip()
            return summary.strip('"\'- \n')
        except Exception as e:
            print(f"Error calling Groq API: {e}")
    
    # Fallback / Local summarization (First 2 full sentences)
    sentences = content.replace("\n", " ").split(".")
    fallback_summary = ". ".join([s.strip() for s in sentences[:2] if s.strip()])
    if fallback_summary:
        return fallback_summary + "."
    return content[:150] + "..."

# --- Auth Endpoints ---

def send_verification_email(to_email: str, code: str) -> bool:
    # For development, just print the code.
    print(f"\n{'='*40}")
    print(f"VERIFICATION CODE FOR {to_email}: {code}")
    print(f"{'='*40}\n")
    
    api_key = os.environ.get("BREVO_API_KEY")
    if not api_key:
        print("[Brevo Email Error]: BREVO_API_KEY environment variable is not set.")
        return False

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    payload = {
        "sender": {
            "name": "Smart Reader",
            "email": "smartreadercommunity1@gmail.com"
        },
        "to": [
            {
                "email": to_email
            }
        ],
        "subject": "كود تفعيل حسابك - Smart Reader",
        "htmlContent": f"<div dir='rtl' style='font-family: Arial, sans-serif; padding: 25px; background-color: #f4f4f7;'><div style='max-width: 500px; margin: 0 auto; background: #ffffff; padding: 30px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); text-align: center;'><h2 style='color: #4f46e5; margin-bottom: 10px;'>Smart Reader</h2><p style='color: #4b5563; font-size: 16px;'>كود التفعيل الخاص بحسابك هو:</p><div style='background: #eef2ff; border: 2px dashed #6366f1; border-radius: 12px; padding: 15px; margin: 20px 0;'><span style='color: #4338ca; font-size: 32px; font-weight: bold; letter-spacing: 6px;'>{code}</span></div><p style='color: #9ca3af; font-size: 14px;'>هذا الكود صالح لمدة 10 دقائق فقط.</p></div></div>"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code in (200, 201, 202):
            print(f"[Brevo Email Success] Status Code: {response.status_code}")
            print(f"[Brevo Email Response Body]: {response.text}")
            return True
        else:
            print(f"[Brevo Email Failure] Status Code: {response.status_code}")
            print(f"[Brevo Email Response Body]: {response.text}")
            print(f"[Brevo Email Response Headers]: {dict(response.headers)}")
            print(f"[Brevo Email Exception Traceback]: None (HTTP Status {response.status_code})")
            return False
    except Exception as e:
        print(f"[Brevo Email Exception Failure]: {e}")
        print(f"[Brevo Email Exception Traceback]:\n{traceback.format_exc()}")
        return False

@app.post("/api/v1/auth/request-verification")
def request_verification(req: schemas.EmailVerificationRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == req.email).first()
    if user:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مسجل مسبقاً")
        
    code = str(random.randint(100000, 999999))
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    
    # Delete old codes for this email
    db.query(models.EmailVerificationCode).filter(models.EmailVerificationCode.email == req.email).delete()
    
    db_code = models.EmailVerificationCode(email=req.email, code=code, expires_at=expires_at)
    db.add(db_code)
    db.commit()
    
    send_verification_email(req.email, code)
    return {"message": "تم إرسال كود التفعيل بنجاح"}

@app.post("/api/v1/auth/register", response_model=schemas.Token)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == user_in.email).first()
    if user:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مسجل مسبقاً")
        
    # Verify code
    db_code = db.query(models.EmailVerificationCode).filter(
        models.EmailVerificationCode.email == user_in.email,
        models.EmailVerificationCode.code == user_in.code
    ).first()
    
    if not db_code:
        raise HTTPException(status_code=400, detail="كود التفعيل غير صحيح")
        
    if db_code.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="انتهت صلاحية كود التفعيل")
    
    hashed_password = get_password_hash(user_in.password)
    new_user = models.User(name=user_in.name, email=user_in.email, hashed_password=hashed_password)
    db.add(new_user)
    
    # Delete the code so it cannot be used again
    db.delete(db_code)
    db.commit()
    db.refresh(new_user)
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": new_user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "user": new_user}

@app.post("/api/v1/auth/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="البريد الإلكتروني أو كلمة المرور غير صحيحة",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "user": user}

# --- Endpoints ---

@app.get("/api/v1/articles", response_model=List[schemas.ArticleResponse])
def get_articles(db: Session = Depends(get_db)):
    articles = db.query(models.Article).order_by(models.Article.id.desc()).all()
    return articles

@app.get("/api/v1/ai/articles/{article_id}/summary")
def get_article_summary(article_id: int, db: Session = Depends(get_db)):
    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="المقال غير موجود")
    
    # Generate live summary
    summary = generate_ai_summary(article.content)
    return summary

@app.post("/api/v1/comments", response_model=schemas.CommentResponse)
def create_comment(comment_in: schemas.CommentCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    article = db.query(models.Article).filter(models.Article.id == comment_in.article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="المقال غير موجود")

    sentiment = analyze_sentiment(comment_in.text)

    db_comment = models.Comment(
        text=comment_in.text,
        sentiment=sentiment,
        user_id=current_user.id,
        article_id=article.id
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    
    return db_comment


@app.post("/api/v1/comments/{comment_id}/rate", response_model=schemas.CommentResponse)
def rate_comment(comment_id: int, rating_in: schemas.CommentRatingCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="التعليق غير موجود")
        
    if rating_in.vote not in [1, -1]:
        raise HTTPException(status_code=400, detail="تقييم غير صالح. يجب أن يكون 1 أو -1")

    # Check if user already rated this comment
    existing_rating = db.query(models.CommentRating).filter(
        models.CommentRating.comment_id == comment_id,
        models.CommentRating.user_id == current_user.id
    ).first()
    
    if existing_rating:
        if existing_rating.vote == rating_in.vote:
            # User wants to remove their vote
            db.delete(existing_rating)
        else:
            # User wants to change their vote
            existing_rating.vote = rating_in.vote
    else:
        # Create new rating
        new_rating = models.CommentRating(
            vote=rating_in.vote,
            user_id=current_user.id,
            comment_id=comment_id
        )
        db.add(new_rating)
        
    db.commit()
    db.refresh(comment)
    return comment


@app.delete("/api/v1/comments/{comment_id}")
def delete_comment(comment_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="التعليق غير موجود")
        
    if comment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="غير مصرح لك بحذف هذا التعليق")
        
    # Delete associated ratings
    db.query(models.CommentRating).filter(models.CommentRating.comment_id == comment_id).delete()
    db.delete(comment)
    db.commit()
    return {"message": "تم حذف التعليق بنجاح", "id": comment_id}


# --- 🚀 Upgraded Scraping Endpoint ---
@app.post("/api/v1/articles/scrape", response_model=schemas.ArticleResponse)
def scrape_and_add_article(req: schemas.ScrapeRequest, db: Session = Depends(get_db)):
    scraped_data = scrape_article_url(req.url)
    
    # Auto-generate next ID
    max_id_article = db.query(models.Article).order_by(models.Article.id.desc()).first()
    next_id = (max_id_article.id + 1) if max_id_article else 1
    
    db_article = models.Article(
        id=next_id,
        title=scraped_data["title"],
        content=scraped_data["content"],
        category=scraped_data["category"],
        author=scraped_data["author"],
        image=scraped_data["image"],
        summary=""  # Generate on demand
    )
    
    db.add(db_article)
    db.commit()
    db.refresh(db_article)
    
    return db_article

# --- 📁 File Upload Endpoint ---
import io
import docx
from PyPDF2 import PdfReader

@app.post("/api/v1/articles/upload", response_model=schemas.ArticleResponse)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="الملف غير صالح")
        
    ext = file.filename.split('.')[-1].lower()
    content_text = ""
    title = file.filename.rsplit('.', 1)[0]
    
    try:
        file_bytes = await file.read()
        
        if ext == "txt":
            content_text = file_bytes.decode('utf-8', errors='ignore')
        elif ext == "pdf":
            reader = PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    content_text += text + "\n"
        elif ext == "docx":
            doc = docx.Document(io.BytesIO(file_bytes))
            for para in doc.paragraphs:
                content_text += para.text + "\n"
        else:
            raise HTTPException(status_code=400, detail="نوع الملف غير مدعوم. يرجى رفع ملفات (pdf, docx, txt)")
            
        if not content_text.strip():
            raise HTTPException(status_code=400, detail="لم نتمكن من قراءة أي نص من الملف")
            
        # Add to database as article
        max_id_article = db.query(models.Article).order_by(models.Article.id.desc()).first()
        next_id = (max_id_article.id + 1) if max_id_article else 1
        
        db_article = models.Article(
            id=next_id,
            title=title,
            content=content_text.strip(),
            category="مستند مرفوع",
            author="أنت",
            image=None,
            summary=""
        )
        db.add(db_article)
        db.commit()
        db.refresh(db_article)
        return db_article
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"حدث خطأ أثناء معالجة الملف: {str(e)}")

from fastapi.responses import StreamingResponse

# --- 🚀 Upgraded Chatbot (RAG) Endpoint ---
@app.post("/api/v1/ai/articles/{article_id}/chat")
def chat_with_article(article_id: int, chat_req: schemas.ChatRequest, db: Session = Depends(get_db)):
    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="المقال غير موجود")
        
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key or not api_key.strip():
        user_msg = chat_req.message.lower()
        if any(greeting in user_msg for greeting in ["مرحباً", "hello", "hi", "سلام", "هلا"]):
            reply_text = "أهلاً بك! أنا مساعدك الذكي لقراءة وتلخيص هذا المقال. كيف يمكنني مساعدتك اليوم؟"
        elif any(kw in user_msg for kw in ["لخص", "ملخص", "summary", "summarize"]):
            summary_text = article.summary if article.summary else generate_ai_summary(article.content)
            reply_text = f"إليك ملخص سريع للمقال:\n{summary_text}"
        else:
            reply_text = "أهلاً بك! لم يتم ضبط مفتاح Groq API Key في ملف `.env` بعد. يمكنك الحصول عليه مجاناً من https://console.groq.com"
        
        return {"reply": reply_text}
        
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        
        system_prompt = f"""أنت مساعد قراءة ذكي وتفاعلي لموقع "Smart Reader". 
وظيفتك الإجابة عن أي أسئلة يطرحها القارئ حول المقال التالي بدقة بالغة وبنفس لغة سؤال القارئ (العربية أو الإنجليزية).
تجنب تأليف معلومات ليست في المقال، وإذا سألك عن موضوع عام غير موجود بالمقال وضح له ذلك ثم أجب باختصار وبشكل مفيد.

محتوى المقال كمرجع لك:
العنوان: {article.title}
الكاتب: {article.author}
التصنيف: {article.category}
المحتوى:
{article.content[:4000]}"""
        
        # Build messages safely (filtering out empty messages)
        messages = [{"role": "system", "content": system_prompt}]
        if chat_req.history:
            for h in chat_req.history:
                if h.content and h.content.strip():
                    role = "user" if h.role == "user" else "assistant"
                    messages.append({"role": role, "content": h.content.strip()})
        messages.append({"role": "user", "content": chat_req.message.strip()})
        
        groq_model = os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b")
        response = client.chat.completions.create(
            model=groq_model,
            messages=messages,
            max_tokens=1024,
        )
        reply_text = response.choices[0].message.content.strip()
        return {"reply": reply_text}

    except Exception as e:
        print(f"Groq Chat error: {e}")
        return {"reply": f"حدث خطأ أثناء الاتصال بالذكاء الاصطناعي: {str(e)}"}

# --- 🔍 Web Search Endpoint ---
@app.get("/api/v1/search", response_model=List[schemas.SearchResult])
def web_search(q: str, max_results: int = 8):
    """
    Searches Wikipedia (Arabic or English depending on query) and returns article results.
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="يجب إدخال كلمة بحث")
    try:
        import urllib.request
        import urllib.parse
        import json
        import re

        # Detect if query has Arabic characters
        is_arabic = bool(re.search(r'[\u0600-\u06FF]', q))
        lang = "ar" if is_arabic else "en"
        
        # Wikipedia Search API
        url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(q)}&utf8=&format=json&srlimit={max_results}"
        headers = {
            'User-Agent': 'SmartReaderBot/1.0 (https://github.com/mohamedragab478/smart-reader-backend; bot@example.com)'
        }
        req = urllib.request.Request(url, headers=headers)
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise HTTPException(status_code=429, detail="عذراً، ويكيبيديا تمنع كثرة الطلبات حالياً. يرجى المحاولة بعد قليل.")
            raise e
            
        results = []
        for item in data.get('query', {}).get('search', []):
            title = item.get('title', '')
            # Clean HTML tags from snippet
            snippet_html = item.get('snippet', '')
            snippet = re.sub(r'<[^>]+>', '', snippet_html)
            
            # Construct Wikipedia URL
            article_url = f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
            
            results.append(schemas.SearchResult(
                title=title,
                url=article_url,
                snippet=snippet,
                image=None,
                source="ويكيبيديا" if is_arabic else "Wikipedia"
            ))
            
        return results
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"حدث خطأ أثناء البحث: {str(e)}")
