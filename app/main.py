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
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
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

# --- Endpoints ---

@app.get("/api/v1/articles", response_model=List[schemas.ArticleResponse])
def get_articles(db: Session = Depends(get_db)):
    articles = db.query(models.Article).all()
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
def create_comment(comment_in: schemas.CommentCreate, db: Session = Depends(get_db)):
    user_id = comment_in.user.id if comment_in.user else 1
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        user = models.User(id=user_id, name="مستخدم جديد")
        db.add(user)
        db.commit()
        db.refresh(user)

    article_id = None
    if comment_in.article and hasattr(comment_in.article, 'id'):
        article_id = comment_in.article.id
    
    if not article_id:
        raise HTTPException(status_code=400, detail="يجب تحديد المقال المرتبط بالتعليق")

    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="المقال غير موجود")

    sentiment = analyze_sentiment(comment_in.text)

    db_comment = models.Comment(
        text=comment_in.text,
        sentiment=sentiment,
        user_id=user.id,
        article_id=article.id
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    
    return db_comment

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

# --- 🚀 Upgraded Chatbot (RAG) Endpoint ---
@app.post("/api/v1/ai/articles/{article_id}/chat")
def chat_with_article(article_id: int, chat_req: schemas.ChatRequest, db: Session = Depends(get_db)):
    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="المقال غير موجود")
        
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key or not api_key.strip():
        # Fallback offline replies
        user_msg = chat_req.message.lower()
        if any(greeting in user_msg for greeting in ["مرحباً", "hello", "hi", "سلام", "هلا"]):
            return {"reply": "أهلاً بك! أنا مساعدك الذكي لقراءة وتلخيص هذا المقال. كيف يمكنني مساعدتك اليوم؟"}
        
        if any(kw in user_msg for kw in ["لخص", "ملخص", "summary", "summarize"]):
            summary_text = article.summary if article.summary else generate_ai_summary(article.content)
            return {"reply": f"إليك ملخص سريع للمقال:\n{summary_text}"}
            
        return {"reply": f"أهلاً بك! لم يتم ضبط مفتاح Groq API Key في ملف `.env` بعد. يمكنك الحصول عليه مجاناً من https://console.groq.com"}
        
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
        
        # Build messages from history
        messages = [{"role": "system", "content": system_prompt}]
        if chat_req.history:
            for h in chat_req.history:
                role = "user" if h.role == "user" else "assistant"
                messages.append({"role": role, "content": h.content})
        messages.append({"role": "user", "content": chat_req.message})
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=1024,
        )
        return {"reply": response.choices[0].message.content.strip()}
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
        req = urllib.request.Request(url, headers={'User-Agent': 'SmartReader/1.0'})
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
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
        with open("error.log", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"حدث خطأ أثناء البحث: {str(e)}")
