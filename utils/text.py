import re

EMOJI_REGEX = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags
    "\u2600-\u26FF"          # misc symbols
    "\u2700-\u27BF"
    "]+",
    flags=re.UNICODE,
)


def strip_emojis(text: str) -> str:
    """Remove emoji glyphs from text while preserving other characters."""
    if not isinstance(text, str):
        return text
    return EMOJI_REGEX.sub("", text)

