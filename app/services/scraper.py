import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse

def scrape_article_url(url: str) -> dict:
    """
    Scrapes a webpage URL and extracts:
    - title
    - content (main body text)
    - author
    - image (cover image)
    - category
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Detect encoding
        if response.encoding == 'ISO-8859-1':
            response.encoding = response.apparent_encoding
            
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 1. Extract Title
        title = ""
        # Try og:title first
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"]
        else:
            # Try <h1>
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text().strip()
            else:
                title_tag = soup.find("title")
                if title_tag:
                    title = title_tag.get_text().strip()
        
        if not title:
            title = "مقال مستخلص من الويب"
            
        # 2. Extract Author
        author = "كاتب ويب"
        author_meta = soup.find("meta", attrs={"name": "author"}) or soup.find("meta", property="article:author")
        if author_meta and author_meta.get("content"):
            author = author_meta["content"].strip()
        else:
            # Search for typical author classes
            author_tag = soup.find(class_=re.compile(r"author|byline|writer", re.I))
            if author_tag:
                author = author_tag.get_text().strip()
                
        # 3. Extract Cover Image
        image_url = "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=600&auto=format&fit=crop&q=60"  # default
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            image_url = og_image["content"]
        else:
            # Try finding the first large image in body
            for img in soup.find_all("img"):
                src = img.get("src")
                if src and not src.endswith(".gif") and not src.endswith(".svg"):
                    # Resolve relative url
                    image_url = urljoin(url, src)
                    break

        # 4. Extract Main Content
        # Remove noisy elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            element.extract()
            
        # Find paragraphs
        paragraphs = soup.find_all("p")
        text_blocks = []
        for p in paragraphs:
            text = p.get_text().strip()
            # Ignore short/noise paragraphs (less than 30 characters)
            if len(text) > 30:
                text_blocks.append(text)
                
        content = "\n\n".join(text_blocks)
        
        if not content:
            # Fallback: get raw body text if no paragraphs are found
            content = soup.body.get_text(separator="\n\n").strip() if soup.body else "تعذر استخلاص محتوى النص من هذا الموقع."
            # Limit length if it's too raw and full of noise
            content = content[:3000]

        # 5. Extract/Guess Category or Domain Name
        domain = urlparse(url).netloc.replace("www.", "")
        category = domain.split(".")[0].capitalize()
        
        return {
            "title": title,
            "content": content,
            "author": author,
            "image": image_url,
            "category": category
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Scraping error: {e}")
        return {
            "title": "فشل جلب المقال",
            "content": f"حدث خطأ أثناء محاولة الاتصال بالموقع أو جلب محتواه:\n{str(e)}",
            "author": "خطأ النظام",
            "image": "https://images.unsplash.com/photo-1594322436404-5a0526db4d13?w=600&auto=format&fit=crop&q=60",
            "category": "خطأ"
        }
