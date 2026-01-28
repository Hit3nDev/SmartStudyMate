from typing import Dict

try:
    from spellchecker import SpellChecker
except ImportError:
    SpellChecker = None


def clean_text(text: str, enable_spellcheck: bool = False) -> Dict[str, str]:
    if not text:
        return {"text": ""}
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned = "\n".join(lines)

    if enable_spellcheck and SpellChecker:
        spell = SpellChecker()
        tokens = []
        for word in cleaned.split():
            corrected = spell.correction(word) if word.isalpha() else word
            tokens.append(corrected or word)
        cleaned = " ".join(tokens)

    return {"text": cleaned}

