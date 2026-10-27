from config import Settings
from services.orchestrator import Orchestrator
def test_demo_no_services(tmp_path):
    config=Settings(output_dir=tmp_path/'reports',database_path=tmp_path/'db.sqlite',log_dir=tmp_path/'logs',ollama_model='')
    digest,path=Orchestrator(config).run(demo=True); assert path.exists() and digest.mode=='demo'
