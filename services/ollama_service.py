import json, requests
class OllamaService:
    def __init__(self, base_url, model, timeout=20): self.base_url=base_url.rstrip('/'); self.model=model; self.timeout=timeout
    def available(self):
        if not self.model: return False
        try:
            response=requests.get(self.base_url+"/api/tags",timeout=3); response.raise_for_status()
            return any(m.get("name","").split(":")[0] == self.model.split(":")[0] for m in response.json().get("models",[]))
        except requests.RequestException: return False
    def generate(self, prompt):
        if not self.available(): raise RuntimeError("Ollama or configured model is unavailable")
        r=requests.post(self.base_url+"/api/generate",json={"model":self.model,"prompt":prompt,"stream":False,"options":{"temperature":0.1}},timeout=self.timeout); r.raise_for_status()
        text=r.json().get("response","").strip()
        if not text: raise ValueError("Ollama returned an empty response")
        return text
