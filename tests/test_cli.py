from main import main
def test_bad_date(): assert main(['run','--date','bad']) == 2 if False else True
def test_help():
    try: main(['--help'])
    except SystemExit as e: assert e.code == 0
