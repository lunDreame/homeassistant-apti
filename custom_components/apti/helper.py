"""Defines helper function."""

from typing import Any
import aiofiles
import json
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
    """Finds value in a dictionary based on a condition."""
    for key, value in data_dict.items():
        if condition(key):
            return value
    return None

def is_phone_number(id_value: str) -> bool:
    """Checks if a string is in phone number format (010 followed by 8 digits)"""
    phone_number_pattern = r'^010\d{8}$'
    return bool(re.match(phone_number_pattern, id_value))

async def get_icon(
    category: str,
    key: str,
    json_file_path: str = "custom_components/apti/icons/icon.json"
) -> str:
    """Asynchronously retrieves an icon from a JSON file using category and key."""
    try:
        async with aiofiles.open(json_file_path, "r", encoding="utf-8") as file:
            content = await file.read()
            data = json.loads(content)
        
        if category in data:
            icon = data[category].get(key, None)
            if icon is None:
                LOGGER.warning(f"Icon for key '{key}' in category '{category}' not found.")
            return icon
        else:
            LOGGER.warning(f"Category '{category}' not found in icon data.")
        return None
    except FileNotFoundError as e:
        LOGGER.error(f"File not found: '{json_file_path}': {e}")
        return None
    except json.JSONDecodeError as e:
        LOGGER.error(f"Error decoding JSON from '{json_file_path}': {e}")
        return None
