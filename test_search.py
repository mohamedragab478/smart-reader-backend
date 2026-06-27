import urllib.request
import urllib.parse
import json
import re

q = "محمد نجيب"
max_results = 9

is_arabic = bool(re.search(r'[\u0600-\u06FF]', q))
lang = "ar" if is_arabic else "en"

url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(q)}&utf8=&format=json&srlimit={max_results}"
req = urllib.request.Request(url, headers={'User-Agent': 'SmartReader/1.0'})

with urllib.request.urlopen(req, timeout=10) as response:
    data = json.loads(response.read().decode('utf-8'))

results = []
for item in data.get('query', {}).get('search', []):
    title = item.get('title', '')
    snippet_html = item.get('snippet', '')
    snippet = re.sub(r'<[^>]+>', '', snippet_html)
    article_url = f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
    results.append({
        "title": title,
        "url": article_url,
        "snippet": snippet,
        "source": "ويكيبيديا" if is_arabic else "Wikipedia"
    })

print(json.dumps(results, indent=2, ensure_ascii=False))
