from services.pdf_generator import DigestPDF
class ReportAssemblyAgent:
    def run(self,digest,output):
        if not digest.indexes and digest.mode != "demo": raise ValueError("Cannot make a live report without verified indexes")
        if not digest.education: raise ValueError("Education section is required")
        return DigestPDF().build(digest,output)
