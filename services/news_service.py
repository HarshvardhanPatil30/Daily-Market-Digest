from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit
import re
from models.schemas import NewsArticle

QUERIES=["Indian stock market", "Nifty 50 Sensex", "RBI inflation monetary policy", "India corporate earnings"]
def _norm(text): return re.sub(r"\W+", "", text.lower())
def _url(url):
    p=urlsplit(url); return urlunsplit((p.scheme,p.netloc,p.path,"",""))
def deduplicate(items):
    seen=set(); result=[]
    for item in items:
        key=(_norm(item.title),_url(item.url))
        if key[0] in seen or key[1] in seen: continue
        seen.update(key); result.append(item)
    return result
def collect_news(timeout=20, limit=6):
    try: import feedparser
    except ImportError as exc: raise RuntimeError("feedparser is not installed. Install requirements.txt or use --demo.") from exc
    all_items=[]; now=datetime.now(timezone.utc)
    for query in QUERIES:
        feed=feedparser.parse("https://news.google.com/rss/search?q="+query.replace(" ","+")+"&hl=en-IN&gl=IN&ceid=IN:en", agent="DailyMarketDigest/1.0")
        for e in feed.entries:
            try: published=parsedate_to_datetime(e.published).astimezone(timezone.utc) if getattr(e,"published",None) else None
            except (TypeError, ValueError): published=None
            title=getattr(e,"title","").strip(); url=getattr(e,"link","")
            if title and url: all_items.append(NewsArticle(title,url,getattr(getattr(e,"source",None),"title",None),published,query,now,""))
    terms=("nifty","sensex","market","stock","rbi","inflation","earnings","shares","equity")
    filtered=[x for x in deduplicate(all_items) if any(t in x.title.lower() for t in terms)]
    filtered.sort(key=lambda x: x.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return filtered[:limit]
