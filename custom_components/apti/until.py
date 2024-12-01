"""Defines various utility."""

from datetime import datetime
from dateutil.relativedelta import relativedelta

def format_date_target_months_ago(target: int) -> str:
    """After calculating the date target months ago, format it in the format 'YYYYMM'."""
    current_date = datetime.now()
    previous_date = current_date - relativedelta(months=target)

    formatted_date = previous_date.strftime('%Y%m')
    return formatted_date

def get_target_month(target: int) -> str:
    """Returns months before the current month to target months in numeric form."""
    current_date = datetime.now()
    target_month = (current_date.month - target) % 12 or 12
    return str(target_month)
