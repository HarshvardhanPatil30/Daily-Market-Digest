class MarketAnalysisAgent:
    def __init__(self, ollama=None): self.ollama=ollama
    def run(self,indexes,news):
        facts="; ".join(f"{i.name} closed at {i.close:.2f}, {i.percent_change:+.2f}%" for i in indexes)
        headlines=" | ".join(a.title[:180] for a in news[:3])
        if self.ollama and self.ollama.available():
            prompt=("Write a factual 90-word Indian market narrative based ONLY on these validated figures and headlines. Do not predict, recommend, or claim causality unless explicitly stated. Figures: "+facts+" Headlines: "+headlines)
            try: return self.ollama.generate(prompt)
            except Exception: pass
        direction="mixed" if len({i.percent_change > 0 for i in indexes}) > 1 else ("higher" if indexes[0].percent_change >= 0 else "lower")
        return f"The validated index snapshot showed a {direction} session: {facts}. The accompanying headlines are presented as reported developments, not as verified explanations for price moves."
