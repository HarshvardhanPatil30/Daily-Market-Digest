from services.database import Database
def test_persistence(tmp_path):
    db=Database(tmp_path/'x.db'); db.initialize(); db.start_run('a','now','demo'); db.finish_run('a','later','2026-10-20','completed',True); assert db.latest()['status']=='completed'


def test_latest_digest_and_email_history(tmp_path):
    from pathlib import Path
    db=Database(tmp_path/'x.db'); db.initialize()
    db.start_run('a','now','live')
    db.finish_run('a','later','2026-10-20','completed',True)
    pdf=tmp_path/'report.pdf'; pdf.write_bytes(b'%PDF-test')
    db.save_digest('a',pdf,'created',[])
    row=db.latest_digest()
    assert row['execution_id']=='a' and row['pdf_path']==str(pdf)
    db.record_email_delivery('a','sent-at','sent','recipient@example.com')
    with db.connect() as con:
        saved=con.execute('SELECT status FROM email_deliveries').fetchone()
    assert saved['status']=='sent'
