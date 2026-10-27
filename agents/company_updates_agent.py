class CompanyUpdatesAgent:
    def run(self, articles):
        keywords=("earnings","results","acquisition","merger","appoint","dividend","company","bank","ltd","operational update")
        return [a for a in articles if any(k in a.title.lower() for k in keywords)][:3]
