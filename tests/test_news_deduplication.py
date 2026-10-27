from datetime import datetime,timezone
from models.schemas import NewsArticle
from services.news_service import deduplicate
def test_deduplicate_titles_and_urls():
    now=datetime.now(timezone.utc); one=NewsArticle("Markets rise!","https://x.test/a?x=1",None,None,"q",now); two=NewsArticle("markets rise","https://x.test/b",None,None,"q",now)
    assert len(deduplicate([one,two]))==1
