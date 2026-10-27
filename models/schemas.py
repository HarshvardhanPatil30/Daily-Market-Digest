from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import List, Optional

@dataclass
class IndexSnapshot:
    name: str; symbol: str; close: float; previous_close: float; change: float; percent_change: float
    market_date: date; source: str; retrieved_at: datetime; validated: bool = True

@dataclass
class StockMove:
    name: str; symbol: str; close: float; change: float; percent_change: float
    market_date: date; source: str; validated: bool = True

@dataclass
class NewsArticle:
    title: str; url: str; publisher: Optional[str]; published_at: Optional[datetime]
    query: str; retrieved_at: datetime; summary: str = ""

@dataclass
class EducationTerm:
    term: str; definition: str; explanation: str; why_it_matters: str; source: str

@dataclass
class DigestData:
    execution_id: str; trading_date: date; generated_at: datetime; mode: str
    indexes: List[IndexSnapshot] = field(default_factory=list)
    narrative: str = ""; news: List[NewsArticle] = field(default_factory=list)
    company_updates: List[NewsArticle] = field(default_factory=list)
    education: Optional[EducationTerm] = None
    gainers: List[StockMove] = field(default_factory=list); losers: List[StockMove] = field(default_factory=list)
    disclosures: List[str] = field(default_factory=list); complete: bool = False

def serialize(value):
    if hasattr(value, "isoformat"): return value.isoformat()
    if hasattr(value, "__dataclass_fields__"): return asdict(value)
    raise TypeError(f"Not serializable: {type(value)!r}")
