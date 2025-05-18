import datetime
from typing import Optional

def escape_md(text: str) -> str:
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    text = text.replace('\\', '\\\\') 
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text


def format_datetime_md(date_obj: Optional[datetime.datetime]) -> str:
    if not date_obj:
        return 'N/A'

    if date_obj.tzinfo is None:
        date_obj = date_obj.replace(tzinfo=datetime.timezone.utc)
    else:
        date_obj = date_obj.astimezone(datetime.timezone.utc)
    
    formatted = date_obj.strftime('%Y-%m-%d %H:%M UTC')
    return formatted.replace('-', '\\-')

def format_date_md(date_obj: Optional[datetime.date | datetime.datetime]) -> str:
    if not date_obj:
        return 'N/A'
    formatted = date_obj.strftime('%Y-%m-%d')

    return formatted.replace('-', '\\-') 
