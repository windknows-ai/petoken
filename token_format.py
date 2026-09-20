"""Central presentation-only formatting for Token values."""

TOKEN_NUMBER_FORMATS = ('full', 'compact')
DEFAULT_TOKEN_NUMBER_FORMAT = 'compact'
_UNITS = ((1_000, 'K'), (1_000_000, 'M'), (1_000_000_000, 'B'),
          (1_000_000_000_000, 'T'))


def normalize_token_format(value):
    return value if value in TOKEN_NUMBER_FORMATS else DEFAULT_TOKEN_NUMBER_FORMAT


def _token_count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def format_token_value(value, style=DEFAULT_TOKEN_NUMBER_FORMAT):
    value = _token_count(value)
    if value is None:
        return 'N/A'
    if normalize_token_format(style) == 'full' or value < 1_000:
        return f'{value:,}'
    index = max(i for i,(scale,_) in enumerate(_UNITS) if value >= scale)
    scale, suffix = _UNITS[index]
    if index < len(_UNITS)-1 and value/scale >= 999.995:
        scale, suffix = _UNITS[index+1]
    return f'{value/scale:.2f}{suffix}'


def format_tokens(value, style=DEFAULT_TOKEN_NUMBER_FORMAT):
    formatted = format_token_value(value, style)
    return formatted if formatted == 'N/A' else formatted+' Tokens'


def format_ratio(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return 'N/A'
    return f'{value:.2f}%'
