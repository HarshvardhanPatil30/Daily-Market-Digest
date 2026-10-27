import pytest
from services.validation import calculate_change
def test_change_positive_negative_zero():
    assert calculate_change(110,100)==(10.0,10.0)
    assert calculate_change(90,100)==(-10.0,-10.0)
    assert calculate_change(100,100)==(0.0,0.0)
@pytest.mark.parametrize("a,b",[(None,1),(1,None),(1,0),(-1,2)])
def test_invalid_prices(a,b):
    with pytest.raises(ValueError): calculate_change(a,b)
