import argparse
import pytest
from main import main, parse_date
def test_bad_date():
    with pytest.raises(argparse.ArgumentTypeError, match='Date must use YYYY-MM-DD'):
        parse_date('bad')
def test_help():
    try: main(['--help'])
    except SystemExit as e: assert e.code == 0
