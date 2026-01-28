from typing import Dict, Any, Optional

try:
    import pytesseract
except ImportError:
    pytesseract = None


def run_tesseract(pil_img, lang: str = "eng", psm: str = "3") -> Dict[str, Any]:
    if pytesseract is None:
        raise ImportError("pytesseract is not installed")

    config = f"--psm {psm} --oem 1"
    data = pytesseract.image_to_data(pil_img, lang=lang, config=config, output_type=pytesseract.Output.DICT)

    words = data.get("text", [])
    confs = data.get("conf", [])
    text = " ".join([w for w in words if w.strip()])
    avg_conf = (
        sum(float(c) for c in confs if isinstance(c, (int, float, str)) and str(c).isdigit())
        / max(1, len([c for c in confs if str(c).isdigit()]))
    )
    return {
        "text": text,
        "segments": words,
        "confidences": confs,
        "engine": "tesseract",
        "avg_confidence": avg_conf,
    }

