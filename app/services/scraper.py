import socket
import ipaddress
import re
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

MAX_SCRAPE_BYTES = 5 * 1024 * 1024  # 5 MB max response size


def is_safe_url(url: str) -> bool:
    """
    Validates URL to protect against Server-Side Request Forgery (SSRF).
    Only allows HTTP/HTTPS and rejects private, loopback, link-local, and cloud metadata IPs.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # Check against dangerous known hostnames
        blocked_hostnames = {
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "::1",
            "metadata",
            "metadata.google.internal",
            "instance-data",
        }
        if hostname.lower() in blocked_hostnames or hostname.lower().endswith(".internal") or hostname.lower().endswith(".local"):
            return False

        # Resolve hostname to all associated IPs and verify each is public
        addr_info = socket.getaddrinfo(hostname, None)
        for family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False

        return True
    except Exception:
        return False


def scrape_article_url(url: str) -> dict:
    """
    Scrapes a webpage URL safely with SSRF protection and extracts:
    - title
    - content (main body text)
    - author
    - image (cover image)
    - category
    """
    # 1. SSRF URL Check
    if not is_safe_url(url):
        return {
            "title": "فشل جلب المقال",
            "content": "عذراً، هذا الرابط غير مسموح بجلبه لدواعي الأمان والحماية.",
            "author": "خطأ النظام",
            "image": "https://images.unsplash.com/photo-1594322436404-5a0526db4d13?w=600&auto=format&fit=crop&q=60",
            "category": "خطأ"
        }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        with requests.get(url, headers=headers, timeout=10, stream=True, allow_redirects=True) as response:
            # Re-check redirect target URL for SSRF
            if not is_safe_url(response.url):
                return {
                    "title": "فشل جلب المقال",
                    "content": "تم إعادة توجيه الرابط إلى عنوان غير مسموح به.",
                    "author": "خطأ النظام",
                    "image": "https://images.unsplash.com/photo-1594322436404-5a0526db4d13?w=600&auto=format&fit=crop&q=60",
                    "category": "خطأ"
                }

            response.raise_for_status()

            # Enforce max download size (5MB)
            content_bytes = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                content_bytes.extend(chunk)
                if len(content_bytes) > MAX_SCRAPE_BYTES:
                    return {
                        "title": "فشل جلب المقال",
                        "content": "حجم الصفحة يتجاوز الحد الأقصى المسموح به (5 ميجابايت).",
                        "author": "خطأ النظام",
                        "image": "https://images.unsplash.com/photo-1594322436404-5a0526db4d13?w=600&auto=format&fit=crop&q=60",
                        "category": "خطأ"
                    }

            encoding = response.encoding or response.apparent_encoding or "utf-8"
            if encoding.upper() == "ISO-8859-1":
                encoding = response.apparent_encoding or "utf-8"

            html_text = content_bytes.decode(encoding, errors="replace")

        soup = BeautifulSoup(html_text, "html.parser")

        # 1. Extract Title
        title = ""
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        else:
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
            author_tag = soup.find(class_=re.compile(r"author|byline|writer", re.I))
            if author_tag:
                author = author_tag.get_text().strip()

        # 3. Extract Cover Image
        image_url = "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=600&auto=format&fit=crop&q=60"  # default
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            image_url = og_image["content"]
        else:
            for img in soup.find_all("img"):
                src = img.get("src")
                if src and not src.endswith(".gif") and not src.endswith(".svg"):
                    image_url = urljoin(url, src)
                    break

        # 4. Extract Main Content
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            element.extract()

        paragraphs = soup.find_all("p")
        text_blocks = []
        for p in paragraphs:
            text = p.get_text().strip()
            if len(text) > 30:
                text_blocks.append(text)

        content = "\n\n".join(text_blocks)
        if not content:
            content = soup.body.get_text(separator="\n\n").strip() if soup.body else "تعذر استخلاص محتوى النص من هذا الموقع."
            content = content[:3000]

        # 5. Extract Category
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
        print(f"Scraping error: {e}")
        return {
            "title": "فشل جلب المقال",
            "content": "حدث خطأ أثناء محاولة الاتصال بالموقع أو جلب محتواه.",
            "author": "خطأ النظام",
            "image": "https://images.unsplash.com/photo-1594322436404-5a0526db4d13?w=600&auto=format&fit=crop&q=60",
            "category": "خطأ"
        }
