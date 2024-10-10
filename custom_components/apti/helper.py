"""Defines helper function."""

from typing import Any
import re

from .const import LOGGER

def get_text_or_log(
    soup_elem: str,
    selector: str | None,
    log_message: str,
    find_method: str = "select_one",
    attr: str | None = None
) -> str:
    """A helper function that finds HTML elements and leaves logs in case of failure."""
    if not soup_elem:
        LOGGER.warning(log_message)
        return ""
    
    elem = getattr(soup_elem, find_method)(selector) if find_method else soup_elem
    if elem:
        return elem.get(attr).strip() if attr else elem.text.strip()
    LOGGER.warning(log_message)
    return ""

def find_value_by_condition(data_dict: dict, condition) -> Any | None:
    for key, value in data_dict.items():
        if condition(key):
            return value
    return None

def is_phone_number(id_value: str) -> bool:
    phone_number_pattern = r'^010\d{8}$'
    return bool(re.match(phone_number_pattern, id_value))
