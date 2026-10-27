import logging, uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo
from config import settings
from models.schemas import DigestData
from services.database import Database
from services.demo_data import demo_payload
from services.ollama_service import OllamaService
from services.trading_calendar import latest_weekday, is_weekday
from services.validation import validate_indexes
from agents.market_data_agent import MarketDataAgent
from agents.nse_movers_agent import NSEMoversAgent
from agents.news_agent import NewsCollectionAgent
from agents.company_updates_agent import CompanyUpdatesAgent
from agents.market_analysis_agent import MarketAnalysisAgent
from agents.education_agent import FinancialEducationAgent
from agents.report_assembly_agent import ReportAssemblyAgent

class Orchestrator:
    def __init__(self, config=settings): self.config=config; self.db=Database(config.database_path); self.log=logging.getLogger(__name__)
    def run(self, demo=False, requested_date=None):
        ist=ZoneInfo(self.config.timezone); now=datetime.now(ist); target=requested_date or latest_weekday(now.date()); execution_id=str(uuid.uuid4()); mode="demo" if demo else "live"
        self.db.initialize(); self.db.start_run(execution_id,now.isoformat(),mode); ai=OllamaService(self.config.ollama_base_url,self.config.ollama_model,self.config.timeout_seconds)
        try:
            self.log.info("Run %s started: mode=%s target=%s",execution_id,mode,target)
            if not demo and not is_weekday(target): raise ValueError("Requested date is not a weekday; exchange holidays must be verified by data availability")
            if demo: indexes,moves,news=demo_payload(target)
            else:
                indexes=MarketDataAgent().run(target); moves=NSEMoversAgent().run(target); gainers,losers=moves; news=NewsCollectionAgent().run()
            ok,msg=validate_indexes(indexes,target)
            if not ok: raise ValueError(msg)
            if demo: gainers=sorted((m for m in moves if m.percent_change>0),key=lambda m:m.percent_change,reverse=True)[:5]; losers=sorted((m for m in moves if m.percent_change<0),key=lambda m:m.percent_change)[:5]
            disclosures=[]
            if demo: disclosures.append("Demo mode: all figures and headlines are fictional synthetic fixtures.")
            if not ai.available(): disclosures.append("Ollama narrative generation was unavailable; a conservative deterministic narrative was used.")
            narrative=MarketAnalysisAgent(ai).run(indexes,news); updates=CompanyUpdatesAgent().run(news)
            education=FinancialEducationAgent().run()
            digest=DigestData(execution_id,target,now,mode,indexes,narrative,news,updates,education,gainers,losers,disclosures,complete=True)
            out=self.config.output_dir / f"{target:%Y}" / f"{target:%m}" / f"{target:%d}" / f"market_digest_{target:%Y-%m-%d}.pdf"
            path=ReportAssemblyAgent().run(digest,out); self.db.save_digest(execution_id,path,datetime.now(ist).isoformat(),disclosures)
            self.db.finish_run(execution_id,datetime.now(ist).isoformat(),target,"completed",True,ai_mode="ollama" if ai.available() else "offline")
            self.log.info("Run %s completed: %s",execution_id,path); return digest,path
        except Exception as exc:
            self.log.exception("Run %s failed",execution_id); self.db.finish_run(execution_id,datetime.now(ist).isoformat(),target,"failed",False,str(exc),"offline"); raise
    def source_status(self):
        ai=OllamaService(self.config.ollama_base_url,self.config.ollama_model,self.config.timeout_seconds)
        statuses={"ollama": ai.available()}
        try:
            from services.news_service import collect_news; statuses["google_news_rss"] = bool(collect_news(limit=1))
        except Exception as e: statuses["google_news_rss"] = f"unavailable: {e}"
        try:
            import yfinance; statuses["yfinance"] = "installed"
        except ImportError: statuses["yfinance"] = "not installed"
        return statuses
