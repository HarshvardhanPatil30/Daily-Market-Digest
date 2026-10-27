from datetime import datetime
from models.schemas import DigestData
from services.demo_data import demo_payload
from agents.education_agent import FinancialEducationAgent
from services.pdf_generator import DigestPDF
from pypdf import PdfReader
def test_pdf_sections(tmp_path):
    idx,moves,news=demo_payload(); data=DigestData('x',idx[0].market_date,datetime.now(),'demo',idx,'narrative',news,news[:1],FinancialEducationAgent().run(),moves[:5],moves[5:],[],True)
    path=DigestPDF().build(data,tmp_path/'test.pdf'); text=' '.join(p.extract_text() or '' for p in PdfReader(path).pages)
    assert 'Top Gainers' in text and 'Word of the Day' in text
