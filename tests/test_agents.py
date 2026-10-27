from services.demo_data import demo_payload
from agents.market_analysis_agent import MarketAnalysisAgent
from agents.company_updates_agent import CompanyUpdatesAgent
from agents.education_agent import FinancialEducationAgent
def test_fallback_agents():
    indexes,_,news=demo_payload(); assert "Nifty" in MarketAnalysisAgent().run(indexes,news); assert CompanyUpdatesAgent().run(news); assert FinancialEducationAgent().run().term
