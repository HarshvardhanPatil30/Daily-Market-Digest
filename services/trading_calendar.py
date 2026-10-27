from datetime import date, timedelta

def latest_weekday(value: date) -> date:
    while value.weekday() >= 5: value -= timedelta(days=1)
    return value

def is_weekday(value: date) -> bool:
    return value.weekday() < 5
