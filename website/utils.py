import re


def format_phone(raw):
    """Normalizes a phone number to (xxx)-xxx-xxxx. Returns the original
    (trimmed) input unchanged if it doesn't contain a recognizable 10-digit
    US number, rather than guessing."""
    if not raw:
        return raw
    digits = re.sub(r'\D', '', raw)
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    if len(digits) == 10:
        return f'({digits[0:3]})-{digits[3:6]}-{digits[6:10]}'
    return raw.strip()
