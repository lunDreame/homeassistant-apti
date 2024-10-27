"""Defines various utility."""

from datetime import datetime
from dateutil.relativedelta import relativedelta

def format_date_two_months_ago() -> str:
    """After calculating the date two months ago, format it in the format 'YYYYMM'."""
    current_date = datetime.now()
    previous_date = current_date - relativedelta(months=1)

    formatted_date = previous_date.strftime('%Y%m')
    return formatted_date

def get_target_month() -> str:
    """Returns months before the current month to 2 months in numeric form."""
    current_date = datetime.now()
    target_month = (current_date.month - 1) % 12 or 12
    return str(target_month)
